#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing

from typing import Any, Dict, Tuple
from zulip import Client

import tumcsbot.lib as lib


class Command(lib.Command):
    syntax: str = 'help'
    description: str = 'post this help as private message'

    def __init__(self, **kwargs):
        self._pattern: re.Pattern = re.compile('\s*help\s*', re.I)

    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        return lib.build_message(
            message,
            lib.Helper.get_help(user = message['sender_full_name']),
            type = 'private',
            to = message['sender_email']
        )

