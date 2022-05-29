#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""TUM CS Bot - a generic Zulip bot.

This bot is currently especially intended for administrative tasks.
It supports several commands which can be written to the bot using
a private message or a message starting with @mentioning the bot.
"""

import atexit
import logging
import signal
from graphlib import TopologicalSorter
from multiprocessing import Queue
from threading import Lock, Thread
from typing import Any, Dict, Final, Iterable, List, Optional, Set, Tuple, Type, cast

from tumcsbot import lib
from tumcsbot.client import Client
from tumcsbot.plugin import (
    Event, _Plugin, EventType, PluginContext, get_zulip_events_from_plugins
)


class _RootClient(Client):
    """Enhanced Client class with additional functionality.

    Particularly, this client initializes the Client's database tables.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Enhance the constructor of the parent class."""
        super().__init__(*args, **kwargs)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize some tables of the database."""
        self._db.checkout_table(
            'PublicStreams', '(StreamName text primary key, Subscribed integer not null)'
        )
        # Get previous data.
        old_streams: Dict[str, int] = dict(cast(Iterable[Tuple[str, int]], self._db.execute(
            'select StreamName, Subscribed from PublicStreams'
        )))
        # Clear table to prevent deprecated information.
        self._db.execute('delete from PublicStreams')

        # Fill in current data.
        stream_names: List[str] = self.get_public_stream_names(use_db = False)
        for stream_name in stream_names:
            subscribed: bool = False
            # We do not compare the streams using lib.stream_names_equal here,
            # because we store the stream names in the database as we receive
            # them from Zulip. There is no user interaction involved.
            if stream_name in old_streams and old_streams[stream_name] == 1:
                subscribed = True
            self._db.execute(
                'insert or ignore into PublicStreams values (?, ?)',
                stream_name, subscribed, commit=True
            )


class _ZulipEventListener(Thread):
    """Handle incoming events from the Zulip server.

    Arguments:
        zuliprc    The zuliprc of the bot.
        events     A list of events (strings) to listen for.
        queue      The queue to push the preprocessed events to.
    """
    def __init__(self, zuliprc: str, events: List[str], queue: "Queue[Event]") -> None:
        super().__init__(name="zulip_event_listener", daemon=True)
        self.events: List[str] = events
        self.queue: "Queue[Event]" = queue
        # Init own Zulip client.
        self.client: Client = Client(config_file=zuliprc)

    def run(self) -> None:
        self.client.call_on_each_event(
            lambda event: self.queue.put(Event(sender="_root", type=EventType.ZULIP, data=event)),
            event_types=self.events,
            all_public_streams=True
        )


class TumCSBot:
    """Main Bot class.

    Use run() to run the bot.

    Arguments:
    ----------
    zuliprc       zuliprc file containing the bot's configuration
    db_path       path to the bot's database
    debug         debugging mode switch
    logfile       use LOGFILE for logging output
    """
    QUEUE_LIMIT_SIZE: Final[int] = 4096

    def __init__(
        self,
        zuliprc: str,
        db_path: str,
        debug: bool = False,
        logfile: Optional[str] = None
    ) -> None:
        self.events: List[str]
        self.plugins: Dict[str, _Plugin] = {}
        self.restart: bool = False

        # Init logging.
        logging_level: int = logging.WARNING
        if debug:
            logging_level = logging.DEBUG
        logging.basicConfig(
            format = lib.LOGGING_FORMAT, level = logging_level, filename = logfile
        )

        # Init database handler.
        lib.DB.path = db_path
        # Ensure presence of Plugins table.
        db: lib.DB = lib.DB()
        db.checkout_table("Plugins", "(name text primary key, syntax text, description text)")
        db.close()

        # Init own Zulip client.
        self.client = _RootClient(config_file = zuliprc)

        # Init the event queue.
        self.event_queue: "Queue[Event]" = Queue(maxsize=self.QUEUE_LIMIT_SIZE)

        # Register exit handler.
        atexit.register(self.exit_handler)
        signal.signal(signal.SIGTERM, self.sigterm_handler)
        signal.signal(signal.SIGUSR1, self.sig_restart_handler)

        # Start central worker for distributing events.
        self._worker: Thread = Thread(target=self.run, name="_root", daemon=True)
        logging.debug("start central queue")
        self._worker.start()

        # Get the plugin classes.
        plugin_classes: Iterable[Type[_Plugin]] = lib.get_classes_from_path(
            "tumcsbot.plugins", _Plugin # type: ignore
        )

        self.start_plugins(plugin_classes, zuliprc, logging_level)

        # Get events to listen for.
        self.events = get_zulip_events_from_plugins(plugin_classes)
        # Init the Zulip event listener.
        self._event_listener: _ZulipEventListener = _ZulipEventListener(
            zuliprc, self.events, self.event_queue
        )
        # Start the Zulip event listener.
        logging.debug('start event listener, listening on events: %s', str(self.events))
        self._event_listener.start()

    def exit_handler(self) -> None:
        """Terminate all attached threads and processes.

        Needs to be idempotent.
        """
        logging.debug('try exit')

        for plugin_name, plugin in self.plugins.items():
            if not plugin.is_alive():
                continue
            logging.debug("stop plugin %s ...", plugin_name)
            plugin.push_event(Event.stop_event("_root", plugin_name))
            plugin.join()

    def run(self) -> None:
        """Run the central event queue."""
        # This queue does not only get the events from the event
        # listener, but also loopback data from the plugins.
        while True:
            event: Event = self.event_queue.get()
            logging.debug('received event %s', str(event))

            if event.type == EventType.ZULIP:
                if event.data["type"] == "heartbeat":
                    continue
                try:
                    event.data = self.zulip_event_preprocess(event.data)
                except Exception as e:
                    logging.exception(e)
                    continue

            if event.dest is not None:
                if event.dest in self.plugins:
                    self.plugins[event.dest].push_event(event)
                else:
                    logging.error("event.dest unknown: %s", event.dest)
                    continue
            else:
                for plugin in self.plugins.values():
                    plugin.push_event(event)

    def sigterm_handler(self, *_: Any) -> None:
        raise SystemExit()

    def sig_restart_handler(self, *_: Any) -> None:
        self.restart = True
        raise SystemExit()

    def start_plugins(
        self,
        plugin_classes: Iterable[Type[_Plugin]],
        zuliprc: str,
        logging_level: int
    ) -> None:
        """Start the plugin threads / processes."""
        # Create global client lock for the plugins.
        global_client_lock: Lock = Lock()
        # First, build the correct order using the dependency information.
        plugin_class_dict: Dict[str, Type[_Plugin]] = {
            cast(str, plugin_class.plugin_name): plugin_class
            for plugin_class in plugin_classes
        }
        plugin_graph: Dict[str, Set[str]] = {
            cast(str, plugin_class.plugin_name): set(plugin_class.dependencies)
            for plugin_class in plugin_classes
        }
        for plugin_name in TopologicalSorter(plugin_graph).static_order():
            logging.debug("start %s", plugin_name)
            plugin: _Plugin = plugin_class_dict[plugin_name](
                self.client,
                PluginContext(zuliprc, self.event_queue.put, logging_level, global_client_lock)
            )
            if plugin_name in self.plugins:
                raise ValueError(f"plugin {plugin.plugin_name} appears twice")
            self.plugins[plugin_name] = plugin
            plugin.start()

    def zulip_event_preprocess(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess a Zulip event dictionary.

        Check if the event could be an interactive command (to be
        handled by a CommandPlugin instance).

        Check if one of the following requirements are met by the event:
          - It is a private message to the bot.
          - It is a message starting with mentioning the bot.
        The sender of the message must not be the bot itself.

        If this event may be a command, add two new fields to the
        message dict:
          command_name     The name of the command.
          command          The command without the name.
        """
        startswithping: bool = False

        if (event['type'] == 'message'
                and event['message']['content'].startswith(self.client.ping)):
            startswithping = True

        if (event['type'] != 'message'
                or event['message']['sender_id'] == self.client.id
                or (event['message']['type'] != 'private' and not startswithping)
                or (event['message']['type'] == 'private' and (
                    startswithping or not self.client.is_only_pm_recipient(event['message'])
                ))):
            return event

        content: str
        message: Dict[str, Any] = event['message']

        if startswithping:
            content = message['content'][self.client.ping_len:]
        else:
            content = message['content']

        cmd: List[str] = content.split(maxsplit = 1)
        logging.debug('received command line %s', str(cmd))

        event['message'].update(
            command_name = cmd[0] if len(cmd) > 0 else '',
            command = cmd[1] if len(cmd) > 1 else ''
        )

        return event
