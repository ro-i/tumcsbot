#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""TUM CS Bot - a generic Zulip bot.

This bot is currently especially intended for administrative tasks.
It supports several commands which can be written to the bot using
a private message or a message starting with @mentioning the bot.
"""

import atexit
import concurrent.futures
import logging
import signal

from typing import cast, Any, Dict, Iterable, List, Optional, Tuple, Type

import tumcsbot.lib as lib
# This import is necessary.
import tumcsbot.plugins

from tumcsbot.client import Client
from tumcsbot.plugin import PluginContext, CommandPlugin, Plugin, SubBotPlugin, \
    get_events_from_plugins
from tumcsbot.plugin_manager import PluginManager


class RootClient(Client):
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
            if stream_name in old_streams and old_streams[stream_name] == 1:
                subscribed = True
            self._db.execute(
                'insert or ignore into PublicStreams values (?, ?)', stream_name, subscribed,
                commit = True
            )


class TumCSBot:
    """Main Bot class.

    Use run() to run the bot.

    Arguments:
    ----------
    zuliprc       zuliprc file containing the bot's configuration
    db_path       path to the bot's database
    max_workers   maximum number of threads to use to run the plugins
                  (default: 8)
    debug         debugging mode switch
    logfile       use LOGFILE for logging output
    """
    def __init__(
        self,
        zuliprc: str,
        db_path: str,
        max_workers: int = 8,
        debug: bool = False,
        logfile: Optional[str] = None,
        **kwargs: str
    ) -> None:
        self.executor: concurrent.futures.ThreadPoolExecutor
        self.restart: bool = False

        if max_workers < 1:
            raise ValueError('max_workers must be >= 1')

        # Init logging.
        logging_level: int = logging.WARNING
        if debug:
            logging_level = logging.DEBUG
        logging.basicConfig(
            format = lib.LOGGING_FORMAT,
            level = logging_level, filename = logfile
        )

        # Init database handler.
        lib.DB.path = db_path

        # Init own Zulip client.
        self.client: RootClient = RootClient(config_file = zuliprc)

        # Init plugin context.
        plugin_context: PluginContext = PluginContext(
            client = Client(config_file = zuliprc), zuliprc = zuliprc,
            command_plugin_classes = CommandPlugin.get_implementing_classes()
        )

        # Get the subbots ...
        self.subbots: List[SubBotPlugin] = [
            subbot(plugin_context = plugin_context)
            for subbot in SubBotPlugin.get_implementing_classes()
        ]
        # ... and start them.
        for subbot in self.subbots:
            subbot.start()

        # Get the other plugin classes.
        plugin_classes: List[Type[Plugin]] = (
            Plugin.get_implementing_classes()
            + cast(List[Type[Plugin]], CommandPlugin.get_implementing_classes())
        )
        # Register events to listen for.
        self.events: List[str] = get_events_from_plugins(plugin_classes)
        # Instantiate thread-local data object.
        self.plugin_manager: PluginManager = PluginManager(plugin_classes)

        # Start the plugin executor thread pool.
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers = max_workers, thread_name_prefix = 'plugin_manager',
            initializer = PluginManager.instantiate,
            initargs = (self.plugin_manager, plugin_context)
        )

        # Register exit handler.
        atexit.register(self.exit_handler)
        signal.signal(signal.SIGTERM, self.sigterm_handler)
        signal.signal(signal.SIGUSR1, self.sig_restart_handler)

    def _event_callback(
        self,
        event: Dict[str, Any]
    ) -> None:
        """Process one event."""
        self.executor.submit(self.plugin_manager.event_callback, event = event)

    def exit_handler(self) -> None:
        """Terminate all attached threads and processes.

        Needs to be idempotent.
        """
        logging.debug('try exit')

        self.executor.shutdown(wait = True)

        for subbot in self.subbots:
            if not subbot.is_alive():
                return
            logging.debug('shutdown %s', str(subbot.plugin_name))
            subbot.terminate()
            subbot.join()

    def run(self) -> None:
        """Run the bot."""
        logging.debug('listening on events: %s', str(self.events))

        self.client.call_on_each_event(
            self._event_callback,
            event_types = self.events,
            all_public_streams = True
        )

    def sigterm_handler(self, signum: int, frame: Any) -> None:
        raise SystemExit()

    def sig_restart_handler(self, signum: int, frame: Any) -> None:
        self.restart = True
        raise SystemExit()
