#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Define (partially abstract) base classes for commands (plugins).

Classes:
--------
Command              The most general base classm, suitable for any
                     command (= plugin).
CommandInteractive   Base class specifically intended for interactive
                     commands.
"""

import logging

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Pattern, Tuple, Union

from tumcsbot.client import Client
from tumcsbot.lib import MessageType, Response


class Command(ABC):
    """Generic command (plugin) base class."""

    name: str
    # Zulip events to listen to, see https://zulip.com/api/get-events
    events: List[str]

    @abstractmethod
    def __init__(self, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def func(
        self,
        client: Client,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, List[Response]]:
        """Do the work this command is designed for. (abstract method)

        Process the given event and return a tuple containing the type
        of the response (see lib.MessageType) and the response itself.
        """
        pass

    def is_responsible(
        self,
        client: Client,
        event: Dict[str, Any]
    ) -> bool:
        """Check if this command is responsible for the given event.

        Provide a minimal default implementation for such a
        responsibility check.
        """
        logging.debug('Command.is_responsible: ' + str(event))
        return event['type'] in type(self).events


class CommandInteractive(Command):
    """Base class for interactive commands."""

    syntax: str
    description: str
    events: List[str] = ['message']

    @abstractmethod
    def __init__(self, **kwargs: Any) -> None:
        self._pattern: Pattern[str]
        pass

    @abstractmethod
    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, List[Response]]:
        """Handle preprocessed message and do the actual work.

        This is an abstract method.
        """
        pass

    def func(
        self,
        client: Client,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, List[Response]]:
        """Process message.

        Turn the given message event into a message object and call
        the "handle_message" method of the implementing class.
        """
        return self.handle_message(client, event['message'], **kwargs)

    def get_usage(self) -> Tuple[str, str]:
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
        return (type(self).syntax, type(self).description)

    def is_responsible(
        self,
        client: Client,
        event: Dict[str, Any]
    ) -> bool:
        """Check for responsibility.

        Check if the event is a message and if the implementing class
        is responsible for handling this message.
        """
        return (
            super().is_responsible(client, event) # ensure it's a message event
            and event['message']['interactive'] # see tumcsbot message_preprocess()
            and self._pattern.fullmatch(event['message']['command']) is not None
        )
