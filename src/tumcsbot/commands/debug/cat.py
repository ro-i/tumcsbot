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
        self._pattern: re.Pattern = re.compile(
            '\s*cat\s*' + lib.Regex.FILE + '\s*', re.I
        )

    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        file_path: str = lib.parse_filenames(message['content'])[0]

        content: str = lib.get_file(client, file_path)

        return lib.build_message(message, '```\n{}\n```'.format(content))
