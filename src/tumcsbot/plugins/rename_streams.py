#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import logging

from inspect import cleandoc
from typing import Any, Dict, Iterable, List, Optional, Union

from tumcsbot.lib import Response, split
from tumcsbot.plugin import CommandPlugin


class RenameStreams(CommandPlugin):
    plugin_name = 'rename_streams'
    syntax = 'rename_streams <stream_name_old>,<stream_name_new>...'
    description = cleandoc(
        """
        Rename stream for every (`stream_name_old`,`stream_name_new`)-tuple \
        passed to this command. The stream names have to be plain names, \
        without `#` or `**`.
        [administrator rights needed]
        """
    )

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        if not self.client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return Response.admin_err(message)

        failed: List[str] = []

        stream_tuples: Optional[List[Any]] = split(
            message['command'], converter = [lambda t: split(t, sep = ',', exact_split = 2)]
        )
        if stream_tuples is None:
            return Response.error(message)

        for old, new in stream_tuples:
            # Used for error messages.
            line: str = f'{old} -> {new}'

            try:
                old_id: int = self.client.get_stream_id(old)['stream_id']
            except Exception as e:
                logging.exception(e)
                failed.append(line)
                continue

            result: Dict[str, Any] = self.client.update_stream(
                {'stream_id': old_id, 'new_name': '"{}"'.format(new)}
            )
            if result['result'] != 'success':
                failed.append(line)

        if not failed:
            return Response.ok(message)

        response: str = 'Failed to perform the following renamings:\n' + '\n'.join(failed)

        return Response.build_message(message, response, msg_type = 'private')
