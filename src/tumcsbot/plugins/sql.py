#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Iterable

from tumcsbot.lib import DB, Response
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class Source(PluginCommandMixin, PluginThread):
    syntax = cleandoc(
        """
        sql <sql_script>
          or sql list
        """
    )
    description = cleandoc(
        """
        Access the internal database of the bot read-only.
        The `list` command is a shortcut to list all tables.
        [administrator/moderator rights needed]
        """
    )
    _list_sql: str = 'select * from sqlite_master where type = "table"'

    def _init_plugin(self) -> None:
        # Get own read-only (!!!) database connection.
        self._db: DB = DB(read_only=True)

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        result_sql: list[tuple[Any, ...]]

        if not self.client.user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        try:
            if message["command"] == "list":
                result_sql = self._db.execute(self._list_sql)
            else:
                result_sql = self._db.execute(message["command"])
        except Exception as e:
            return Response.build_message(message, str(e))

        result: str = "```text\n" + "\n".join(map(str, result_sql)) + "\n```"

        return Response.build_message(message, result)
