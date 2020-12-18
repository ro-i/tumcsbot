#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import sqlite3 as sqlite
import typing
import urllib.parse
import urllib.request

from abc import ABC, abstractmethod
from enum import Enum
from inspect import cleandoc
from typing import Any, Dict, List, Optional, Tuple, Union

from .client import Client


##################
## Begin: enums ##
##################

# cf. https://docs.python.org/3/library/enum.html#others
class StrEnum(str, Enum):
    pass


class Regex(StrEnum):
    FILE: str = '\[[^\[\]]*\]\([^\(\)]*\)'
    FILE_CAPTURE: str = '\[[^\[\]]*\]\(([^\(\)]*)\)'
    OPT_ASTERISKS: str = '(?:\*\*|)'
    STREAM: str = '[^*#]*'


class MessageType(StrEnum):
    MESSAGE: str = 'message'
    EMOJI: str = 'emoji'
    NONE: str = 'none'

################
## End: enums ##
################


class DB:
    '''
    Simple wrapper class for conveniently accessing a sqlite database.
    Currently not threadsafe.
    '''
    path: Optional[str] = None

    def __init__(self) -> None:
        if not DB.path:
            raise ValueError('no path to database given')
        self.connection = sqlite.connect(DB.path)
        self.cursor = self.connection.cursor()

    def checkout_table(self, table: str, schema: str) -> None:
        '''
        Create table if it does not already exist.
        Arguments:
            table   name of the table
            schema  schema of the table in the form of
                      '(Name Type, ...)' --> valid SQL!
        '''
        result: List[Tuple[Any, ...]] = self.execute(
            ('select * from sqlite_master where type = "table" and '
             'name = "{}";'.format(table))
        )
        if not result:
            self.execute(
                'create table {} {};'.format(table, schema),
                commit = True
            )

    def checkout_row(
        self,
        table: str,
        key_column: str,
        key: str,
        default_values: str
    ) -> None:
        '''
        Create row in table if it does not already exist.
        Arguments:
            table           name of the table
            key_column      name of the column of the primary key
            key             key to identify the row
            default_values  default value to insert if row does not yet
                            exist
                            - must be in the form of
                              '(Integer, "String", ...)' --> valid SQL!
        '''
        result: List[Tuple[Any, ...]] = self.execute(
            'select * from {} where {} = "{}";'.format(table, key_column, key)
        )
        if not result:
            self.execute(
                'insert into {} values {}'.format(table, default_values),
                commit = True
            )

    def execute(
        self,
        command: str,
        *args: Any,
        commit: bool = False
    ) -> List[Tuple[Any, ...]]:
        '''
        Execute sql command, save the new database state
        (if commit == True) and return the result of the command.
        Forward 'args' to cursor.execute()
        '''
        result: sqlite.Cursor = self.cursor.execute(command, args)
        if commit:
            self.connection.commit()
        return result.fetchall()


class Helper:
    '''
    Collect all usage documentation from the command classes during
    their import by TumCSBot.
    '''

    help: str = cleandoc(
        '''
        Hi {}!
        Currently, I understand the following commands:

        {}

        Have a nice day! :-)
        '''
    )
    command_docs: str = ''

    @classmethod
    def get_help(cls, user: str) -> str:
        return cls.help.format(user, cls.command_docs)

    @classmethod
    def extend_command_docs(cls, docs: List[Tuple[str, str]]) -> None:
        processed: List[str] = []

        # sort by syntax string
        docs = sorted(docs, key = lambda tuple: tuple[0])

        # format
        for (syntax, desc) in docs:
            syntax = '- `' + syntax.replace('\n', '') + '`'
            # replace multiple newlines by a single one
            desc = re.sub('\n{2,}', '\n', desc)
            if not desc.endswith('\n'):
                desc += '\n'
            # ensure one (!) joining newline
            if not desc.startswith('\n'):
                syntax += '\n'
            processed.append(syntax + desc)

        cls.command_docs += '\n'.join(processed)


class Response:
    admin_err_msg: str = cleandoc(
        '''
        Hi {}!
        You need to be administrator of this organization in order to execute \
        this command.
        '''
    )
    command_not_found_msg: str = cleandoc(
        '''
        Hi {}!
        Unfortunately, I currently cannot understand what you wrote to me.
        Try "help" to get a glimpse of what I am capable of. :-)
        '''
    )
    exception_msg: str = cleandoc(
        '''
        Hi {}!
        An exception occurred while executing your request.
        Did you try to hack me? ;-)
        '''
    )
    error_msg: str = cleandoc(
        '''
        Sorry, {}, an error occurred while executing your request.
        '''
    )
    greet_msg: str = 'Hi {}! :-)'
    ok_emoji: str = 'ok'
    no_emoji: str = 'cross_mark'

    @classmethod
    def build_message(
        cls,
        message: Dict[str, Any],
        response: str,
        type: Optional[str] = None,
        to: Optional[str] = None,
        subject: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        if type is None:
            type = message['type']
        private: bool = type == 'private'

        if to is None:
            to = message['sender_email'] if private else message['stream_id']

        if subject is None:
            subject = message['subject'] if not private else ''

        if private:
            return new_private_message(
                to = to,
                content = response
            )
        else:
            return new_stream_message(
                stream = to,
                subject = subject,
                content = response
            )

    @classmethod
    def build_reaction(
        cls,
        message: Dict[str, Any],
        emoji: str
    ) -> Tuple[str, Dict[str, Any]]:
        return (
            MessageType.EMOJI,
            dict(message_id = message['id'], emoji_name = emoji)
        )

    @classmethod
    def admin_err(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return cls.build_message(
            message,
            cls.admin_err_msg.format(message['sender_full_name'])
        )

    @classmethod
    def command_not_found(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return cls.build_message(
            message,
            cls.command_not_found_msg.format(message['sender_full_name'])
        )

    @classmethod
    def error(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return cls.build_message(
            message, cls.error_msg.format(message['sender_full_name'])
        )

    @classmethod
    def exception(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return cls.build_message(
            message, cls.exception_msg.format(message['sender_full_name'])
        )

    @classmethod
    def greet(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return cls.build_message(
            message, cls.greet_msg.format(message['sender_full_name'])
        )

    @classmethod
    def ok(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return cls.build_reaction(message, cls.ok_emoji)

    @classmethod
    def no(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return cls.build_reaction(message, cls.no_emoji)

    @classmethod
    def none(cls) -> Tuple[str, Dict[str, Any]]:
        '''no response'''
        return (MessageType.NONE, {})


def new_private_message(
    to: Union[str, int],
    content: str
) -> Tuple[str, Dict[str, Any]]:
    '''
    Send private message. "to" is either a list containing integer user
    IDs or a list containing string email addresses.
    '''
    return (
        MessageType.MESSAGE,
        dict(
            type = 'private',
            to = to,
            content = content
        )
    )


def new_stream_message(
    stream: Union[str, int],
    subject: str,
    content: str
) -> Tuple[str, Dict[str, Any]]:
    '''
    Send stream message. "stream" is either the name or the integer ID
    of the stream.
    '''
    return (
        MessageType.MESSAGE,
        dict(
            type = 'stream',
            to = stream,
            subject = subject,
            content = content
        )
    )

