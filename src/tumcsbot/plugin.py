#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Define (partially abstract) base classes for plugins.
Plugins may handle arbitrary events.

Classes:
--------
PluginContect   All information a plugin may need.
Plugin          Base class for non-specialized general-purpose plugins.
CommandPlugin   Subclass of Plugin.
                A command plugin is specialized to handle textual
                commands sent by the user to the bot.
SubBotPlugin    Subclass of Plugin.
                A subbot is a plugin that lives in its own process and
                has its own event queue.
"""

import logging
import multiprocessing

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Set, Tuple, Type, TypeVar, Union
from uuid import uuid4

from tumcsbot.client import Client
from tumcsbot.lib import LOGGING_FORMAT, Response


PluginType = TypeVar('PluginType', bound = 'Plugin')


class PluginContext:
    """All information a plugin may need.

    Fields:
    -------
    client       A reference to the bot-wide client instance.
    zuliprc      The zuliprc needed to instantiate an own client
                 instance.
    command_plugin_classes
                 A list of currently active CommandPlugin classes.
    """
    def __init__(
        self,
        client: Client,
        zuliprc: str,
        command_plugin_classes: List[Type['CommandPlugin']],
        **kwargs: Any
    ) -> None:
        self.client: Client = client
        self.zuliprc: str = zuliprc
        self.command_plugin_classes: List[Type['CommandPlugin']] = command_plugin_classes


class Plugin(ABC):
    """Abstract base class for every plugin."""

    # To facilitate debugging.
    plugin_name: str = str(uuid4())
    # Zulip events this plugin is responsible for.
    # See https://zulip.com/api/get-events.
    events: List[str] = []

    def __init__(self, plugin_context: PluginContext, **kwargs: Any) -> None:
        # Get own client reference by default.
        self.client: Client = plugin_context.client

    @classmethod
    def get_implementing_classes(cls: Type[PluginType]) -> List[Type[PluginType]]:
        """Get all known implementing classes."""
        # Exclude the other plugin base classes.
        return [
            sub for sub in cls.__subclasses__()
            if sub not in [CommandPlugin, SubBotPlugin]
        ]

    def event_callback(self, event: Dict[str, Any]) -> None:
        """Process one event."""
        try:
            if self.is_responsible(event):
                self.client.send_responses(self.handle_event(event))
        except Exception as e:
            logging.exception(e)
            if event['type'] == 'message':
                try:
                    self.client.send_responses(Response.exception(event['message']))
                except Exception as e2:
                    logging.exception(e2)

    @abstractmethod
    def handle_event(
        self,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        """Process event.

        Process the given event and return a Response or an Iterable
        consisting of Response objects.
        """

    def is_responsible(self, event: Dict[str, Any]) -> bool:
        """Check if this plugin is responsible for the given event.

        Provide a minimal default implementation for such a
        responsibility check.
        """
        logging.debug('%s is_responsible: %s', self.__module__, str(event))
        return event['type'] in self.events


class CommandPlugin(Plugin):
    """Base class tailored for interactive commands."""

    # The usage syntax.
    syntax: str = str(None)
    # The verbose description.
    description: str = str(None)
    # The events this command would like to receive.
    events = ['message']

    @abstractmethod
    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        """Process message.

        Process the given message and return a Response or an Iterable
        consisting of Response objects.
        """

    def handle_event(
        self,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        """Defaults to assume event to be a message event.

        Overwrite if necessary!
        """
        return self.handle_message(event['message'])

    def is_responsible(
        self,
        event: Dict[str, Any]
    ) -> bool:
        return (
            super().is_responsible(event)
            and 'message' in event
            and 'command_name' in event['message']
            and event['message']['command_name'] == self.plugin_name
        )

    @classmethod
    def get_usage(cls) -> Tuple[str, str]:
        """Get own documentation to help users use this command.

        Return a tuple containing:
        - the syntax of the command
        - its description.
        Example:
            ('command [OPTION]... [FILE]...',
            'this command does a lot of interesting stuff...')
        The description may contain Zulip-compatible markdown.
        Newlines in the description will be removed.
        The syntax string is formatted as code (using backticks)
        automatically.
        """
        return (cls.syntax, cls.description)


class SubBotPlugin(multiprocessing.Process, Plugin):
    """Base class for daemon plugins that live in a separate process.

    SubBots are plugins that live in an own process and have an own
    event queue.
    """

    def __init__(self, plugin_context: PluginContext, **kwargs: Any) -> None:
        # A separate process needs an own client.
        plugin_context.client = Client(config_file = plugin_context.zuliprc)
        Plugin.__init__(self, plugin_context)
        # The 'daemon'-Argument ensures that subprocesses get
        # terminated when the parent process terminates.
        multiprocessing.Process.__init__(
            self, target = self._wait_for_event, daemon = True
        )
        # Get own multiprocessing-aware logger.
        self.logger: logging.Logger = multiprocessing.log_to_stderr()
        self.logger.handlers[0].setFormatter(fmt = logging.Formatter(LOGGING_FORMAT))
        # Maybe specify some additional arguments for the event queue.
        self.event_register_params: Dict[str, Any] = {}

    def _wait_for_event(self) -> None:
        """Wait for an event."""
        self.logger.debug(
            'SubBot %s is listening on events: %s', self.__module__, str(self.events)
        )
        self.client.call_on_each_event(
            self.event_callback,
            event_types = self.events,
            **self.event_register_params
        )


def get_events_from_plugins(
    plugins: Union[List[Plugin], List[Type[Plugin]]]
) -> List[str]:
    """Get all events to listen to from the plugins.

    Every plugin decides on its own which events it likes to
    receive.
    The plugins passed to this function may be classes or instances.
    """
    events: Set[str] = set()

    for plugin in plugins:
        for event in plugin.events:
            events.add(event)

    return list(events)
