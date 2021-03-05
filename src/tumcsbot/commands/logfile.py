#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import logging
import re

from typing import Any, Dict, Iterable, List, Pattern, Tuple, Union

import tumcsbot.lib as lib
import tumcsbot.command as command

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'logfile'
    syntax: str = 'logfile'
    description: str = 'Get the bot\'s own logfile.\n[administrator rights needed]'

    def __init__(self, **kwargs: Any):
        super().__init__()
        self._pattern: Pattern[str] = re.compile(r'\s*logfile\s*', re.I)

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, Iterable[lib.Response]]:
        if not client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return lib.Response.admin_err(message)

        handlers: List[logging.Handler] = logging.getLogger().handlers
        if not handlers or len(handlers) > 1:
            return lib.Response.build_message(message, 'Cannot determine the logfile.')

        if not isinstance(handlers[0], logging.FileHandler):
            return lib.Response.build_message(message, 'No logfile in use.')

        # Upload the logfile. (see https://zulip.com/api/upload-file)
        with open(handlers[0].baseFilename, 'rb') as lf:
            result: Dict[str, Any] = client.call_endpoint(
                'user_uploads', method = 'POST', files = [lf]
            )

        if result['result'] != 'success':
            return lib.Response.build_message(message, 'Could not upload the logfile.')

        return lib.Response.build_message(message, '[logfile]({})'.format(result['uri']))
