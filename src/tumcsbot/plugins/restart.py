#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import os
import signal

from typing import Any, Dict, Iterable, Union

from tumcsbot.lib import user_is_privileged, Response
from tumcsbot.plugin import CommandPlugin


class Restart(CommandPlugin):
    plugin_name = 'restart'
    syntax = 'restart'
    description = 'Restart the bot.\n[administrator/moderator rights needed]'

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        if not user_is_privileged(self.client.get_user_by_id(message['sender_id'])):
            return Response.admin_err(message)

        # Ask the parent process to restart.
        os.kill(os.getpid(), signal.SIGUSR1)

        # dead code
        return Response.none()
