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

from typing import Iterable

from tumcsbot.lib import DB, Response
from tumcsbot.plugin import Event, PluginThread


class AutoSubscriber(PluginThread):
    zulip_events = ["stream"]
    _insert_sql: str = "insert or ignore into PublicStreams values (?, 0)"
    _select_sql: str = "select StreamName, Subscribed from PublicStreams"
    _subscribe_sql: str = "update PublicStreams set Subscribed = 1 where StreamName = ?"
    _remove_sql: str = "delete from PublicStreams where StreamName = ?"

    def _init_plugin(self) -> None:
        self._db: DB = DB()
        self._db.checkout_table(
            "PublicStreams",
            "(StreamName text primary key, Subscribed integer not null)",
        )
        # Ensure that we are subscribed to all existing streams.
        for stream_name, subscribed in self._db.execute(self._select_sql):
            if subscribed == 1:
                continue
            self._handle_stream(stream_name, False)

    def is_responsible(self, event: Event) -> bool:
        return super().is_responsible(event) and (
            event.data["op"] == "create"
            or event.data["op"] == "update"
            or event.data["op"] == "delete"
        )

    def handle_zulip_event(self, event: Event) -> Response | Iterable[Response]:
        if event.data["op"] == "create":
            for stream in event.data["streams"]:
                self._handle_stream(stream["name"], stream["invite_only"])
        elif event.data["op"] == "delete":
            for stream in event.data["streams"]:
                self._remove_stream_from_table(stream["name"])
        elif event.data["op"] == "update":
            if event.data["property"] == "invite_only":
                self._handle_stream(event.data["name"], event.data["value"])
            elif event.data[
                "property"
            ] == "name" and not self.client().private_stream_exists(event.data["name"]):
                # Remove the previous stream name from the database.
                self._remove_stream_from_table(event.data["name"])
                # Add the new stream name.
                self._handle_stream(event.data["value"], False)

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
            self._db.execute(self._insert_sql, stream_name, commit=True)
        except Exception as e:
            self.logger.exception(e)

        if self.client().subscribe_users([self.client().id], stream_name):
            try:
                self._db.execute(self._subscribe_sql, stream_name, commit=True)
            except Exception as e:
                self.logger.exception(e)
        else:
            self.logger.warning("could not subscribe to %s", stream_name)

    def _remove_stream_from_table(self, stream_name: str) -> None:
        """Remove the given stream name from the PublicStreams table."""
        try:
            self._db.execute(self._remove_sql, stream_name, commit=True)
        except Exception as e:
            self.logger.exception(e)
