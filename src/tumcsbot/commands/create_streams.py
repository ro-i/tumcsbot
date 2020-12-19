#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re

from typing import Any, Dict, List, Pattern, Tuple

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'create_streams'
    syntax: str = 'create_streams\\n<stream_name>,<stream_description>\\n...'
    description: str = (
        'create a public stream for every (stream,description)-tuple passed to this '
        'command (separated by newline)\n'
        '[administrator rights needed]'
    )

    def __init__(self, **kwargs: Any) -> None:
        self._pattern: Pattern[str] = re.compile(
            r'\s*create_streams\s*.+', re.I | re.DOTALL
        )

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        if not client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return lib.Response.admin_err(message)

        failed: List[Tuple[str, str]] = []

        for line in message['command'].split('\n')[1:]:
            name: str
            description: str = ''

            if line.count(',') > 1:
                failed.append(line)
                continue

            try:
                (name, description) = line.split(',')
            except:
                name = line

            if not name:
                failed.append(line)
                continue

            result: Dict[str, Any] = client.add_subscriptions(
                streams = [{'name': name, 'description': description}]
            )

            if result['result'] != 'success':
                failed.append(line)

        if not failed:
            return lib.Response.ok(message)

        response: str = 'Failed to create the following streams:'
        for line in failed:
            response += '\n' + line

        return lib.Response.build_message(
            message,
            response,
            msg_type = 'private'
        )
