#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Dict, Iterable, List, Tuple, Union

from tumcsbot.lib import DB, Response
from tumcsbot.plugin import CommandPlugin, PluginContext


class Source(CommandPlugin):
    plugin_name = 'sql'
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
        [administrator rights needed]
        """
    )
    _list_sql: str = 'select * from sqlite_master where type = "table"'

    def __init__(self, plugin_context: PluginContext) -> None:
        super().__init__(plugin_context)
        # Get own read-only (!!!) database connection.
        self._db = DB(read_only = True)

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        result_sql: List[Tuple[Any, ...]]

        if not self.client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return Response.admin_err(message)

        try:
            if message['command'] == 'list':
                result_sql = self._db.execute(self._list_sql)
            else:
                result_sql = self._db.execute(message['command'])
        except Exception as e:
            return Response.build_message(message, str(e))

        result: str = '```text\n' + '\n'.join(map(str, result_sql)) + '\n```'

        return Response.build_message(message, result)
