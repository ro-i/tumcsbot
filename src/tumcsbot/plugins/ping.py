#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from typing import Any, Dict, Iterable, Union

from tumcsbot.lib import Response
from tumcsbot.plugin import Plugin


class Ping(Plugin):
    """The user pinged us. Still be nice! :)

    Do not react on pings in private messages that do not contain a
    command! Otherwise, we'll reach the API rate limit when we
    subscribe a lot of users to a stream, the Notification Bot
    notifies them of the subscription (with ping) and we react on the
    messages of the Notification Bot to the users.
    """
    plugin_name = 'ping'
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
                    # Only handle command messages if the command is empty.
                    'command_name' in event['message']
                    and not event['message']['command_name']
                )
                or (
                    'command_name' not in event['message']
                    and event['message']['sender_id'] != self.client.id
                    and 'mentioned' in event['flags']
                    and (not event['message']['type'] == 'private'
                         or self.client.is_only_pm_recipient(event['message']))
                )
            )
        )
