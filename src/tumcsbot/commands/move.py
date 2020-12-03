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
    syntax: str = '[Experimental] move <stream>'
    description: str = (
        'move the current topic to "stream" and notify the creator of this '
        'topic by a private message\n'
        '**Note**: This works only if both streams are public!'
    )
    msg_template: str = (
        'Hi, {}, I moved your topic "{}" to stream "{}" because I think that '
        'it might be more appropriate there :smile:'
    )

    def __init__(self, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile(
            '\s*move\s+#{0}{1}{0}\s*'.format(lib.Regex.OPT_ASTERISKS, lib.Regex.STREAM),
            re.I
        )
        self._capture_pattern: Pattern[str] = re.compile(
            '\s*move\s+#{0}({1}){0}\s*'.format(lib.Regex.OPT_ASTERISKS, lib.Regex.STREAM),
            re.I
        )

    def func(
            self,
            client: Client,
            message: Dict[str, Any],
            **kwargs: Any
            ) -> Tuple[str, Dict[str, Any]]:
        request: Dict[str, Any]
        result: Dict[str, Any]

        if 'stream_id' not in message:
            return lib.build_message(message, 'Error: Not a stream topic')
        # remove requesting message
        client.delete_message(message['id'])

        # get destination stream id
        dest_stream: str = self._capture_pattern.match(message['content']).group(1)
        result = client.get_stream_id(dest_stream)
        if result['result'] != 'success':
            return lib.Response.error(message)
        dest_stream_id: int = result['stream_id']
        # get source stream
        src_stream_id: int = message['stream_id']
        # get topic
        topic: str = message['subject']

        # get message which started the topic
        request = {
            'anchor': 'oldest',
            'num_before': 0,
            'num_after': 1,
            'narrow': [
                { 'operator': 'stream', 'operand': src_stream_id },
                { 'operator': 'topic', 'operand': topic }
            ]
        }
        result = client.get_messages(request)
        if result['result'] != 'success':
            return lib.Response.error(message)
        first_message: Dict[str, Any] = result['messages'][0]

        # move message (and all following in the same topic) = move topic
        request = {
            'message_id': first_message['id'],
            'topic': topic,
            'stream_id': dest_stream_id,
            'send_notification_to_old_thread': False,
            'propagate_mode': 'change_all'
        }
        result = client.update_message(request)
        if result['result'] != 'success':
            return lib.Response.error(message)

        return lib.build_message(
            first_message,
            Command.msg_template.format(first_message['sender_full_name'], topic, dest_stream),
            type = 'private'
        )
