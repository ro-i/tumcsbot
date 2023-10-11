#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from typing import Any, Iterable

from tumcsbot.lib import Response
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class Source(PluginCommandMixin, PluginThread):
    syntax = "source"
    description = "Post the link to the repository of my source code."

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        return Response.build_message(message, "https://github.com/ro-i/tumcsbot")
