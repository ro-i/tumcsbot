#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import datetime
import json
from inspect import cleandoc
from sqlite3 import IntegrityError
from typing import Any, Final, Iterable

from tumcsbot.lib import CommandParser, DB, Response
from tumcsbot.plugin import Event, EventType, PluginCommandMixin, PluginThread


class Jobs(PluginCommandMixin, PluginThread):
    syntax = cleandoc(
        """
        jobs add <iso_timestamp_string>\\n<command>
          or jobs remove <iso_timestamp_string>
          or jobs list
        """
    )
    description = cleandoc(
        """
        one-shot jobs for Zulip
        Note on `iso_timestamp_string`: `2020-12-15 20:42:00`
        [administrator rights needed]
        """
    )
    _insert_sql: Final[str] = "insert into Jobs values (?,?,?,?)"
    _list_sql: Final[str] = "select * from Jobs"
    _remove_sql: Final[str] = "delete from Jobs where TimeStamp = ?"
    _select_next_sql: Final[
        str
    ] = 'select min(TimeStamp), Command, Result from Jobs where Result = "not yet executed"'
    _update_result_sql: Final[str] = "update Jobs set Result = ? where TimeStamp = ?"

    def _init_plugin(self) -> None:
        self.command: str | None = None
        self.timestamp: str | None = None

        # Get own database connection.
        self._db: DB = DB()
        # Check for database table.
        self._db.checkout_table(
            table="Jobs",
            schema=(
                "(TimeStamp timestamp primary key, Command text not null, "
                "UserId integer not null, Result text not null)"
            ),
        )
        # Set the timeout for the event queue to block.
        self.reload()

        self.command_parser = CommandParser()
        self.command_parser.add_subcommand(
            "add", args={"timestamp": str, "command": str}, greedy=True
        )
        self.command_parser.add_subcommand("remove", args={"timestamp": str})
        self.command_parser.add_subcommand("list")

    def handle_message(self, _: dict[str, Any]) -> Response | Iterable[Response]:
        """Dummy implementation."""
        return Response.none()

    def handle_zulip_event(self, event: Event) -> Response | Iterable[Response]:
        responses: Response | Iterable[Response]
        result: tuple[str, CommandParser.Opts, CommandParser.Args] | None

        message: dict[str, Any] = event.data["message"]

        if not self.client().get_user_by_id(message["sender_id"])["user"]["is_admin"]:
            return Response.admin_err(message)

        result = self.command_parser.parse(message["command"])
        if result is None:
            return Response.command_not_found(message)
        command, _, args = result

        if command == "add":
            responses = self._add(
                message, event.data, args.timestamp, " ".join(args.command)
            )
            self.reload()
            return responses
        if command == "list":
            return self._list(message)
        if command == "remove":
            responses = self._remove(message, args.timestamp)
            self.reload()
            return responses

        return Response.command_not_found(message)

    def _add(
        self,
        message: dict[str, Any],
        zulip_event: dict[str, Any],
        timestamp: str,
        command: str,
    ) -> Response | Iterable[Response]:
        # Validate time format.
        try:
            datetime.datetime.fromisoformat(timestamp)
        except:
            return Response.build_message(message, "invalid time format")

        future_zulip_event: dict[str, Any] = self._build_command(zulip_event, command)
        try:
            self._db.execute(
                self._insert_sql,
                timestamp,
                json.dumps(future_zulip_event),
                message["sender_id"],
                "not yet executed",
                commit=True,
            )
        except IntegrityError as e:
            return Response.build_message(message, str(e))

        return Response.ok(message)

    def _build_command(
        self, zulip_event: dict[str, Any], command: str
    ) -> dict[str, Any]:
        """Build the command message to be sent in the future.

        Replace the original message text with the command and return
        the new message object.
        (Thus, keep the sender and all the other message attributes.)
        """
        future_zulip_event: dict[str, Any] = zulip_event.copy()
        # Replace original content.
        future_zulip_event["message"]["content"] = command
        # Set the message type to private.
        future_zulip_event["message"]["type"] = "private"
        # Remove custom attribute.
        del future_zulip_event["message"]["command"]
        del future_zulip_event["message"]["command_name"]
        return future_zulip_event

    def handle_queue_timeout(self) -> None:
        """Queue timeout.

        We need to execute our scheduled job.
        """
        if self.command is not None and self.timestamp is not None:
            self.logger.debug("fake command %s", self.command)
            # Fake original event.
            self.plugin_context.push_loopback(
                Event(
                    sender=self.plugin_name(),
                    type=EventType.ZULIP,
                    data=json.loads(self.command),
                )
            )
            self._update_result(self.timestamp, "sent")
        self.reload()

    def _list(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        response: str = (
            "TimeStamp | Command | UserId | Result\n---- | ---- | ---- | ----"
        )
        for ts, cmd, user, result in self._db.execute(self._list_sql):
            response += "\n" + "{} | {} | {} | {}".format(ts, cmd, user, result)
        return Response.build_message(message, response)

    def reload(self) -> None:
        while True:
            result: list[tuple[Any, ...]] = self._db.execute(self._select_next_sql)
            if not result or not result[0] or result[0][0] is None:
                self.logger.debug("disable queue timeout")
                self.queue_timeout = None
                break
            try:
                todo_time: datetime.datetime = datetime.datetime.fromisoformat(
                    result[0][0]
                )
            except:
                self._update_result(result[0][0], "cannot execute: invalid timestamp")
                continue
            new_timeout: float = (todo_time - datetime.datetime.now()).total_seconds()
            if new_timeout < 0:
                self._update_result(result[0][0], "not executed: time over")
                continue
            self.queue_timeout = new_timeout
            self.logger.debug("set timeout %d", self.queue_timeout)
            self.command = result[0][1]
            self.timestamp = result[0][0]
            break

    def _remove(
        self,
        message: dict[str, Any],
        timestamp: str,
    ) -> Response | Iterable[Response]:
        self._db.execute(self._remove_sql, timestamp, commit=True)
        return Response.ok(message)

    def _update_result(self, timestamp: str, result: str) -> None:
        """Update command execution result."""
        try:
            self._db.execute(self._update_result_sql, result, timestamp, commit=True)
        except Exception as e:
            self.logger.exception(e)
