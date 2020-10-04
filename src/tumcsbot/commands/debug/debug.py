#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing

from typing import Any, Dict
from zulip import Client

import tumcsbot.lib as lib


class Command(lib.BaseCommand):

    def __init__(self, **kwargs):
        self._pattern: re.Pattern = re.compile('\s*debug.*', re.I)

    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        return lib.build_message(message, '```\n{}\n```'.format(str(message)))

