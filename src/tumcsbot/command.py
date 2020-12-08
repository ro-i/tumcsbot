#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from zulip import Client


class Command(ABC):
    name: str
    syntax: str
    description: str

    @abstractmethod
    def __init__(self, **kwargs: Any) -> None:
        self._pattern: typing.Pattern[str]
        pass

    @abstractmethod
    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        '''
        Process request and return a tuple containing the type of the
        response (cf. Response) and the response request itself.
        '''
        pass

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

    def is_responsible(self, message: Dict[str, Any]) -> bool:
        return self._pattern.fullmatch(message['content']) is not None

