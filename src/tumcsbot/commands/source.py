#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re

from typing import Any, Dict, Pattern, Tuple

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'source'
    syntax: str = 'source'
    description: str = 'Post the link to the repository of my source code.'

    def __init__(self, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile(r'\s*source\s*', re.I)

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[lib.MessageType, Dict[str, Any]]:
        return lib.Response.build_message(
            message, 'https://github.com/ro-i/tumcsbot'
        )
