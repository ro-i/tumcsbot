#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from typing import Any, Dict, Iterable, Union

from tumcsbot.lib import Response
from tumcsbot.plugin import CommandPlugin


class Source(CommandPlugin):
    plugin_name = 'source'
    syntax = 'source'
    description = 'Post the link to the repository of my source code.'

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        return Response.build_message(
            message, 'https://github.com/ro-i/tumcsbot'
        )
