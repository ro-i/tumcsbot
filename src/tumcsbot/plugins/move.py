#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Dict, Iterable, Optional, Union

from tumcsbot.lib import Regex, Response
from tumcsbot.plugin import CommandPlugin


class Move(CommandPlugin):
    plugin_name = 'move'
    syntax = 'move <destination stream>'
    description = cleandoc(
        """
        Move the current topic to `destination stream` and notify the \
        creator of the topic by a private message.
        **Note**: This works only if the bot has access to both streams!
        """
    )
    msg_template: str = (
        'Hi {}, I moved your topic "{}" to stream #**{}** because I think that '
        'it might be more appropriate there :smile:'
    )

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        if 'stream_id' not in message:
            return Response.build_message(message, 'Error: Not a stream topic.')

        # Get destination stream name.
        dest_stream: Optional[str] = Regex.get_stream_name(message['command'])
        if dest_stream is None:
            return Response.command_not_found(message)

        # Get destination stream id.
        result: Dict[str, Any] = self.client.get_stream_id(dest_stream)
        if result['result'] != 'success':
            return Response.error(message)
        dest_stream_id: int = result['stream_id']

        # Get source stream.
        src_stream_id: int = message['stream_id']
        # Get topic.
        topic: str = message['subject']

        # Get message which started the topic.
        request: Dict[str, Any] = {
            'anchor': 'oldest',
            'num_before': 0,
            'num_after': 1,
            'narrow': [
                { 'operator': 'stream', 'operand': src_stream_id },
                { 'operator': 'topic', 'operand': topic }
            ]
        }
        result = self.client.get_messages(request)
        if result['result'] != 'success':
            return Response.error(message)
        first_message: Dict[str, Any] = result['messages'][0]

        # Move message (and all following in the same topic) = move topic.
        request = {
            'message_id': first_message['id'],
            'topic': topic,
            'stream_id': dest_stream_id,
            'send_notification_to_old_thread': False,
            'propagate_mode': 'change_all'
        }
        result = self.client.update_message(request)
        if result['result'] != 'success':
            return Response.error(message)

        # Remove requesting message.
        self.client.delete_message(message['id'])

        return Response.build_message(
            first_message,
            self.msg_template.format(first_message['sender_full_name'], topic, dest_stream),
            msg_type = 'private'
        )
