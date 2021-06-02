#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Collection of useful classes and functions.

Classes:
--------
MessageType     Enum describing the type of a message.
Regex           Some widely used regex methods.
CommandParser   A simple positional argument parser.
Conf            Manage the bot's configuration variables.
DB              Simple sqlite wrapper.
Response        Provide Response building methods.

Functions:
----------
split               Similar to the default split, but respects quotes.
stream_names_equal  Decide whether two stream names are equal.
"""

import re
import shlex
import sqlite3 as sqlite

from argparse import Namespace
from enum import Enum
from inspect import cleandoc
from itertools import repeat
from os.path import isabs
from typing import cast, Any, Callable, Dict, Final, List, Match, Optional, Pattern, Tuple, Union


LOGGING_FORMAT: str = (
    '%(asctime)s %(processName)s %(threadName)s %(module)s %(funcName)s: %(message)s'
)


class StrEnum(str, Enum):
    """Construct a string enum.

    See https://docs.python.org/3/library/enum.html#others.
    """


class MessageType(StrEnum):
    """Represent the type of a message.

    MESSAGE  Normal message as written by a human user.
    EMOJI    Emoji reaction on a message.
    NONE     No message.
    """

    MESSAGE: str = 'message'
    EMOJI: str = 'emoji'
    NONE: str = 'none'


class Regex:
    """Some widely used regex methods."""

    _ASTERISKS: Final[Pattern[str]] = re.compile(r'(?:\*\*)')
    _OPT_ASTERISKS: Final[Pattern[str]] = re.compile(
        r'(?:{}|)'.format(_ASTERISKS)
    )
    _EMOJI: Final[Pattern[str]] = re.compile(r'[^:]+')
    _EMOJI_AUTOCOMPLETED_CAPTURE: Final[Pattern[str]] = re.compile(
        r':({}):'.format(_EMOJI.pattern)
    )
    # Note: Currently, there are no further restrictions on stream names posed
    # by Zulip. That is why we cannot enforce sensible restrictions here.
    _STREAM: Final[Pattern[str]] = re.compile(r'.+')
    _STREAM_AUTOCOMPLETED_CAPTURE: Final[Pattern[str]] = re.compile(
        r'#{0}({1}){0}'.format(_ASTERISKS.pattern, _STREAM.pattern)
    )
    _USER: Final[Pattern[str]] = re.compile(r'[^\*\`\\\>\"\@]+')
    _USER_AUTOCOMPLETED_TEMPLATE: str = r'{0}({1}){0}'.format(
        _ASTERISKS.pattern, _USER.pattern
    )
    _USER_AUTOCOMPLETED_ID_TEMPLATE: str = r'{0}({1})\|(\d+){0}'.format(
        _ASTERISKS.pattern, _USER.pattern
    )
    _USER_LINKED_CAPTURE: Final[Pattern[str]] = re.compile(
        r'@_' + _USER_AUTOCOMPLETED_TEMPLATE
    )
    _USER_MENTIONED_CAPTURE: Final[Pattern[str]] = re.compile(
        r'@' + _USER_AUTOCOMPLETED_TEMPLATE
    )
    _USER_LINKED_ID_CAPTURE: Final[Pattern[str]] = re.compile(
        r'@_' + _USER_AUTOCOMPLETED_ID_TEMPLATE
    )
    _USER_MENTIONED_ID_CAPTURE: Final[Pattern[str]] = re.compile(
        r'@' + _USER_AUTOCOMPLETED_ID_TEMPLATE
    )

    @staticmethod
    def get_captured_string_from_match(
        match: Optional[Match[str]],
        capture_group_id: int
    ) -> Optional[str]:
        """Return the string of a capture group from a match.

        Return None if the match is None or if there is no capture group
        with the given index or if the expression of the capture group
        in the original regular expression could not be matched.
        """
        if match is None:
            return None
        try:
            return match.group(capture_group_id)
        except:
            return None

    @classmethod
    def get_captured_strings_from_pattern_or(
        cls,
        patterns: List[Tuple[Pattern[str], List[int]]],
        string: str
    ) -> Optional[List[str]]:
        """Extract a substring from a string.

        Walk through the provided patterns, find the first that matchs
        the given string (fullmatch) and extract the capture groups with
        the given ids.
        Return None if there has been no matching pattern.
        """
        for (pattern, group_ids) in patterns:
            match: Optional[Match[str]] = pattern.fullmatch(string)
            if match is None:
                continue
            result: List[Optional[str]] = [
                cls.get_captured_string_from_match(match, group_id)
                for group_id in group_ids
            ]
            return None if None in result else cast(List[str], result)

        return None

    @classmethod
    def get_emoji_name(cls, string: str) -> Optional[str]:
        """Extract the emoji name from a string.

        Match the whole string.
        Emoji names may be of the following forms:
           <name>, :<name>:

        Leading/trailing whitespace is discarded.
        Return None if no match could be found.
        """
        result: Optional[List[str]] = cls.get_captured_strings_from_pattern_or(
            [(cls._EMOJI_AUTOCOMPLETED_CAPTURE, [1]), (cls._EMOJI, [0])], string.strip()
        )
        return None if not result else result[0]

    @classmethod
    def get_stream_name(cls, string: str) -> Optional[str]:
        """Extract the stream name from a string.

        Match the whole string.
        There are two cases handled here:
           abc -> abc, #**abc** -> abc

        Leading/trailing whitespace is discarded.
        Return None if no match could be found.
        """
        result: Optional[List[str]] = cls.get_captured_strings_from_pattern_or(
            [(cls._STREAM_AUTOCOMPLETED_CAPTURE, [1]), (cls._STREAM, [0])], string.strip()
        )
        return None if not result else result[0]

    @classmethod
    def get_user_name(
        cls,
        string: str,
        get_user_id: bool = False
    ) -> Optional[Union[str, Tuple[str, Optional[int]]]]:
        """Extract the user name from a string.

        Match the whole string.
        There are five cases handled here:
           abc -> abc, @**abc** -> abc, @_**abc** -> abc
        and
           @**abc|1234** -> abc, @_**abc|1234** -> abc
           or - if get_user_id is True -
           @**abc|1234** -> (abc, 1234), @_**abc|1234** -> (abc, 1234)

        Leading/trailing whitespace is discarded.
        Return None if no match could be found.
        """
        result: Optional[List[str]] = cls.get_captured_strings_from_pattern_or(
            [
                (cls._USER_MENTIONED_ID_CAPTURE, [1, 2]),
                (cls._USER_LINKED_ID_CAPTURE, [1, 2]),
                (cls._USER_MENTIONED_CAPTURE, [1]),
                (cls._USER_LINKED_CAPTURE, [1]),
                (cls._USER, [0])
            ],
            string.strip()
        )
        if not result:
            return None
        if not get_user_id:
            return result[0]
        if len(result) == 1:
            # We wanted the user ID, but did not find it.
            return (result[0], None)
        return (result[0], int(result[1]))


class CommandParser:
    """A simple positional argument parser."""
    class Args(Namespace):
        pass

    def __init__(self) -> None:
        self.commands: Dict[str, Tuple[
            Dict[str, Callable[[str], Any]], bool, bool
        ]] = {}

    def add_subcommand(
        self,
        name: str,
        args: Dict[str, Callable[[str], Any]] = {},
        greedy: bool = False,
        optional: bool = False
    ) -> bool:
        """Add a subcommand to the parser.

        Arguments:
        ----------
        name       The name of the subcommand.
        args       The arguments to be expected as dict mapping the
                   argument name to the function that should be used
                   to get the argument value from the command string.
                   (default: {})
        greedy     The last argument should consume all remaining
                   tokens of the command string (if there are any).
                   Note that the return value for the last argument
                   will be a list in that case.
                   (default: False)
        optional   The last argument is optional.
                   (default: False)

        Note that the arguments will be passed in the order they
        appear in the list.
        """
        if not name:
            return False
        self.commands.update({name: (args, greedy, optional)})
        return True

    def parse(self, command: Optional[str]) -> Optional[Tuple[str, Args]]:
        """Parse the given command string."""
        result_args: Dict[str, Any] = {}

        if not command or not self.commands:
            return None

        # Split on (any) whitespace.
        tokens: Optional[List[str]] = split(command)
        if not tokens:
            return None

        # Get the fitting subcommand.
        subcommand: str = tokens[0]
        if subcommand not in self.commands:
            return None
        token_len: int = len(tokens[1:])

        args, greedy, optional = self.commands[subcommand]
        args_len: int = len(args)
        if ((args_len > token_len + (1 if optional else 0))
                or (not greedy and args_len < token_len)):
            return None

        name: Optional[str] = None
        converter: Optional[Callable[[str], Any]] = None

        # Iterate over expected arguments in the correct order.
        for token, (name, converter) in zip(tokens[1:], args.items()):
            try:
                result_args.update({name: converter(token)})
            except:
                return None

        # If greedy, consume the remaining tokens into the last argument.
        # Check, however, if there is an optional argument that is not present.
        if greedy and not (optional and args_len > token_len) and name and converter:
            try:
                rest_list: List[Any] = list(map(converter, tokens[args_len + 1:]))
                rest_list.insert(0, result_args[name])
            except:
                return None
            result_args[name] = rest_list

        return (subcommand, self.Args(**result_args))


class DB:
    """Simple wrapper class to conveniently access a sqlite database."""

    path: Optional[str] = None

    def __init__(self, *args: Any, read_only: bool = False, **kwargs: Any) -> None:
        """Initialize the database connection.

        Arguments:
        ----------
        read_only     Opens a read-only database connection.

        *args and **kwargs are forwarded to sqlite.connect().
        """
        if not DB.path:
            raise ValueError('no path to database given')
        if not isabs(DB.path):
            raise ValueError('path to database is not absolute')

        self.read_only: bool = read_only
        if self.read_only:
            kwargs.update(uri = True)
            self.connection = sqlite.connect('file:' + DB.path + '?mode=ro', *args, **kwargs)
        else:
            self.connection = sqlite.connect(DB.path, *args, **kwargs)

        self.cursor = self.connection.cursor()
        # Switch on foreign key support.
        self.execute('pragma foreign_keys = on')

    def checkout_table(self, table: str, schema: str) -> None:
        """Create table if it does not already exist.

        Arguments:
        ----------
        table   name of the table
        schema  schema of the table in the form of
                    '(Name Type, ...)' --> valid SQL!
        """
        if not self.table_exists(table):
            self.execute('create table {} {};'.format(table, schema), commit = True)

    def execute(
        self,
        command: str,
        *args: Any,
        commit: bool = False
    ) -> List[Tuple[Any, ...]]:
        """Execute an sql command.

        Execute an sql command, save the new database state
        (if commit == True) and return the result of the command.
        Forward 'args' to cursor.execute()
        """
        try:
            result: sqlite.Cursor = self.cursor.execute(command, args)
        except sqlite.Error as e:
            self.connection.rollback()
            raise e
        if commit and not self.read_only:
            self.connection.commit()
        return result.fetchall()

    def table_exists(self, table: str) -> bool:
        """Check if a table with the given name exists."""
        return bool(self.execute(
            'select * from sqlite_master where type = "table" and name = ?', table
        ))


class Response:
    """Some useful methods for building a response message."""

    admin_err_msg: str = cleandoc(
        """
        Hi {}!
        You need to be administrator of this organization in order to execute \
        this command.
        """
    )
    command_not_found_msg: str = cleandoc(
        """
        Hi {}!
        Unfortunately, I currently cannot understand what you wrote to me.
        Try "help" to get a glimpse of what I am capable of. :-)
        """
    )
    exception_msg: str = cleandoc(
        """
        Hi {}!
        An exception occurred while executing your request.
        Did you try to hack me? ;-)
        """
    )
    error_msg: str = cleandoc(
        """
        Sorry, {}, an error occurred while executing your request.
        """
    )
    greet_msg: str = 'Hi {}! :-)'
    ok_emoji: str = 'ok'
    no_emoji: str = 'cross_mark'

    def __init__(
        self,
        message_type: MessageType,
        response: Dict[str, Any]
    ) -> None:
        self.message_type: MessageType = message_type
        self.response: Dict[str, Any] = response

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return '({}, {})'.format(self.message_type, str(self.response))

    def is_none(self) -> bool:
        """Check whether this response has the MessageType 'None'."""
        return self.message_type == MessageType.NONE

    @classmethod
    def build_message(
        cls,
        message: Optional[Dict[str, Any]],
        content: str,
        msg_type: Optional[str] = None,
        to: Optional[Union[str, int, List[int], List[str]]] = None,
        subject: Optional[str] = None
    ) -> 'Response':
        """Build a message.

        Arguments:
        ----------
        message    The message to respond to.
                       May be explicitely set to None. In this case,
                       'msg_type', 'to' (and 'subject' if 'msg_type'
                       is 'stream') have to be specified.
        response   The content of the response.
        msg_type   Determine if the response should be a stream or a
                   private message. ('stream', 'private')
                   [optional]
        to         If it is a private message:
                       Either a list containing integer user IDs
                       or a list containing string email addresses.
                   If it is a stream message:
                       Either the name or the integer ID of a stream.
                   [optional]
        subject    The topic the message should be added to (only for
                   stream messages).
                   [optional]

        The optional arguments are inferred from 'message' if provided.

        Return a Response object.
        """
        if message is None and (msg_type is None
                                or to is None
                                or (msg_type == 'stream' and subject is None)):
            return cls.none()

        if message is not None:
            if msg_type is None:
                msg_type = message['type']
            private: bool = msg_type == 'private'

            if to is None:
                to = message['sender_email'] if private else message['stream_id']

            if subject is None:
                subject = message['subject'] if not private else ''

        # 'subject' field is ignored for private messages
        # see https://zulip.com/api/send-message#parameter-topic
        return cls(
            MessageType.MESSAGE,
            dict(**{
                'type': msg_type,
                'to': to,
                'subject': subject,
                'content': content
            })
        )

    @classmethod
    def build_reaction(
        cls,
        message: Dict[str, Any],
        emoji: str
    ) -> 'Response':
        """Build a reaction response.

        Arguments:
        ----------
        message   The message to react on.
        emoji     The emoji to react with.
        """
        return cls(
            MessageType.EMOJI,
            dict(message_id = message['id'], emoji_name = emoji)
        )

    @classmethod
    def build_reaction_from_id(
        cls,
        message_id: int,
        emoji: str
    ) -> 'Response':
        """Build a reaction response.

        Arguments:
        ----------
        message_id   The id of the message to react on.
        emoji        The emoji to react with.
        """
        return cls(
            MessageType.EMOJI,
            dict(message_id = message_id, emoji_name = emoji)
        )

    @classmethod
    def admin_err(
        cls, message: Dict[str, Any]
    ) -> 'Response':
        """The user has not sufficient rights.

        Tell the user that they have not administrator rights. Relevant
        for some commands intended to be exclusively used by admins.
        """
        return cls.build_message(
            message,
            cls.admin_err_msg.format(message['sender_full_name'])
        )

    @classmethod
    def command_not_found(
        cls, message: Dict[str, Any]
    ) -> 'Response':
        """Tell the user that his command could not be found."""
        return cls.build_reaction(message, 'question')

    @classmethod
    def error(
        cls, message: Dict[str, Any]
    ) -> 'Response':
        """Tell the user that an error occurred."""
        return cls.build_message(
            message, cls.error_msg.format(message['sender_full_name'])
        )

    @classmethod
    def exception(
        cls, message: Dict[str, Any]
    ) -> 'Response':
        """Tell the user that an exception occurred."""
        return cls.build_message(
            message, cls.exception_msg.format(message['sender_full_name'])
        )

    @classmethod
    def greet(
        cls, message: Dict[str, Any]
    ) -> 'Response':
        """Greet the user."""
        return cls.build_message(
            message, cls.greet_msg.format(message['sender_full_name'])
        )

    @classmethod
    def ok(
        cls, message: Dict[str, Any]
    ) -> 'Response':
        """Return an "ok"-reaction."""
        return cls.build_reaction(message, cls.ok_emoji)

    @classmethod
    def no(
        cls, message: Dict[str, Any]
    ) -> 'Response':
        """Return a "no"-reaction."""
        return cls.build_reaction(message, cls.no_emoji)

    @classmethod
    def none(cls) -> 'Response':
        """No response."""
        return cls(MessageType.NONE, {})


def split(
    string: str,
    sep: Optional[str] = None,
    exact_split: int = 0,
    discard_empty: bool = True,
    converter: Optional[List[Callable[[str], Any]]] = None
) -> Optional[List[Any]]:
    """Similar to the default split, but respects quotes.

    Basically, it's a wrapper for shlex.

    Arguments:
    ----------
    string         The string to split.
    sep            The delimiter to split on may be any string, but is
                   not supposed to contain quotation characters.
    exact_split    If the resulting list after splitting has not
                   exact_split elements, return None.
                   Values <= 0 will be ignored.
                   Note that exact_split is verified **after**
                   discarding empty strings (if discard_empty is true).
    discard_empty  Discard empty strings as splitting result (before
                   applying any converter).
    converter      A list of functions to be applied to each token.
                   If there are more token than converter, the last
                   converter will be used for every remaining token.
                   A converter may return None to indicate an error.

    Whitespace around the resulting tokens will be removed.
    Return None if there has been an error.
    """
    def exec_converter(conv: Callable[[str], Any], arg: str) -> Any:
        try:
            result: Any = conv(arg)
        except:
            return None
        return result

    if string is None:
        return None

    parser: shlex.shlex = shlex.shlex(
        instream = string, posix = True, punctuation_chars = False
    )
    # Do not handle comments.
    parser.commenters = ''
    # Split only on the characters specified as "whitespace".
    parser.whitespace_split = True
    if sep:
        parser.whitespace = sep

    try:
        result: List[Any] = list(map(str.strip, parser))
    except:
        return None

    if discard_empty:
        result = list(filter(lambda s: s, result))

    if exact_split > 0 and len(result) != exact_split:
        return None

    if converter:
        # Apply converter if present.
        len_result: int = len(result)
        len_converter: int = len(converter)

        if len_converter < len_result:
            converter.extend(repeat(converter[-1], len_result - len_converter))

        result = [
            exec_converter(conv, token)
            for (conv, token) in zip(converter, result)
        ]

    return result


def stream_names_equal(stream_name1: str, stream_name2: str) -> bool:
    """Decide whether two stream names are equal.

    Currently, Zulip considers stream names to be case insensitive.
    """
    return stream_name1.casefold() == stream_name2.casefold()


def stream_name_match(stream_reg: str, stream_name: str) -> bool:
    """Decide whether a stream regex matches a stream_name (fullmatch).

    Currently, Zulip considers stream names to be case insensitive.
    """
    return re.fullmatch(stream_reg, stream_name, flags = re.I) is not None
