#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import subprocess as sp

from inspect import cleandoc
from typing import Any, Dict, Iterable, List, Pattern, Tuple, Union

import tumcsbot.lib as lib
import tumcsbot.command as command

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'update'
    syntax: str = 'update'
    description: str = cleandoc(
        """
        Update the bot. You may want to restart it afterwards.
        [administrator rights needed]
        """
    )
    _git_pull_cmd: List[str] = ['git', 'pull']
    _timeout: int = 15

    def __init__(self, **kwargs: Any):
        super().__init__()
        self._pattern: Pattern[str] = re.compile(r'\s*update\s*', re.I)

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, Iterable[lib.Response]]:
        if not client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return lib.Response.admin_err(message)

        # Execute command and capture stdout and stderr into one stream (stdout).
        try:
            result: sp.CompletedProcess = sp.run(
                self._git_pull_cmd, stdout = sp.PIPE, stderr = sp.STDOUT,
                text = True, timeout = self._timeout
            )
        except sp.TimeoutExpired:
            return lib.Response.build_message(
                message, f'{self._git_pull_cmd} failed: timeout ({self._timeout} seconds) expired'
            )

        return lib.Response.build_message(
            message,
            f'Return code: {result.returncode}\nOutput:\n```text\n{result.stdout}\n```'
        )
