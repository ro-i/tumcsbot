#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing

from typing import Any, Dict, Tuple
from zulip import Client

import tumcsbot.lib as lib


class Command(lib.Command):
    syntax: str = 'source'
    description: str = 'post the link to the repository of my source code'

    def __init__(self, me: bool = False, **kwargs):
        self._pattern: re.Pattern = re.compile('\s*source\s*', re.I)

    @property
    def pattern(self):
        return self._pattern

    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        return lib.build_message(message, 'https://github.com/ro-i/tumcsbot')

