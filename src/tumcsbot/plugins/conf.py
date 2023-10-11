#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Iterable

from tumcsbot.lib import CommandParser, DB, Response
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class Conf(PluginCommandMixin, PluginThread):
    syntax = cleandoc(
        """
        conf set <key> <value>
          or conf remove <key>
          or conf list
        """
    )
    description = cleandoc(
        """
        Set/get/remove bot configuration variables.
        [administrator/moderator rights needed]
        """
    )
    _list_sql: str = "select * from Conf"
    _remove_sql: str = "delete from Conf where Key = ?"
    _update_sql: str = "replace into Conf values (?,?)"

    def _init_plugin(self) -> None:
        self._db: DB = DB()
        self._db.checkout_table("Conf", "(Key text primary key, Value text not null)")
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand("list")
        self.command_parser.add_subcommand("set", args={"key": str, "value": str})
        self.command_parser.add_subcommand("remove", args={"key": str})

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        result: tuple[str, CommandParser.Opts, CommandParser.Args] | None

        if not self.client().user_is_privileged(message["sender_id"]):
            return Response.admin_err(message)

        result = self.command_parser.parse(message["command"])
        if result is None:
            return Response.command_not_found(message)
        command, _, args = result

        if command == "list":
            response: str = "Key | Value\n ---- | ----"
            for key, value in self._db.execute(self._list_sql):
                response += f"\n{key} | {value}"
            return Response.build_message(message, response)

        if command == "remove":
            self._db.execute(self._remove_sql, args.key, commit=True)
            return Response.ok(message)

        if command == "set":
            try:
                self._db.execute(self._update_sql, args.key, args.value, commit=True)
            except Exception as e:
                self.logger.exception(e)
                return Response.build_message(message, "Failed: %s" % str(e))
            return Response.ok(message)

        return Response.command_not_found(message)
