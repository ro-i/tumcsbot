#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import urllib.parse

from typing import Any, Dict, List, Tuple, Union

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.Command):
    name: str = 'solved'
    events: List[str] = ['reaction']
    solved_emoji_name: str = 'check'
    msg_template: str = (
        '[This answer ↑{}]({}) has been marked as solution by '
    )
    mention_template: str = '@_**{}**'
    # arguments: stream id, topic name, message id
    path: str = '#narrow/stream/{}/topic/{}/near/{}'

    def __init__(self, **kwargs: Any) -> None:
        pass

    def is_responsible(
        self,
        client: Client,
        event: Dict[str, Any]
    ) -> bool:
        return (
            event['type'] in Command.events
            and event['op'] == 'add' # TODO: handle "remove" case?
            and event['emoji_name'] == Command.solved_emoji_name
        )

    def func(
        self,
        client: Client,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, List[lib.Response]]:
        # Try to get the message.
        result = self._get_message(client, event['message_id'])
        if result['result'] != 'success':
            return lib.Response.none()
        if not result['found_anchor']:
            # Try again. Message has been sent before the bot subscribed to
            # the corresponding stream.
            result = self._get_message(client, event['message_id'], True)

        if (result['result'] != 'success'
                or not result['found_anchor']
                or result['messages'][0]['type'] == 'private'):
            return lib.Response.none()

        message: Dict[str, Any] = result['messages'][0]

        # Get the user who reacted on this message.
        result = client.get_user_by_id(event['user_id'])
        if result['result'] != 'success':
            return lib.Response.none()
        user_name: str = result['user']['full_name']

        # Fix strange behavior of Zulip which does not accept literal periods.
        topic: str = urllib.parse.quote(message['subject'], safe = '')\
            .replace('.', '%2E')
        # Get host url (removing trailing 'api/').
        base_url: str = client.base_url[:-4]
        # Build the full url.
        url: str = base_url + Command.path.format(
            message['stream_id'], topic, message['id']
        )

        # Build the message the bot might write.
        bot_message: str = Command.msg_template.format(message['id'], url)

        # Check if there already exists a bot message regarding this message.
        result = self._search_bot_message(client, message)
        if result['result'] != 'success' or len(result['messages']) < 1:
            return lib.Response.build_message(
                None,
                msg_type = 'stream',
                to = message['stream_id'],
                subject = message['subject'],
                content = bot_message + Command.mention_template.format(user_name)
            )

        # Get previous bot message.
        old_bot_message: Dict[str, Any] = result['messages'][0]

        # Reject multiple reactions of the same user.
        if user_name in old_bot_message['content'][len(bot_message) + 4:-2]\
                .split('**, @_**'):
            return lib.Response.none()

        # Add user to the reaction list.
        client.update_message({
            'message_id': old_bot_message['id'],
            'content': (old_bot_message['content'] + ', '
                        + Command.mention_template.format(user_name))
        })

        return lib.Response.none()

    def _get_message(
        self,
        client: Client,
        message_id: int,
        public_streams: bool = False
    ) -> Dict[str, Any]:
        narrow: List[Dict[str, str]] = []

        if public_streams:
            narrow = [{'operator': 'streams', 'operand': 'public'}]

        return client.get_messages({
            'anchor': message_id,
            'num_before': 0,
            'num_after': 0,
            'narrow': narrow
        })

    def _search_bot_message(
        self,
        client: Client,
        message: Dict[str, Any],
    ) -> Dict[str, Any]:
        search: str = '↑{} has been marked as solution by'.format(message['id'])

        result: Dict[str, Any] =  client.get_messages({
            'anchor': message['id'],
            'num_before': 0,
            'num_after': 1,
            'narrow': [
                { 'operator': 'stream', 'operand': message['stream_id'] },
                { 'operator': 'topic', 'operand': message['subject'] },
                { 'operator': 'sender', 'operand': client.id },
                { 'operator': 'has', 'operand': 'link' },
                { 'operator': 'search', 'operand': search }
            ]
        })

        return result
