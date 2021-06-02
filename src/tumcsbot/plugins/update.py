#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import logging
import os
import subprocess as sp

from inspect import cleandoc
from pathlib import Path
from typing import Any, Dict, Iterable, List, Union

from tumcsbot.lib import Response
from tumcsbot.plugin import CommandPlugin


class Update(CommandPlugin):
    plugin_name = 'update'
    syntax = 'update'
    description = cleandoc(
        """
        Update the bot. You may want to restart it afterwards.
        [administrator/moderator rights needed]
        """
    )
    _git_pull_cmd: List[str] = ['git', 'pull']
    _timeout: int = 15

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        if not self.client.user_is_privileged(message['sender_id']):
            return Response.admin_err(message)

        # Get the dirname of this file (which is located in the git repo).
        git_dir: Path = Path(__file__).parent.absolute()

        try:
            os.chdir(git_dir)
        except Exception as e:
            logging.exception(e)
            return Response.build_message(
                message,
                f'Cannot access the directory of my git repo {git_dir}. Please contact the admin.'
            )

        # Execute command and capture stdout and stderr into one stream (stdout).
        try:
            result: sp.CompletedProcess[Any] = sp.run(
                self._git_pull_cmd, stdout = sp.PIPE, stderr = sp.STDOUT,
                text = True, timeout = self._timeout,
            )
        except sp.TimeoutExpired:
            return Response.build_message(
                message, f'{self._git_pull_cmd} failed: timeout ({self._timeout} seconds) expired'
            )

        return Response.build_message(
            message,
            f'Return code: {result.returncode}\nOutput:\n```text\n{result.stdout}\n```'
        )
