#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing

from typing import Any, Dict, Pattern, Tuple

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'source'
    syntax: str = 'source'
    description: str = 'post the link to the repository of my source code'

    def __init__(self, me: bool = False, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile('\s*source\s*', re.I)

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        return lib.Response.build_message(
            message, 'https://github.com/ro-i/tumcsbot'
        )

