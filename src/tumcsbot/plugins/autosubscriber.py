#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Keep the bot subscribed to all public streams.

Reason:
As the 'all_public_streams' parameter of the event API [1] does not
seem to work properly, we need a work-around in order to be able to
receive events for all public streams.

[1] https://zulip.com/api/register-queue#parameter-all_public_streams
"""

import logging

from typing import Any, Dict, Iterable, Union

from tumcsbot.lib import DB, Response
from tumcsbot.plugin import Plugin, PluginContext


class AutoSubscriber(Plugin):
    plugin_name = 'autosubscriber'
    events = ['stream']
    _insert_sql: str = 'insert into PublicStreams values (?)'

    def __init__(self, plugin_context: PluginContext, **kwargs: Any) -> None:
        super().__init__(plugin_context)
        self._db = DB()
        self._db.checkout_table('PublicStreams', '(StreamName text primary key)')

    def is_responsible(self, event: Dict[str, Any]) -> bool:
        return (super().is_responsible(event)
                and event['op'] == 'create')

    def handle_event(
        self,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        """Do the actual subscribing."""
        for stream in event['streams']:
            if stream['invite_only']:
                continue
            try:
                self._db.execute(self._insert_sql, stream['name'], commit = True)
            except Exception as e:
                logging.exception(e)
            self.client.subscribe_users([self.client.id], stream['name'])

        return Response.none()
