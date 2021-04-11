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
    _insert_sql: str = 'insert or ignore into PublicStreams values (?)'
    _remove_sql: str = 'delete from PublicStreams where StreamName = ?'

    def __init__(self, plugin_context: PluginContext, **kwargs: Any) -> None:
        super().__init__(plugin_context)
        self._db = DB()
        self._db.checkout_table('PublicStreams', '(StreamName text primary key)')

    def is_responsible(self, event: Dict[str, Any]) -> bool:
        return (super().is_responsible(event)
                and (
                    event['op'] == 'create'
                    or event['op'] == 'update'
                    or event['op'] == 'delete'
                ))

    def handle_event(
        self,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        if event['op'] == 'create':
            for stream in event['streams']:
                self._handle_stream(stream['name'], stream['invite_only'])
        elif event['op'] == 'delete':
            for stream in event['streams']:
                self._remove_stream_from_table(stream['name'])
        elif event['op'] == 'update':
            if event['property'] == 'invite_only':
                self._handle_stream(event['name'], event['value'])
            elif (event['property'] == 'name' and not
                  self.client.private_stream_exists(event['name'])):
                # Remove the previous stream name from the database.
                self._remove_stream_from_table(event['name'])
                # Add the new stream name.
                self._handle_stream(event['value'], False)

        return Response.none()

    def _handle_stream(self, stream_name: str, private: bool) -> None:
        """Do the actual subscribing.

        Additionally, keep the list of public streams in the database
        up-to-date.
        """
        if private:
            self._remove_stream_from_table(stream_name)
            return

        try:
            self._db.execute(self._insert_sql, stream_name, commit = True)
        except Exception as e:
            logging.exception(e)

        self.client.subscribe_users([self.client.id], stream_name)

    def _remove_stream_from_table(self, stream_name: str) -> None:
        """Remove the given stream name from the PublicStreams table."""
        try:
            self._db.execute(self._remove_sql, stream_name, commit = True)
        except Exception as e:
            logging.exception(e)
