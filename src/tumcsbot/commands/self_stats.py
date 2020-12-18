#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing

from typing import Any, Dict, List, Pattern, Tuple

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'self_stats'
    syntax: str = 'self_stats'
    description: str = 'get some statistics about the usage of this bot'

    def __init__(self, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile('\s*self_stats\s*', re.I)
        self._db: lib.DB = lib.DB()

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        result: List[Tuple[Any, ...]] = self._db.execute('select * from SelfStats;')
        response: str = 'Command | Count | Since\n---- | ---- | ----'
        for (command, count, since) in result:
            response += '\n{} | {} | {}'.format(
                command, count, since
            )
        return lib.Response.build_message(message, response)
