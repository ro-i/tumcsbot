#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Iterable

from tumcsbot.lib import CommandParser, DB, Response
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class Msg(PluginCommandMixin, PluginThread):
    syntax = cleandoc(
        """
        msg add <identifier> <text>
          or msg send|remove <identifier>
          or msg list
        """
    )
    description = cleandoc(
        """
        Store a message for later use, send or delete a stored message \
        or list all stored messages. The text must be quoted but may
        contain line breaks.
        The identifiers are handled case insensitively.
        [administrator/moderator rights needed]
        """
    )
    _delete_sql: str = "delete from Messages where MsgId = ?"
    _list_sql: str = "select * from Messages"
    _search_sql: str = "select MsgText from Messages where MsgId = ?"
    _update_sql: str = "replace into Messages values (?,?)"

    def _init_plugin(self) -> None:
        # Get own database connection.
        self._db: DB = DB()
        # Check for database table.
        self._db.checkout_table(
            table="Messages", schema="(MsgId text primary key, MsgText text not null)"
        )
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand("add", args={"id": str, "text": str})
        self.command_parser.add_subcommand("send", args={"id": str})
        self.command_parser.add_subcommand("remove", args={"id": str})
        self.command_parser.add_subcommand("list")

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        result: tuple[str, CommandParser.Opts, CommandParser.Args] | None
        result_sql: list[tuple[Any, ...]]

        if not self.client().user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        # Get command and parameters.
        result = self.command_parser.parse(message["command"])
        if result is None:
            return Response.command_not_found(message)
        command, _, args = result

        if command == "list":
            response: str = "***List of Identifiers and Messages***\n"
            for ident, text in self._db.execute(self._list_sql):
                response += f"\n--------\nTitle: **{ident}**\n{text}"
            return Response.build_message(message, response)

        # Use lowercase -> no need for case insensitivity.
        ident = args.id.lower()

        if command == "send":
            result_sql = self._db.execute(self._search_sql, ident)
            if not result_sql:
                return Response.command_not_found(message)
            # Remove requesting message.
            self.client().delete_message(message["id"])
            return Response.build_message(message, result_sql[0][0])

        if command == "add":
            self._db.execute(self._update_sql, ident, args.text, commit=True)
            return Response.ok(message)

        if command == "remove":
            self._db.execute(self._delete_sql, ident, commit=True)
            return Response.ok(message)

        return Response.command_not_found(message)
