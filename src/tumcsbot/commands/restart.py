#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import sys

from typing import Any, Dict, Iterable, List, Pattern, Tuple, Union

import tumcsbot.lib as lib
import tumcsbot.command as command

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'restart'
    syntax: str = 'restart'
    description: str = 'Restart the bot.\n[administrator rights needed]'

    def __init__(self, **kwargs: Any):
        super().__init__()
        self._pattern: Pattern[str] = re.compile(r'\s*restart\s*', re.I)

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, Iterable[lib.Response]]:
        if not client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return lib.Response.admin_err(message)

        # Raises SystemExit which will be catched and handled.
        sys.exit()

        # dead code
        return lib.Response.none()
