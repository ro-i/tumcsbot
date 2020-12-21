#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re

from typing import Any, Dict, List, Pattern, Tuple, Union

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'self_stats'
    syntax: str = 'self_stats'
    description: str = 'Get some statistics about the usage of this bot.'

    def __init__(self, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile(r'\s*self_stats\s*', re.I)
        self._db: lib.DB = lib.DB()

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, List[lib.Response]]:
        result: List[Tuple[Any, ...]] = self._db.execute('select * from SelfStats;')
        response: str = 'Command | Count | Since\n---- | ---- | ----'
        for (cmd, count, since) in result:
            response += '\n{} | {} | {}'.format(
                cmd, count, since
            )
        return lib.Response.build_message(message, response)
