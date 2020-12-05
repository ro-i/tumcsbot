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
    syntax: str = 'exercise_statement'
    description: str = (
        'remind someone politely to read the exercise statement carefully'
    )
    msg_template: str = (
        'Hi, I take the liberty of sneaking in here to remind you that there '
        'is a (hopefully) really good exercise instruction. Presumably, the '
        'instructors took great care in formulating this exercise statement, '
        'so it might be worth a look. :wink:\n'
        'If you still have any questions, do not hesitate to ask further! :smile:'
    )

    def __init__(self, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile('\s*exercise_statement\s*', re.I)

    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        # remove requesting message
        client.delete_message(message['id'])
        return lib.build_message(message, Command.msg_template)
