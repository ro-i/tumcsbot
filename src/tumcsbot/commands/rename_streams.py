#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing

from typing import Any, Dict, List, Pattern, Tuple
from zulip import Client

import tumcsbot.lib as lib


class Command(lib.Command):
    name: str = 'rename_streams'
    syntax: str = 'rename_streams\\n<stream_name_old>,<stream_name_new>\\n...'
    description: str = (
        'rename stream for every (stream_name_old,stream_name_new)-tuple '
        'passed to this command (separated by newline)\n'
        '[administrator rights needed]'
    )

    def __init__(self, **kwargs: Any) -> None:
        self._pattern: Pattern[str] = re.compile(
            '\s*rename_streams\s*.+', re.I | re.DOTALL
        )

    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        if not client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return lib.Response.admin_err(message)

        failed: List[Tuple[str, str]] = []

        for line in message['content'].split('\n')[1:]:
            name_new: str
            name_old: str

            try:
                (name_old, name_new) = line.split(',')
            except:
                name_old = ''

            if not name_old or not name_new:
                failed.append(line)
                continue

            try:
                id: int = client.get_stream_id(name_old)['stream_id']
            except:
                failed.append(line)
                continue

            result: Dict[str, Any] = client.update_stream(
                {'stream_id': id, 'new_name': '"{}"'.format(name_new)}
            )

            if result['result'] != 'success':
                failed.append(line)

        if not failed:
            return lib.Response.ok(message)

        response: str = 'Failed to perform the following renamings:'
        for line in failed:
            response += '\n' + line

        return lib.build_message(
            message,
            response,
            type = 'private'
        )
