#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from tumcsbot.lib import CommandParser, DB, Response
from tumcsbot.plugin import PluginContext, CommandPlugin


class Msg(CommandPlugin):
    plugin_name = 'msg'
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
    _delete_sql: str = 'delete from Messages where MsgId = ?'
    _list_sql: str = 'select * from Messages'
    _search_sql: str = 'select MsgText from Messages where MsgId = ?'
    _update_sql: str = 'replace into Messages values (?,?)'

    def __init__(self, plugin_context: PluginContext) -> None:
        super().__init__(plugin_context)
        # Get own database connection.
        self._db = DB()
        # Check for database table.
        self._db.checkout_table(
            table = 'Messages', schema = '(MsgId text primary key, MsgText text not null)'
        )
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand('add', {'id': str, 'text': str})
        self.command_parser.add_subcommand('send', {'id': str})
        self.command_parser.add_subcommand('remove', {'id': str})
        self.command_parser.add_subcommand('list')

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        result: Optional[Tuple[str, CommandParser.Args]]
        result_sql: List[Tuple[Any, ...]]

        if not self.client.user_is_privileged(message['sender_id']):
            return Response.admin_err(message)

        # Get command and parameters.
        result = self.command_parser.parse(message['command'])
        if result is None:
            return Response.command_not_found(message)
        command, args = result

        if command == 'list':
            response: str = '***List of Identifiers and Messages***\n'
            for (ident, text) in self._db.execute(self._list_sql):
                response += '\n--------\nTitle: **{}**\n{}'.format(ident, text)
            return Response.build_message(message, response)

        # Use lowercase -> no need for case insensitivity.
        ident = args.id.lower()

        if command == 'send':
            result_sql = self._db.execute(self._search_sql, ident)
            if not result_sql:
                return Response.command_not_found(message)
            # Remove requesting message.
            self.client.delete_message(message['id'])
            return Response.build_message(message, result_sql[0][0])

        if command == 'add':
            self._db.execute(self._update_sql, ident, args.text, commit = True)
            return Response.ok(message)

        if command == 'remove':
            self._db.execute(self._delete_sql, ident, commit = True)
            return Response.ok(message)

        return Response.command_not_found(message)
