#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re

from inspect import cleandoc
from typing import Any, Dict, Match, Optional, Pattern, Tuple

import tumcsbot.lib as lib
import tumcsbot.command as command

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'subscribe'
    syntax: str = 'subscribe\\n<stream_name1>\\n<stream_name2[\\ndescription]'
    description: str = cleandoc(
        """
        Subscribe all subscribers of `stream_name1` to `stream_name2`.
        If `stream_name2` does not exist yet, create it with the \
        optional description.
        The stream names may be of the form `#<stream_name>` or \
        `#**<stream_name>**` (autocompleted stream name).
        [administrator rights needed]
        """
    )
    err_msg: str = cleandoc(
        '''
        Hi {}!
        There was an error, I could not execute your command successfully.
        Most likely, I do not have sufficient permissions in order to access \
        one of the streams.
        '''
    )

    def __init__(self, **kwargs: Any) -> None:
        self._pattern: Pattern[str] = re.compile(
            ' *subscribe *\n#{0}({1}){0} *\n#{0}({1}){0} *(\n.+)?'.format(
                lib.Regex.OPT_ASTERISKS, lib.Regex.STREAM
            ), re.I
        )

    def err(self, message: Dict[str, Any]) -> Tuple[lib.MessageType, Dict[str, Any]]:
        return lib.Response.build_message(
            message, type(self).err_msg.format(message['sender_full_name'])
        )

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[lib.MessageType, Dict[str, Any]]:
        if not client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return lib.Response.admin_err(message)

        match: Optional[Match[Any]] = self._pattern.match(
            message['command']
        )
        if match is None:
            return lib.Response.command_not_found(message)

        (from_stream, to_stream, description) = match.groups()
        if description is None:
            description = ''

        subs: Dict[str, Any] = client.get_subscribers(stream = from_stream)

        if subs['result'] != 'success':
            return self.err(message)

        subs_len: int = len(subs['subscribers'])

        # Only subscribe max. 500 users at once
        for i in range(0, subs_len, 500):
            result: Dict[str, Any] = client.add_subscriptions(
                streams = [{'name': to_stream, 'description': description}],
                principals = subs['subscribers'][i:i + 500]
            )
            # (a too large index will be automatically reduced to len())

            if result['result'] != 'success':
                return self.err(message)

        return lib.Response.ok(message)
