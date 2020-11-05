#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing

from typing import Any, Dict, Pattern, Tuple
from zulip import Client

import tumcsbot.lib as lib


class Command(lib.Command):
    syntax: str = '[BETA] create_streams\\n<stream_name>,<stream_description>\\n...'
    description: str = (
        'create a stream for every (stream,description)-tuple passed to this '
        'command (separated by newline)'
    )

    def __init__(self, **kwargs: Any) -> None:
        self._pattern: Pattern[str] = re.compile(
            '\s*create_streams\s*', re.I
        )

    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        failed: List[Tuple[str, str]] = []

        for line in message['content'].split('\n')[1:]:
            name: str
            description: str = ''

            try:
                (name, description) = line.split(',')
            except:
                name = line.split(',')

            result: Dict[str, Any] = client.add_subscriptions(
                streams = [{'name': name, 'description': description}]
            )

            if result['result'] != 'success':
                failed.append((name, description))

        if not failed:
            return lib.Response.ok(message)

        response: str = 'Failed to create the following streams:'
        for (name, description) in failed:
            response += '\n{},{}'.format(name, description)
        return lib.build_message(
            message,
            lib.build_message(response),
            type = 'private'
        )
