#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing
import urllib.parse

from typing import Any, Dict, Pattern, Tuple
from zulip import Client

import tumcsbot.lib as lib


class Command(lib.Command):
    name: str = 'self_stats'
    syntax: str = '[Experimental] self_stats'
    description: str = 'get some statistics about the usage of this bot'

    def __init__(self, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile('\s*self_stats\s*', re.I)
        self._db: lib.DB = lib.DB()

    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        result: List[Tuple] = self._db.execute('select * from SelfStats;')
        response: str = 'Command | Count | Since\n---- | ---- | ----'
        for (command, count, since) in result:
            response += '\n{} | {} | {}'.format(
                command, count, since
            )
        return lib.build_message(message, response)