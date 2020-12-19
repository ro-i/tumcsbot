#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import logging

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Pattern, Tuple

from tumcsbot.client import Client


class Command(ABC):
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
    ) -> Tuple[str, Dict[str, Any]]:
        '''
        Process request and return a tuple containing the type of the
        response (cf. Response) and the response itself.
        '''
        pass

    def is_responsible(
        self,
        client: Client,
        event: Dict[str, Any]
    ) -> bool:
        '''
        Provide a minimal default implementation for a
        responsibility check.
        '''
        logging.debug('Command.is_responsible: ' + str(event))
        return event['type'] in type(self).events


class CommandInteractive(Command):
    '''
    This class is a simple base class for commands triggered by messages.
    '''
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
    ) -> Tuple[str, Dict[str, Any]]:
        '''Handle preprocessed message.'''
        pass

    def func(
        self,
        client: Client,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        '''
        Turn an event into a message object and call the "handle_message"
        method of the implementing class.
        '''
        return self.handle_message(client, event['message'], **kwargs)

    def get_usage(self) -> Tuple[str, str]:
        '''
        Return a tuple containing:
        - the syntax of the command
        - its description.
        Example:
            ('command [OPTION]... [FILE]...',
            'this command does a lot of interesting stuff...')
        The description may contain Zulip-compatible markdown.
        Newlines in the description will be removed.
        The syntax string is formatted as code (using backticks) automatically.
        '''
        return (type(self).syntax, type(self).description)

    def is_responsible(
        self,
        client: Client,
        event: Dict[str, Any]
    ) -> bool:
        return (
            super().is_responsible(client, event) # ensure it's a message event
            and event['message']['interactive'] # see tumcsbot message_preprocess()
            and self._pattern.fullmatch(event['message']['command']) is not None
        )
