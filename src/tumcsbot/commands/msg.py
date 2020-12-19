#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing

from typing import Any, Dict, List, Match, Optional, Pattern, Sequence, Tuple, Union

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'msg'
    syntax: str = ('[Experimental] msg store <identifier>\\n<text> or '
                   'msg send|delete <identifier> or '
                   'msg list')
    description: str = ('store a message for later use, send or delete a '
                        'stored message or list all stored messages')
    _search_sql: str = 'select m.Text from Messages m where m.Id = ? collate nocase'
    _update_sql: str = 'update Messages set Text = ? where Id = ? collate nocase'
    _insert_sql: str = 'insert into Messages values (?,?)'
    _delete_sql: str = 'delete from Messages where Id = ? collate nocase'
    _list_sql: str = 'select * from Messages'

    def __init__(self, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile(
            '\s*msg\s*(?:store *[^\n]+\n.+|send *[^\n]+|delete *[^\n]+|list\s*)',
            re.I | re.DOTALL
        )
        self._pattern_store: Pattern[str] = re.compile(
            '\s*msg\s*(store) *([^\n]+)\n(.+)', re.I | re.DOTALL
        )
        self._pattern_send: Pattern[str] = re.compile(
            '\s*msg\s*(send) *(.+)', re.I
        )
        self._pattern_delete: Pattern[str] = re.compile(
            '\s*msg\s*(delete) *(.+)', re.I
        )
        self._pattern_list: Pattern[str] = re.compile(
            '\s*msg\s*(list)\s*', re.I
        )
        # get own database connection
        self._db = lib.DB()
        # check for database table
        self._db.checkout_table(
            table = 'Messages',
            schema = '(Id varchar, Text varchar)'
        )

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        result: List[Tuple[Any, ...]]

        if not client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return lib.Response.admin_err(message)

        # get command and parameters
        match: Optional[Match[str]] = (
            self._pattern_store.match(message['command'])
            or self._pattern_send.match(message['command'])
            or self._pattern_delete.match(message['command'])
            or self._pattern_list.match(message['command'])
        )

        if not match:
            return lib.Response.command_not_found(message)
        args: Union[Sequence[str], Any] = match.groups()

        if args[0] == 'list':
            result = self._db.execute(Command._list_sql)
            response: str = '***List of Identifiers and Messages***\n'
            for (ident, text) in result:
                response += '\n--------\nTitle: **{}**\n{}'.format(ident, text)
            return lib.Response.build_message(message, response)

        # search for identifier in database table
        result = self._db.execute(Command._search_sql, args[1].strip())

        if args[0] == 'send':
            if not result:
                return lib.Response.no(message)
            # remove requesting message
            client.delete_message(message['id'])
            return lib.Response.build_message(message, result[0][0])
        elif args[0] == 'store':
            if result:
                self._db.execute(
                    Command._update_sql, args[2], args[1].strip(), commit = True
                )
            else:
                self._db.execute(
                    Command._insert_sql, args[1].strip(), args[2], commit = True
                )
        elif args[0] == 'delete':
            if not result:
                return lib.Response.no(message)
            self._db.execute(Command._delete_sql, args[1].strip(), commit = True)

        return lib.Response.ok(message)

