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
import multiprocessing

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Pattern, Tuple, Union

from tumcsbot.client import Client
from tumcsbot.lib import Response, send_responses


class Command(ABC):
    """Generic command (plugin) base class.

    Do **not** directly inherit from this class!
    Use one of its subclasses instead.
    """

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
    ) -> Union[Response, Iterable[Response]]:
        """Do the work this command is designed for. (abstract method)

        Process the given event and return a tuple containing the type
        of the response (see lib.MessageType) and the response itself.
        """

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

    def start(self) -> None:
        """Executed after initialization.

        Only for compatibility reasons and maybe future changes.
        """

class CommandDaemon(multiprocessing.Process, Command):
    """Base class for daemon plugins, a separate Process.

    Those plugins have their own process, client and event queue.
    They are a kind of "sub-bot".
    """

    name: str
    # Zulip events to listen to, see https://zulip.com/api/get-events
    events: List[str]

    @abstractmethod
    def __init__(self, zuliprc: str, **kwargs: Any) -> None:
        Command.__init__(self)
        # The 'daemon'-Argument is absolutely necessary, otherwise the
        # processes will not terminate when the bot terminates.
        # (TODO? There may be a better way to do this...)
        multiprocessing.Process.__init__(
            self, target = self.wait_for_event, daemon = True
        )
        # Store client instance.
        self.client: Client = Client(config_file = zuliprc)
        # Get own multiprocessing-aware logger.
        self.logger: logging.Logger = multiprocessing.log_to_stderr()
        # Maybe specify some additional arguments for the event queue.
        self.event_register_params: Dict[str, Any] = {}

    def wait_for_event(self) -> None:
        """Wait for an event."""
        self.logger.debug('Command {} is listening on events: {}'.format(
            type(self).name, str(type(self).events)
        ))
        self.client.call_on_each_event(
            lambda event: self.event_callback(event),
            event_types = type(self).events,
            **self.event_register_params
        )

    def event_callback(self, event: Dict[str, Any]) -> None:
        self.logger.debug('Command {} received event: {}'.format(
            type(self).name, str(event)
        ))

        try:
            if self.is_responsible(self.client, event):
                send_responses(self.client, self.func(self.client, event))
        except Exception as e:
            logging.exception(e)


class CommandOneShot(Command):
    """Base class for one-shot commands.

    They are neither daemon nor interactive commands.
    """
    @abstractmethod
    def __init__(self, **kwargs: Any) -> None:
        super().__init__()


class CommandInteractive(Command):
    """Base class for interactive commands."""

    syntax: str
    description: str
    events: List[str] = ['message']

    @abstractmethod
    def __init__(self, **kwargs: Any) -> None:
        super().__init__()
        self._pattern: Pattern[str]

    @abstractmethod
    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        """Handle preprocessed message and do the actual work.

        This is an abstract method.
        """

    def func(
        self,
        client: Client,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
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
