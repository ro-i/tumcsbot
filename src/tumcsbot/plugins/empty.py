#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from typing import Any, Dict, Iterable, Union

from tumcsbot.lib import Response
from tumcsbot.plugin import Plugin


class Empty(Plugin):
    """The user sent us an empty command.

    Still be nice! :)
    """
    plugin_name = 'empty'
    events = ['message']

    def handle_event(
        self,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        return Response.build_reaction(event['message'], 'wave')

    def is_responsible(self, event: Dict[str, Any]) -> bool:
        return (
            event['type'] == 'message'
            and (
                (
                    'command_name' in event['message']
                    and not event['message']['command_name']
                )
                or (
                    'command_name' not in event['message']
                    and 'mentioned' in event['flags']
                )
            )
        )
