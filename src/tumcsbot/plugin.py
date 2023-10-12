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
PluginCommand   Base class tailored for interactive commands.
"""

from ctypes import c_bool
import json
import logging
import multiprocessing
import queue
from abc import ABC, abstractmethod
from threading import Thread
from typing import Any, Callable, Final, Iterable, Type, cast, final

from tumcsbot.client import Client
from tumcsbot.lib import DB, LOGGING_FORMAT, Response, StrEnum


@final
class EventType(StrEnum):
    GET_USAGE = "get_usage"
    RET_USAGE = "ret_usage"
    RELOAD = "reload"
    START = "start"
    STOP = "stop"
    ZULIP = "zulip"


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
    # Limit the size of the incoming queues.
    QUEUE_LIMIT_SIZE: int = 4096
    # Update the sql entry of the plugin.
    _update_plugin_sql: Final[str] = "replace into Plugins values (?,?,?)"

    def __init__(self, plugin_context: PluginContext) -> None:
        """Use _init_plugin for custom init code."""

        # Some declarations.
        self._worker: Thread | multiprocessing.Process | None = None
        self.queue: "queue.Queue[Event] | multiprocessing.Queue[Event]"

        self.plugin_context: PluginContext = plugin_context
        # Get own logger.
        self.logger: logging.Logger = self.create_logger()
        self.logger.handlers[0].setFormatter(fmt=logging.Formatter(LOGGING_FORMAT))
        self.logger.setLevel(plugin_context.logging_level)
        # Set the running flag.
        self.running = multiprocessing.Value(c_bool, False)
        # Set the default timeout to block the queue. (default: infinity)
        self.queue_timeout: float | None = None
        # Queue for incoming events.
        self.queue = self.create_queue()

        self._client: Client = Client(config_file=plugin_context.zuliprc)

        # Initialize database entry for this plugin.
        self._init_db()

    def _init_db(self) -> None:
        db: DB = DB()
        db.execute(self._update_plugin_sql, self.plugin_name(), None, None, commit=True)
        db.close()

    def _init_plugin(self) -> None:
        """Custom plugin initialization code."""

    @final
    @classmethod
    def plugin_name(cls) -> str:
        """Do not override!"""
        return cls.__module__.rsplit(".", maxsplit=1)[-1]

    @final
    def client(self) -> Client:
        """Get the client object for this plugin.

        Return either the plugin's own client object or the globally
        shared client object.
        """
        return self._client

    @abstractmethod
    def clear_queues(self) -> None:
        """Empty/clear the queues of this plugin."""

    @abstractmethod
    def create_logger(self) -> logging.Logger:
        """Create a logger instance suitable for this plugin type."""

    @abstractmethod
    def create_queue(
        self,
    ) -> "queue.Queue[Event] | multiprocessing.Queue[Event]":
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
            self.client().send_responses(responses)
        elif event.type == EventType.RELOAD:
            self.reload()

    def handle_queue_timeout(self) -> None:
        """What to do on empty queue exception?

        Per default, we reset the timeout and block until data is
        available.
        """
        self.queue_timeout = None

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
        self.queue.put(event)

    @final
    def run(self) -> None:
        """Run the plugin.

        Finish thread-/process-intern initialization and wait for events
        on the main incoming queue and handle them.
        """
        self.logger.debug("init")
        self._init_plugin()

        self.logger.debug("started running")

        while self.running.value:  # type: ignore
            try:
                event: Event = self.queue.get(timeout=self.queue_timeout)
            except queue.Empty:
                self.handle_queue_timeout()
                continue

            self.logger.debug("received event %s", event)
            try:
                self.handle_event(event)
            except Exception as e:
                self.logger.exception(e)

        self.clear_queues()

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
        self._worker = self.create_worker()
        self._worker.start()

    @final
    def stop(self) -> None:
        """Tear the plugin down.

        Do not override!

        Note that this does not automatically join the thread/process!
        """
        self.running.value = False  # type: ignore


class PluginThread(_Plugin):
    """Base class for plugins that live in a separate thread."""

    @final
    def __init__(self, plugin_context: PluginContext) -> None:
        _Plugin.__init__(self, plugin_context)

    @final
    def clear_queues(self) -> None:
        cast("queue.Queue[Event]", self.queue).queue.clear()

    @final
    def create_logger(self) -> logging.Logger:
        return logging.getLogger()

    @final
    def create_queue(self) -> "queue.Queue[Event]":
        return queue.Queue(maxsize=self.QUEUE_LIMIT_SIZE)

    @final
    def create_worker(self) -> Thread:
        # The 'daemon'-Argument ensures that threads get
        # terminated when the parent process terminates.
        return Thread(target=self.run, name=self.plugin_name(), daemon=True)


class PluginProcess(_Plugin):
    """Base class for plugins that live in a separate process."""

    @final
    def __init__(self, plugin_context: PluginContext) -> None:
        _Plugin.__init__(self, plugin_context)

    @final
    def clear_queues(self) -> None:
        def clear_queue(queue: "multiprocessing.Queue[Event]") -> None:
            while not queue.empty():
                queue.get_nowait()

        clear_queue(cast("multiprocessing.Queue[Event]", self.queue))

    @final
    def create_logger(self) -> logging.Logger:
        return multiprocessing.log_to_stderr()

    @final
    def create_queue(self) -> "multiprocessing.Queue[Event]":
        return multiprocessing.Queue(maxsize=self.QUEUE_LIMIT_SIZE)

    @final
    def create_worker(self) -> multiprocessing.Process:
        # The 'daemon'-Argument ensures that subprocesses get
        # terminated when the parent process terminates.
        return multiprocessing.Process(
            target=self.run, name=self.plugin_name(), daemon=True
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
