#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from typing import Any, Iterable

from tumcsbot.lib import Response, is_bot_owner
from tumcsbot.plugin import Event, PluginCommandMixin, PluginThread


class Restart(PluginCommandMixin, PluginThread):
    syntax = "restart"
    description = "Restart the bot.\n[only bot owner]"

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        if not is_bot_owner(message["sender_id"]):
            return Response.privilege_err(message)

        self.plugin_context.push_loopback(Event._empty_event("restart", "_root"))

        return Response.none()
