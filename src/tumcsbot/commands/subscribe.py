#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import logging
import re
import typing

from inspect import cleandoc
from typing import Any, Dict, Optional, Pattern, Tuple
from zulip import Client

import tumcsbot.lib as lib


class Command(lib.Command):
    syntax: str = 'subscribe <stream_name1> to <stream_name2 ![description]'
    description: str = (
        'subscribe all subscribers of `stream_name1` to `stream_name2`; if '
        '`stream_name2` does not exist yet, create it with the '
        '(optional) description\n'
        'The stream names may be of the form `#<stream_name>` or '
        '`#**<stream_name>**` (autocompleted stream name).\n'
        '[administrator rights needed]'
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
            '\s*subscribe\s+#{0}{1}{0}\s+to\s+#{0}{1}{0}.*'.format(
                lib.Regex.OPT_ASTERISKS, lib.Regex.STREAM
            ), re.I
        )
        self._capture_pattern: Pattern[str] = re.compile(
            '\s*subscribe\s+#{0}({1}){0}\s+to\s+#{0}({1}){0}\s*\!?(.*)?\s*'
            .format(lib.Regex.OPT_ASTERISKS, lib.Regex.STREAM), re.I
        )

    def err(self, message: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        return lib.build_message(
            message, type(self).err_msg.format(message['sender_full_name'])
        )

    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        if not client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return lib.Response.admin_err(message)

        match: Optional[typing.Match[Any]] = self._capture_pattern.match(
            message['content']
        )
        if match is None:
            return lib.Response.command_not_found(message)

        (from_stream, to_stream, description) = match.groups()
        if description is None:
            description = ''

        subs: Dict[str, Any] = client.get_subscribers(stream = from_stream)

        if subs['result'] != 'success':
            return self.err(message)

        result: Dict[str, Any] = client.add_subscriptions(
            streams = [{'name': to_stream, 'description': description}],
            principals = subs['subscribers']
        )

        if result['result'] == 'success':
            return lib.Response.ok(message)
        else:
            return self.err(message)

