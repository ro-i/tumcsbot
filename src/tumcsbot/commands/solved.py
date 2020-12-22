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
    solved_emoji_name: str = 'cowboy'
    msg_template: str = (
        '[This answer]({}) has been marked as solution by @_**{}**.'
    )
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
        # try to get the message
        result = client.get_messages({
            'anchor': event['message_id'],
            'num_before': 0,
            'num_after': 0
        })
        # nothing to do if the message could not be received or is private
        if (result['result'] != 'success'
                or result['messages'][0]['type'] == 'private'):
            return lib.Response.none()
        message: Dict[str, Any] = result['messages'][0]

        # try to get the user who reacted on this message
        result = client.get_user_by_id(event['user_id'])
        if result['result'] != 'success':
            return lib.Response.none()
        user_name: str = result['user']['full_name']


        # fix strange behavior of Zulip which does not accept literal periods
        topic: str = urllib.parse.quote(message['subject'], safe = '')\
            .replace('.', '%2E')

        # get host url (removing trailing 'api/')
        base_url: str = client.base_url[:-4]
        # build the full url
        url: str = base_url + Command.path.format(
            message['stream_id'], topic, message['id']
        )

        return lib.Response.build_message(
            None,
            msg_type = 'stream',
            to = message['stream_id'],
            subject = message['subject'],
            content = Command.msg_template.format(url, user_name)
        )
