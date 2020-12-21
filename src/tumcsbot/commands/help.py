#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re

from typing import Any, Dict, List, Pattern, Tuple, Union

import tumcsbot.lib as lib
import tumcsbot.command as command

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'help'
    syntax: str = 'help'
    description: str = 'Post a help message to the requesting user.'

    def __init__(self, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile(r'\s*help\s*', re.I)

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, List[lib.Response]]:
        return lib.Response.build_message(
            message,
            lib.Helper.get_help(user = message['sender_full_name']),
            msg_type = 'private',
            to = message['sender_email']
        )
