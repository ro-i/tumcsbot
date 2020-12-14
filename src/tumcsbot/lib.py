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
from typing import Any, Dict, List, Optional, Tuple
from zulip import Client


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


class ResponseType(StrEnum):
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
                'insert into {} values {}'.format(table, default_values)
                commit = True
            )

    def execute(
        self,
        command: str,
        *args,
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

    @classmethod
    def admin_err(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return build_message(
            message,
            cls.admin_err_msg.format(message['sender_full_name'])
        )

    @classmethod
    def command_not_found(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return build_message(
            message,
            cls.command_not_found_msg.format(message['sender_full_name'])
        )

    @classmethod
    def error(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return build_message(
            message, cls.error_msg.format(message['sender_full_name'])
        )

    @classmethod
    def exception(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return build_message(
            message, cls.exception_msg.format(message['sender_full_name'])
        )

    @classmethod
    def greet(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return build_message(
            message, cls.greet_msg.format(message['sender_full_name'])
        )

    @classmethod
    def ok(
        cls, message: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        return build_reaction(message, cls.ok_emoji)


def build_message(
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

    return (
        ResponseType.MESSAGE,
        dict(
            type = type,
            to = to,
            subject = subject,
            content = response
        )
    )


def build_reaction(
    message: Dict[str, Any],
    emoji: str
) -> Tuple[str, Dict[str, Any]]:
    return (
        ResponseType.EMOJI,
        dict(message_id = message['id'], emoji_name = emoji)
    )


# cf. https://github.com/zulip/python-zulip-api/issues/628
def get_file(client: Client, file_path: str) -> str:
    url: str = client.get_server_settings()['realm_uri'] + file_path

    data = urllib.parse.urlencode({ 'api_key': client.api_key })

    with urllib.request.urlopen(url + '?' + data) as file:
        content: str = file.read().decode()

    return content


def parse_filenames(s: str) -> List[str]:
    files: List[str] = []

    for file in re.findall(Regex.FILE, s, re.I):
        match: Optional[typing.Match[Any]] = re.match(
            Regex.FILE_CAPTURE, file, re.I
        )
        if match is None:
            continue
        files.append(match.group(1))

    return files

