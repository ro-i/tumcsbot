#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing
import urllib.parse

from typing import Any, Dict, List, Match, Optional, Pattern, Sequence, Tuple, Union
from zulip import Client

import tumcsbot.command as command
import tumcsbot.lib as lib


class Command(command.Command):
    name: str = 'msg'
    syntax: str = ('[Experimental] msg store\\n<identifier>\\n<text> or '
                   'msg send|delete <identifier> or '
                   'msg list')
    description: str = ('store a message for later use, send or delete a '
                        'stored message or list all stored messages')
    _search_cmd: str = 'select m.Text from Messages m where m.Id = ? collate nocase'
    _update_cmd: str = 'update Messages set Text = ? where Id = ? collate nocase'
    _insert_cmd: str = 'insert into Messages values (?,?)'
    _delete_cmd: str = 'delete from Messages where Id = ? collate nocase'
    _list_cmd: str = 'select * from Messages'

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

    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        result: List[Tuple[Any, ...]]

        # get command and parameters
        match: Optional[Match[str]] = (
            self._pattern_store.match(message['content'])
            or self._pattern_send.match(message['content'])
            or self._pattern_delete.match(message['content'])
            or self._pattern_list.match(message['content'])
        )

        if not match:
            return lib.Response.command_not_found(message)
        args: Union[Sequence[str], Any] = match.groups()

        if args[0] == 'list':
            result = self._db.execute(Command._list_cmd)
            response: str = '**Id**: Text'
            for (ident, text) in result:
                response += '\n--------\n**{}**:\n{}'.format(ident, text)
            return lib.build_message(message, response)

        # search for identifier in database table
        result = self._db.execute(Command._search_cmd, args[1])

        if args[0] == 'send':
            if not result:
                return lib.Response.no(message)
            # remove requesting message
            client.delete_message(message['id'])
            return lib.build_message(message, result[0][0])
        elif args[0] == 'store':
            self._db.execute(
                Command._update_cmd if result else Command._insert_cmd,
                args[1], args[2], commit = True
            )
        elif args[0] == 'delete':
            if not result:
                return lib.Response.no(message)
            self._db.execute(Command._delete_cmd, args[1], commit = True)

        return lib.Response.ok(message)

