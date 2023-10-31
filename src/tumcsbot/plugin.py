#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Define (partially abstract) base classes for plugins.
Plugins may handle arbitrary events.

Classes:
--------
Event           Represent an event.
PluginContext   All information a plugin may need.
_Plugin         Abstract base class for every plugin.
PluginThread    Base class for plugins that live in a separate thread.
PluginProcess   Base class for plugins that live in a separate process.
PluginCommandMixin   Mixin class tailored for interactive commands.
"""

from ctypes import c_bool
import json
import logging
import multiprocessing
import queue
from abc import ABC, abstractmethod
import signal
from threading import Thread
from typing import Any, Callable, Final, Iterable, Type, cast, final

from tumcsbot.client import Client, SharedClient
from tumcsbot.lib import DB, LOGGING_FORMAT, Response, StrEnum


@final
class EventType(StrEnum):
    GET_USAGE = "get_usage"
    RET_USAGE = "ret_usage"
    RELOAD = "reload"
    START = "start"
    STOP = "stop"
    ZULIP = "zulip"
    _EMPTY = "_empty"


@final
class Event:
    """Represent an event.

    Parameters:
    sender    The sender of the event. If the event requires an answer,
              the sender will also be the recipient of the answer, if
              `reply_to` is not specified.
    type      The type of event. See EventType.
    data      Additional event data.
    dest      The destination of this event. If no destination is
              specified, the event will be broadcasted.
    reply_to  If the event requires an answer, send it to the specified
              entity instead of sending it back to the original sender.
    """

    def __init__(
        self,
        sender: str,
        type: EventType,
        data: Any = None,
        dest: str | None = None,
        reply_to: str | None = None,
    ) -> None:
        self.sender: str = sender
        self.type: EventType = type
        self.data: Any = data
        self.dest: str | None = dest
        self.reply_to: str = reply_to if reply_to is not None else sender

    def __repr__(self) -> str:
        return json.dumps(
            {
                "sender": self.sender,
                "type": self.type,
                "data": str(self.data),
                "dest": self.dest,
                "reply_to": self.reply_to,
            }
        )

    @classmethod
    def _empty_event(cls, sender: str, dest: str) -> "Event":
        return cls(sender, type=EventType._EMPTY, dest=dest)

    @classmethod
    def reload_event(cls, sender: str, dest: str) -> "Event":
        return cls(sender, type=EventType.RELOAD, dest=dest)

    @classmethod
    def start_event(cls, sender: str, dest: str) -> "Event":
        return cls(sender, type=EventType.START, dest=dest)

    @classmethod
    def stop_event(cls, sender: str, dest: str) -> "Event":
        return cls(sender, type=EventType.STOP, dest=dest)


@final
class PluginContext:
    """All information a plugin may need.

    Parameters:
    -------
    zuliprc        The bot's zuliprc in case the plugin need an own
                   client instance.
    push_loopback  Method to push an event to the central event queue of
                   the bot.
    logging_level  The logging level to be used.
    """

    def __init__(
        self,
        zuliprc: str,
        push_loopback: Callable[[Event], None],
        logging_level: Any,
    ) -> None:
        self._zuliprc: Final[str] = zuliprc
        self._push_loopback: Final[Callable[[Event], None]] = push_loopback
        self._logging_level: Final[Any] = logging_level

    @property
    def logging_level(self) -> Any:
        return self._logging_level

    @property
    def push_loopback(self) -> Callable[[Event], None]:
        return self._push_loopback

    @property
    def zuliprc(self) -> str:
        return self._zuliprc


class _Plugin(ABC):
    """Abstract base class for every plugin."""

    # List of plugins which have to be loaded before this plugin.
    dependencies: list[str] = []
    # List of events this plugin is responsible for.
    events: list[EventType] = [EventType.RELOAD, EventType.STOP, EventType.ZULIP]
    # List of Zulip events this plugin is responsible for.
    # See https://zulip.com/api/get-events.
    zulip_events: list[str] = []
    # Update the sql entry of the plugin.
    _update_plugin_sql: Final[str] = "replace into Plugins values (?,?,?)"
    # Whether this plugin needs an own client instance or is ok with a thread-safe
    # shared client instance. Defaults to False for PluginThreads and True for
    # PluginProcesses.
    need_exclusive_client: bool

    def __init__(
        self, plugin_context: PluginContext, client: SharedClient | None = None
    ) -> None:
        """Use _init_plugin for custom init code."""

        # Some declarations.
        self._worker: Thread | multiprocessing.Process | None = None
        self.queue: "queue.SimpleQueue[Event] | multiprocessing.SimpleQueue[Event] | None" = (
            None
        )

        if self.need_exclusive_client != (client is None):
            raise ValueError("wrong client initialization")
        self._client: Client | SharedClient | None = client

        self.plugin_context: PluginContext = plugin_context
        # Get own logger.
        self.logger: logging.Logger = self.create_logger()
        self.logger.handlers[0].setFormatter(fmt=logging.Formatter(LOGGING_FORMAT))
        self.logger.setLevel(plugin_context.logging_level)
        # Set the running flag.
        self.running = multiprocessing.Value(c_bool, False)

        # Initialize database entry for this plugin.
        self._init_db()

    def _init_db(self) -> None:
        db: DB = DB()
        db.execute(self._update_plugin_sql, self.plugin_name(), None, None, commit=True)
        db.close()

    def _init_plugin(self) -> None:
        """Custom plugin initialization code.

        Note that this code is called from the worker thread/process.
        """

    @final
    @classmethod
    def plugin_name(cls) -> str:
        """Do not override!"""
        return cls.__module__.rsplit(".", maxsplit=1)[-1]

    @property
    def client(self) -> Client | SharedClient:
        """Get the client object for this plugin.

        Return either the plugin's own client object or the globally
        shared client object.
        """
        if self._client is None:
            raise ValueError("client attribute is only valid in worker process")
        return self._client

    @abstractmethod
    def clear_queue(self) -> None:
        """Empty/clear the queues of this plugin."""

    @abstractmethod
    def create_logger(self) -> logging.Logger:
        """Create a logger instance suitable for this plugin type."""

    @abstractmethod
    def create_queue(
        self,
    ) -> "queue.SimpleQueue[Event] | multiprocessing.SimpleQueue[Event]":
        """Create a queue instance suitable for this plugin type."""

    @abstractmethod
    def create_worker(self) -> Thread | multiprocessing.Process:
        """Create a new instance for this plugin's thread/process."""

    @abstractmethod
    def handle_zulip_event(self, event: Event) -> Response | Iterable[Response]:
        """Process a Zulip event.

        Process the given event and return a Response or an Iterable
        consisting of Response objects.
        """

    def handle_event(self, event: Event) -> None:
        """Process an event.

        Always call the default implementation of this method if you
        did not receive any custom internal event.
        """
        if event.type == EventType.ZULIP:
            if not self.is_responsible(event):
                return
            responses: Response | Iterable[Response] = self.handle_zulip_event(event)
            self.client.send_responses(responses)
        elif event.type == EventType.RELOAD:
            self.reload()
        elif event.type == EventType.STOP:
            pass

    @final
    def is_alive(self) -> bool:
        """Check whether the plugin is running."""
        if self._worker is None:
            return False
        return self._worker.is_alive()

    def is_responsible(self, event: Event) -> bool:
        """Check if the plugin is responsible for the given Zulip event.

        Provide a minimal default implementation for such a
        responsibility check.
        """
        return event.data["type"] in self.zulip_events

    @final
    def join(self) -> None:
        """Wait for the plugin's thread/process to terminate."""
        if self._worker is not None:
            self._worker.join()

    @final
    def push_event(self, event: Event) -> None:
        if self.queue is None:
            return
        self.queue.put(event)

    @final
    def run(self) -> None:
        """Run the plugin.

        Finish thread-/process-intern initialization and wait for events
        on the main incoming queue and handle them.
        """
        self.logger.debug("init")
        if self._client is None:
            self._client = Client(config_file=self.plugin_context.zuliprc)
        self._init_plugin()

        self.logger.debug("started running")
        assert self.queue is not None

        while self.running.value:  # type: ignore
            event: Event = self.queue.get()

            if event.type == EventType._EMPTY:
                break

            self.logger.debug("received event %s", event)
            try:
                self.handle_event(event)
            except Exception as e:
                self.logger.exception(e)

        self.clear_queue()

        self.logger.debug("stopped running")

    def reload(self) -> None:
        """Reloads the plugin.

        Does only debug logging per default.
        """
        self.logger.debug("reloading")

    @final
    def start(self) -> None:
        """Start the plugin's thread/process."""
        if self.running.value:  # type: ignore
            self.logger.error("start failed; plugin already running")
            return

        self.running.value = True  # type: ignore
        self.queue = self.create_queue()
        self._worker = self.create_worker()
        self._worker.start()

    def stop(self) -> None:
        """Tear the plugin down.

        Note that this does not automatically join the thread/process!
        """
        self.running.value = False  # type: ignore
        self.push_event(Event.stop_event("", ""))


class PluginThread(_Plugin):
    """Base class for plugins that live in a separate thread."""

    need_exclusive_client = False

    @final
    def __init__(
        self, plugin_context: PluginContext, client: SharedClient | None = None
    ) -> None:
        _Plugin.__init__(self, plugin_context, client)

    @final
    def clear_queue(self) -> None:
        def _clear_queue(queue: "queue.SimpleQueue[Event]") -> None:
            while not queue.empty():
                queue.get_nowait()

        _clear_queue(cast("queue.SimpleQueue[Event]", self.queue))

    @final
    def create_logger(self) -> logging.Logger:
        return logging.getLogger()

    @final
    def create_queue(self) -> "queue.SimpleQueue[Event]":
        return queue.SimpleQueue()

    @final
    def create_worker(self) -> Thread:
        # The 'daemon'-Argument ensures that threads get
        # terminated when the parent process terminates.
        return Thread(target=self.run, name=self.plugin_name(), daemon=True)


class PluginProcess(_Plugin):
    """Base class for plugins that live in a separate process."""

    need_exclusive_client = True

    @final
    def __init__(
        self, plugin_context: PluginContext, client: SharedClient | None = None
    ) -> None:
        _Plugin.__init__(self, plugin_context, client)

    @final
    def clear_queue(self) -> None:
        def _clear_queue(queue: "multiprocessing.SimpleQueue[Event]") -> None:
            while not queue.empty():
                queue.get()
            queue.close()

        _clear_queue(cast("multiprocessing.SimpleQueue[Event]", self.queue))

    @final
    def create_logger(self) -> logging.Logger:
        return multiprocessing.log_to_stderr()

    @final
    def create_queue(self) -> "multiprocessing.SimpleQueue[Event]":
        return multiprocessing.SimpleQueue()

    @final
    def create_worker(self) -> multiprocessing.Process:
        def run_wrapper() -> None:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            self.run()

        # The 'daemon'-Argument ensures that subprocesses get
        # terminated when the parent process terminates.
        return multiprocessing.Process(
            target=run_wrapper, name=self.plugin_name(), daemon=True
        )


class PluginCommandMixin(_Plugin):
    """Base class tailored for interactive commands.

    This class is intendet to be inherited form **in addition** one of
    the plugin base classes in this module. (First in order.)
    It provides additional feature for command handling plugins.
    """

    # The usage syntax.
    syntax: str = str(None)
    # The verbose description.
    description: str = str(None)
    # The events this command would like to receive, defaults to
    # messages.
    zulip_events = _Plugin.zulip_events + ["message"]
    events = _Plugin.events + [EventType.GET_USAGE]

    @final
    def _init_db(self) -> None:
        db: DB = DB()
        db.execute(self._update_plugin_sql, *self.get_usage(), commit=True)
        db.close()

    def update_plugin_usage(self) -> None:
        self._init_db()

    @final
    def get_usage(self) -> tuple[str, str, str]:
        """Get own documentation to help users use this command.

        Return a tuple containing:
        - the name of the command,
        - the syntax of the command, and
        - its description.
        Example:
            ('command', 'command [OPTION]... [FILE]...',
            'this command does a lot of interesting stuff...')
        The description may contain Zulip-compatible markdown.
        Newlines in the description will be removed.
        The syntax string is formatted as code (using backticks)
        automatically.
        """
        return (self.plugin_name(), self.syntax, self.description)

    @abstractmethod
    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        """Process message.

        Process the given message and return a Response or an Iterable
        consisting of Response objects.
        """

    def handle_zulip_event(self, event: Event) -> Response | Iterable[Response]:
        """Defaults to assume event to be a message event.

        Overwrite if necessary!
        """
        return self.handle_message(event.data["message"])

    def handle_event(self, event: Event) -> None:
        if event.type == EventType.GET_USAGE:
            self.plugin_context.push_loopback(
                Event(
                    sender=self.plugin_name(),
                    type=EventType.RET_USAGE,
                    data=self.get_usage(),
                    dest=event.reply_to,
                )
            )
        else:
            super().handle_event(event)

    def is_responsible(self, event: Event) -> bool:
        """A default implementation for command plugins.

        May need to be overriden to meet more enhanced requirements.
        """
        return (
            super().is_responsible(event)
            and "message" in event.data
            and "command_name" in event.data["message"]
            and event.data["message"]["command_name"] == self.plugin_name()
        )


def get_zulip_events_from_plugins(
    plugins: Iterable[_Plugin] | Iterable[Type[_Plugin]],
) -> list[str]:
    """Get all Zulip events to listen to from the plugins.

    Every plugin decides on its own which events it likes to receive.
    The plugins passed to this function may be classes or instances.
    """
    events: set[str] = set()
    for plugin in plugins:
        events.update(plugin.zulip_events)
    return list(events)
