#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import logging
from typing import Any, Iterable

from tumcsbot.lib import Response
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class Logfile(PluginCommandMixin, PluginThread):
    syntax = "logfile"
    description = "Get the bot's own logfile.\n[administrator/moderator rights needed]"

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        if not self.client.user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        handlers: list[logging.Handler] = logging.getLogger().handlers
        if not handlers or len(handlers) > 1:
            return Response.build_message(message, "Cannot determine the logfile.")

        if not isinstance(handlers[0], logging.FileHandler):
            return Response.build_message(message, "No logfile in use.")

        # Upload the logfile. (see https://zulip.com/api/upload-file)
        with open(handlers[0].baseFilename, "rb") as lf:
            result: dict[str, Any] = self.client.call_endpoint(
                "user_uploads", method="POST", files=[lf]
            )

        if result["result"] != "success":
            return Response.build_message(message, "Could not upload the logfile.")

        return Response.build_message(message, f"[logfile]({result['uri']})")
