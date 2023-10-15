#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""TUM CS Bot - a generic Zulip bot.

This bot is currently especially intended for administrative tasks.
It supports several commands which can be written to the bot using
a private message or a message starting with @mentioning the bot.
"""

import logging
import signal
from graphlib import TopologicalSorter
from multiprocessing import SimpleQueue as SimpleQueueM
from queue import SimpleQueue as SimpleQueueT
from threading import Thread, current_thread
from typing import Any, Callable, Iterable, Type, cast

from tumcsbot import lib
from tumcsbot.client import Client, SharedClient
from tumcsbot.plugin import (
    Event,
    _Plugin,
    EventType,
    PluginContext,
    PluginProcess,
    get_zulip_events_from_plugins,
)


class _QueueForwarder(Thread):
    """Forward contents of one queue to another.

    Used to connect a multiprocessing queue to a regular queue.
    """

    def __init__(self, src: "SimpleQueueM[Event]", dest: "SimpleQueueT[Event]") -> None:
        super().__init__(name="queue_forwarder", daemon=True)
        self.src: "SimpleQueueM[Event]" = src
        self.dest: "SimpleQueueT[Event]" = dest

    def run(self) -> None:
        while True:
            event: Event = self.src.get()
            self.dest.put(event)


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
            "PublicStreams",
            "(StreamName text primary key, Subscribed integer not null)",
        )
        # Get previous data.
        old_streams: dict[str, int] = dict(
            cast(
                Iterable[tuple[str, int]],
                self._db.execute("select StreamName, Subscribed from PublicStreams"),
            )
        )
        # Clear table to prevent deprecated information.
        self._db.execute("delete from PublicStreams")

        # Fill in current data.
        stream_names: list[str] = self.get_public_stream_names(use_db=False)
        for stream_name in stream_names:
            subscribed: bool = False
            # We do not compare the streams using lib.stream_names_equal here,
            # because we store the stream names in the database as we receive
            # them from Zulip. There is no user interaction involved.
            if stream_name in old_streams and old_streams[stream_name] == 1:
                subscribed = True
            self._db.execute(
                "insert or ignore into PublicStreams values (?, ?)",
                stream_name,
                subscribed,
                commit=True,
            )


class _ZulipEventListener(Thread):
    """Handle incoming events from the Zulip server.

    Arguments:
        zuliprc    The zuliprc of the bot.
        events     A list of events (strings) to listen for.
        queue      The queue to push the preprocessed events to.
    """

    def __init__(
        self, zuliprc: str, events: list[str], queue: "SimpleQueueT[Event]"
    ) -> None:
        super().__init__(name="zulip_event_listener", daemon=True)
        self.events: list[str] = events
        self.queue: "SimpleQueueT[Event]" = queue
        # Init own Zulip client.
        self.client: Client = Client(config_file=zuliprc)

    def run(self) -> None:
        self.client.call_on_each_event(
            lambda event: self.queue.put(
                Event(sender="_root", type=EventType.ZULIP, data=event)
            ),
            event_types=self.events,
            all_public_streams=True,
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

    def __init__(
        self,
        zuliprc: str,
        db_path: str,
        debug: bool = False,
        logfile: str | None = None,
    ) -> None:
        self.events: list[str]
        self.plugins: dict[str, _Plugin] = {}
        self.plugins_stopped: dict[str, _Plugin] = {}
        self.restart: bool = False
        self.stopped: bool = False

        # Init logging.
        logging_level: int = logging.WARNING
        if debug:
            logging_level = logging.DEBUG
        logging.basicConfig(
            format=lib.LOGGING_FORMAT, level=logging_level, filename=logfile
        )

        # Init database handler.
        lib.DB.path = db_path
        # Ensure presence of Plugins table.
        db: lib.DB = lib.DB()
        db.checkout_table(
            "Plugins", "(name text primary key, syntax text, description text)"
        )
        db.close()

        # Init own Zulip client which also inits the global DB tables for all
        # Zulip client objects.
        self.client = _RootClient(config_file=zuliprc)
        # Init Zulip client to be (potentially) shared between plugins.
        self.shared_client = SharedClient(config_file=zuliprc)

        # Init the event queue. It is not a multiprocessing queue because the
        # communication with the process plugins goes over their queues and a
        # separate loopback queue. The loopback queue for the thread plugins
        # simply is the central event queue.
        # In order to deliver the events from the process loopback queue to the
        # central event queue, too, we additionally need a small worker thread.
        self.event_queue: "SimpleQueueT[Event]" = SimpleQueueT()
        self.process_loopback_queue: "SimpleQueueM[Event]" = SimpleQueueM()
        self._queue_delivery_worker: _QueueForwarder = _QueueForwarder(
            self.process_loopback_queue, self.event_queue
        )
        logging.debug("start queue forward worker")
        self._queue_delivery_worker.start()

        # Cleanup properly on SIGTERM and SIGINT.
        signal.signal(signal.SIGTERM, self.sigterm_handler)
        signal.signal(signal.SIGINT, self.sigterm_handler)

        # Rename main thread.
        current_thread().name = "_root"

        # Get the plugin classes and start the plugins in correct dependency order.
        plugin_classes: Iterable[Type[_Plugin]] = lib.get_classes_from_path(
            "tumcsbot.plugins", _Plugin  # type: ignore
        )
        self.start_plugins(plugin_classes, zuliprc, logging_level)

        # Get events to listen for.
        self.events = get_zulip_events_from_plugins(plugin_classes)
        # Init the Zulip event listener.
        self._event_listener: _ZulipEventListener = _ZulipEventListener(
            zuliprc, self.events, self.event_queue
        )
        # Start the Zulip event listener.
        logging.debug("start event listener, listening on events: %s", str(self.events))
        self._event_listener.start()

    def distribute_event(self, event: Event) -> None:
        """Distribute a given event to the appropriate plugins."""
        if event.dest is not None:
            # We need special handling for the start/stop events because
            # they operate on the thread/process workers.
            if event.dest in self.plugins:
                if event.type == EventType.STOP:
                    self.stop_plugin(event.dest)
                else:
                    self.plugins[event.dest].push_event(event)
            elif event.dest in self.plugins_stopped:
                if event.type == EventType.START:
                    self.restart_plugin(event.dest)
                else:
                    logging.warning(
                        "non-start event ignored for stopped plugin: %s", event.dest
                    )
            else:
                logging.error("event.dest unknown: %s", event.dest)
        else:
            for plugin in self.plugins.values():
                plugin.push_event(event)

    def exit_handler(self) -> None:
        """Stop the main loop if necessary."""
        logging.debug("exit handler")

        if not self.stopped:
            self.stopped = True
            self.event_queue.put(Event._empty_event("", ""))

    def restart_plugin(self, name: str) -> None:
        """Restart a plugin given its name."""
        logging.debug("restart plugin %s ...", name)
        plugin: _Plugin = self.plugins_stopped[name]
        plugin.start()
        self.plugins[name] = plugin
        del self.plugins_stopped[name]

    def run(self) -> None:
        """Run the central event queue.

        This queue does not only get the events from the event listener,
        but also loopback data from the plugins.
        """
        logging.debug("start central queue")

        while True:
            event: Event = self.event_queue.get()
            logging.debug("received event %s", str(event))

            if self.stopped or event.type == EventType._EMPTY:
                if event.type == EventType._EMPTY and event.sender == "restart":
                    self.restart = True
                self.stopped = True
                break

            if event.type == EventType.ZULIP:
                if event.data["type"] == "heartbeat":
                    continue
                try:
                    event.data = self.zulip_event_preprocess(event.data)
                except Exception as exc:
                    logging.exception(exc)

            self.distribute_event(event)

        logging.debug("stopping plugins ...")
        for plugin_name in self.plugins:
            self.stop_plugin(plugin_name, update_plugins_dicts=False)

    def sigterm_handler(self, *_: Any) -> None:
        self.exit_handler()

    def start_plugins(
        self, plugin_classes: Iterable[Type[_Plugin]], zuliprc: str, logging_level: int
    ) -> None:
        """Start the plugin threads / processes."""
        # First, build the correct order using the dependency information.
        plugin_class_dict: dict[str, Type[_Plugin]] = {
            plugin_class.plugin_name(): plugin_class for plugin_class in plugin_classes
        }
        plugin_graph: dict[str, set[str]] = {
            plugin_class.plugin_name(): set(plugin_class.dependencies)
            for plugin_class in plugin_classes
        }
        for plugin_name in TopologicalSorter(plugin_graph).static_order():
            logging.debug("start %s", plugin_name)
            plugin_class = plugin_class_dict[plugin_name]

            push_loopback: Callable[[Event], None]
            if issubclass(plugin_class, PluginProcess):
                push_loopback = self.process_loopback_queue.put
            else:
                push_loopback = self.event_queue.put

            client: SharedClient | None = None
            if not plugin_class.need_exclusive_client:
                client = self.shared_client

            plugin: _Plugin = plugin_class(
                plugin_context=PluginContext(zuliprc, push_loopback, logging_level),
                client=client,
            )
            if plugin_name in self.plugins:
                raise ValueError(f"plugin {plugin.plugin_name()} appears twice")
            self.plugins[plugin_name] = plugin
            plugin.start()

    def stop_plugin(self, name: str, update_plugins_dicts: bool = True) -> None:
        """Stop a plugin given its name."""
        logging.debug("stop plugin %s ...", name)
        plugin: _Plugin = self.plugins[name]
        plugin.stop()
        plugin.join()
        if not update_plugins_dicts:
            return
        self.plugins_stopped[name] = plugin
        del self.plugins[name]

    def zulip_event_preprocess(self, event: dict[str, Any]) -> dict[str, Any]:
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

        if event["type"] == "message" and event["message"]["content"].startswith(
            self.client.ping
        ):
            startswithping = True

        if (
            event["type"] != "message"
            or event["message"]["sender_id"] == self.client.id
            or (event["message"]["type"] != "private" and not startswithping)
            or (
                event["message"]["type"] == "private"
                and (
                    startswithping
                    or not self.client.is_only_pm_recipient(event["message"])
                )
            )
        ):
            return event

        content: str
        message: dict[str, Any] = event["message"]

        if startswithping:
            content = message["content"][self.client.ping_len :]
        else:
            content = message["content"]

        cmd: list[str] = content.split(maxsplit=1)
        logging.debug("received command line %s", str(cmd))

        event["message"].update(
            command_name=cmd[0] if len(cmd) > 0 else "",
            command=cmd[1] if len(cmd) > 1 else "",
        )

        return event
