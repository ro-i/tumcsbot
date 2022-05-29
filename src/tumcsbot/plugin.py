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

import json
import logging
import multiprocessing
import queue
from abc import ABC, abstractmethod
from functools import wraps as functools_wraps
from threading import Lock, Thread
from typing import (
    Any, Callable, Dict, Final, Iterable, List, Optional, Set, Tuple, Type, Union, cast, final
)

from tumcsbot.client import Client
from tumcsbot.lib import DB, LOGGING_FORMAT, Response, StrEnum


# Own decorator to guarantee correct client access for _Plugin.client.
# See https://wrapt.readthedocs.io/en/latest/examples.html\
# ?highlight=synchronized#thread-synchronization
def synchronize_client(func: Callable[["_Plugin"], Client]) -> Callable[["_Plugin"], Client]:
    @functools_wraps(func)
    def wrapper(plugin_instance: "_Plugin") -> Client:
        if plugin_instance._need_client_lock:
            with plugin_instance.plugin_context.global_client_lock:
                return func(plugin_instance)
        else:
            return func(plugin_instance)
    return wrapper


@final
class EventType(StrEnum):
    GET_USAGE = "get_usage"
    RET_USAGE = "ret_usage"
    RELOAD = "reload"
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
        dest: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> None:
        self.sender: str = sender
        self.type: EventType = type
        self.data: Any = data
        self.dest: Optional[str] = dest
        self.reply_to: str = reply_to if reply_to is not None else sender

    def __repr__(self) -> str:
        return json.dumps({
            "sender": self.sender,
            "type": self.type,
            "data": str(self.data),
            "dest": self.dest,
            "reply_to": self.reply_to
        })

    @classmethod
    def reload_event(cls, sender: str, dest: str) -> "Event":
        return cls(sender, type=EventType.RELOAD, dest=dest)

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
    global_client_lock
                   A thread lock to be used to access the globally
                   shared client instance.
                   Must not be used by PluginProcess plugins!
    """
    def __init__(
        self,
        zuliprc: str,
        push_loopback: Callable[[Event], None],
        logging_level: Any,
        global_client_lock: Lock
    ) -> None:
        self._zuliprc: Final[str] = zuliprc
        self._push_loopback: Final[Callable[[Event], None]] = push_loopback
        self._logging_level: Final[Any] = logging_level
        self._global_client_lock: Final[Lock] = global_client_lock

    @property
    def global_client_lock(self) -> Lock:
        return self._global_client_lock

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
    dependencies: List[str] = []
    # List of events this plugin is responsible for.
    events: List[EventType] = [EventType.RELOAD, EventType.STOP, EventType.ZULIP]
    # List of Zulip events this plugin is responsible for.
    # See https://zulip.com/api/get-events.
    zulip_events: List[str] = []
    # Whether this plugin can be scheduled automatically.
    schedulable: bool = False
    # Limit the size of the incoming queues.
    QUEUE_LIMIT_SIZE: int = 4096
    # Update the sql entry of the plugin.
    _update_plugin_sql: Final[str] = "replace into Plugins values (?,?,?)"

    def __init__(self, client: Client, plugin_context: PluginContext) -> None:
        # Some declarations.
        self._worker: Union[Thread, multiprocessing.Process]
        self.queue: Union["queue.Queue[Event]", "multiprocessing.Queue[Event]"]

        self.plugin_context: PluginContext = plugin_context
        # Get own logger.
        self.logger: logging.Logger = self.create_logger()
        self.logger.handlers[0].setFormatter(fmt = logging.Formatter(LOGGING_FORMAT))
        self.logger.setLevel(plugin_context.logging_level)
        # Set the running flag.
        self.running: bool = True
        # Set the default timeout to block the queue. (default: infinity)
        self.queue_timeout: Optional[float] = None
        # Queue for incoming events.
        self.queue = self.create_queue()
        # Maybe create own client instance in _init_plugin, overwriting this
        # assignment and setting "_need_client_lock" to False.
        self._client: Client = client
        self._need_client_lock: bool = True
        # Initialize database entry for this plugin.
        self._init_db()

    def _init_db(self) -> None:
        db: DB = DB()
        db.execute(self._update_plugin_sql, self.plugin_name, None, None, commit=True)
        db.close()

    def _init_plugin(self) -> None:
        """Custom plugin initialization code."""

    @final
    @classmethod
    @property
    def plugin_name(cls) -> str:
        """Do not override!"""
        return cls.__module__.rsplit('.', maxsplit=1)[-1]

    @final
    @synchronize_client
    def client(self) -> Client:
        """Get the client object for this plugin.

        Return either the plugin's own client object or the globally
        shared client object using the global client lock.
        """
        return self._client

    @abstractmethod
    def clear_queues(self) -> None:
        """Empty/clear the queues of this plugin."""

    @abstractmethod
    def create_logger(self) -> logging.Logger:
        """Create a logger instance suitable for this plugin type."""

    @abstractmethod
    def create_queue(self) -> Union["queue.Queue[Event]", "multiprocessing.Queue[Event]"]:
        """Create a queue instance suitable for this plugin type."""

    @abstractmethod
    def handle_zulip_event(self, event: Event) -> Union[Response, Iterable[Response]]:
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
            responses: Union[Response, Iterable[Response]] = self.handle_zulip_event(event)
            self.client().send_responses(responses)
        elif event.type == EventType.STOP:
            self.stop()
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

        while self.running:
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
        self._worker.start()

    @final
    def stop(self) -> None:
        """Tear the plugin down.

        Do not override!
        """
        self.running = False


class PluginThread(_Plugin):
    """Base class for plugins that live in a separate thread."""

    @final
    def __init__(self, client: Client, plugin_context: PluginContext) -> None:
        _Plugin.__init__(self, client, plugin_context)
        # The 'daemon'-Argument ensures that threads get
        # terminated when the parent process terminates.
        self._worker = Thread(target=self.run, name=self.plugin_name, daemon=True)

    @final
    def clear_queues(self) -> None:
        self.queue.queue.clear()

    @final
    def create_logger(self) -> logging.Logger:
        return logging.getLogger()

    @final
    def create_queue(self) -> Union["queue.Queue[Event]", "multiprocessing.Queue[Event]"]:
        return queue.Queue(maxsize=self.QUEUE_LIMIT_SIZE)


class PluginProcess(_Plugin):
    """Base class for plugins that live in a separate process."""

    @final
    def __init__(self, client: Client, plugin_context: PluginContext) -> None:
        _Plugin.__init__(self, client, plugin_context)
        # We absolutely need an own client instance here.
        # The global client lock is only suitable for threads!
        self._client = Client(config_file=self.plugin_context.zuliprc)
        self._need_client_lock = False
        # The 'daemon'-Argument ensures that subprocesses get
        # terminated when the parent process terminates.
        self._worker = multiprocessing.Process(target=self.run, name=self.plugin_name, daemon=True)

    @final
    def clear_queues(self) -> None:
        def clear_queue(q: "multiprocessing.Queue[Event]") -> None:
            while not q.empty():
                q.get_nowait()
        clear_queue(cast("multiprocessing.Queue[Event]", self.queue))

    @final
    def create_logger(self) -> logging.Logger:
        return multiprocessing.log_to_stderr()

    @final
    def create_queue(self) -> Union["queue.Queue[Event]", "multiprocessing.Queue[Event]"]:
        return multiprocessing.Queue(maxsize=self.QUEUE_LIMIT_SIZE)


class PluginCommand(_Plugin):
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
    # Add "get_usage" the events.
    events = _Plugin.events + [EventType.GET_USAGE]

    @final
    def _init_db(self) -> None:
        db: DB = DB()
        db.execute(self._update_plugin_sql, *self.get_usage(), commit=True)
        db.close()

    @final
    def get_usage(self) -> Tuple[str, str, str]:
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
        return (self.plugin_name, self.syntax, self.description)

    @abstractmethod
    def handle_message(self, message: Dict[str, Any]) -> Union[Response, Iterable[Response]]:
        """Process message.

        Process the given message and return a Response or an Iterable
        consisting of Response objects.
        """

    def handle_zulip_event(self, event: Event) -> Union[Response, Iterable[Response]]:
        """Defaults to assume event to be a message event.

        Overwrite if necessary!
        """
        return self.handle_message(event.data['message'])

    def handle_event(self, event: Event) -> None:
        if event.type == EventType.GET_USAGE:
            self.plugin_context.push_loopback(Event(
                sender=self.plugin_name,
                type=EventType.RET_USAGE,
                data=self.get_usage(),
                dest=event.reply_to
            ))
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
            and event.data["message"]["command_name"] == self.plugin_name
        )


def get_zulip_events_from_plugins(
    plugins: Union[Iterable[_Plugin], Iterable[Type[_Plugin]]]
) -> List[str]:
    """Get all Zulip events to listen to from the plugins.

    Every plugin decides on its own which events it likes to receive.
    The plugins passed to this function may be classes or instances.
    """
    events: Set[str] = set()
    for plugin in plugins:
        events.update(plugin.zulip_events)
    return list(events)
