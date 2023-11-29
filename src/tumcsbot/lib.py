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

import json
import re
import regex
import shlex
import sqlite3 as sqlite
from argparse import Namespace
from enum import Enum
from importlib import import_module
from inspect import cleandoc, getmembers, isclass, ismodule
from itertools import repeat
from os.path import isabs
from typing import Any, Callable, Final, Iterable, Type, TypeVar, cast


T = TypeVar("T")


LOGGING_FORMAT: Final[
    str
] = "%(asctime)s %(processName)s %(threadName)s %(module)s %(funcName)s: %(message)s"


class StrEnum(str, Enum):
    """Construct a string enum.

    See https://docs.python.org/3/library/enum.html#others.
    This own enum class is deprecated since Python 3.10 but is going
    to stay for some time in order to ensure compatibility.
    """


class MessageType(StrEnum):
    """Represent the type of a message.

    MESSAGE  Normal message as written by a human user.
    EMOJI    Emoji reaction on a message.
    NONE     No message.
    """

    MESSAGE = "message"
    EMOJI = "emoji"
    NONE = "none"


class Regex:
    """Some widely used regex methods."""

    _USER_ARGUMENT_PATTERN = regex.compile(r"@_?\*\*.*?\*\*\s*")
    _GROUP_ARGUMENT_PATTERN = regex.compile(r"@_?\*.*?\*\s*")
    _STREAM_ARGUMENT_PATTERN = regex.compile(r"#\*\*.*?\*\*\s*")
    _REACTION_ARGUMENT_PATTERN = regex.compile(r":.+:")

    _USER_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"data-user-id=\"(?P<id>\d+)\""
    )
    _STREAM_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"data-stream-id=\"(?P<id>\d+)\""
    )
    _USER_GROUP_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"data-user-group-id=\"(?P<id>\d+)\""
    )

    _ARGUMENT_PATTERN = regex.compile(
        r"(?P<args>@_?\*\*.*?\*\*\s*|@_\*.*?\*\s*|#\*\*.*?\*\*\s*|'(\\\\|\\.|.)*?'\s*|"
        + r'"(\\\\|\\.|.)*?"\s*'
        + r"|\S*\s*)*"
    )

    _ASTERISKS: Final[re.Pattern[str]] = re.compile(r"(?:\*\*)")
    _OPT_ASTERISKS: Final[re.Pattern[str]] = re.compile(r"(?:{}|)".format(_ASTERISKS))
    _EMOJI: Final[re.Pattern[str]] = re.compile(r"[^:]+")
    _EMOJI_AUTOCOMPLETED_CAPTURE: Final[re.Pattern[str]] = re.compile(
        r":({}):".format(_EMOJI.pattern)
    )
    _TOPIC: Final[re.Pattern[str]] = re.compile(r".+")
    # Note: Currently, there are no further restrictions on stream names posed
    # by Zulip. That is why we cannot enforce sensible restrictions here.
    _STREAM: Final[re.Pattern[str]] = re.compile(r".+")
    _STREAM_AUTOCOMPLETED_CAPTURE: Final[re.Pattern[str]] = re.compile(
        r"#{0}({1}){0}".format(_ASTERISKS.pattern, _STREAM.pattern)
    )
    _STREAM_AND_TOPIC_AUTOCOMPLETED_CAPTURE: Final[re.Pattern[str]] = re.compile(
        r"#{0}({1})>({2}){0}".format(_ASTERISKS.pattern, r"[^>]+", _TOPIC.pattern)
    )
    _USER: Final[re.Pattern[str]] = re.compile(r"[^\*\`\\\>\"\@]+")
    _USER_AUTOCOMPLETED_TEMPLATE: str = r"{0}({1}){0}".format(
        _ASTERISKS.pattern, _USER.pattern
    )
    _USER_AUTOCOMPLETED_ID_TEMPLATE: str = r"{0}({1})\|(\d+){0}".format(
        _ASTERISKS.pattern, _USER.pattern
    )
    _USER_LINKED_CAPTURE: Final[re.Pattern[str]] = re.compile(
        r"@_" + _USER_AUTOCOMPLETED_TEMPLATE
    )
    _USER_MENTIONED_CAPTURE: Final[re.Pattern[str]] = re.compile(
        r"@" + _USER_AUTOCOMPLETED_TEMPLATE
    )
    _USER_LINKED_ID_CAPTURE: Final[re.Pattern[str]] = re.compile(
        r"@_" + _USER_AUTOCOMPLETED_ID_TEMPLATE
    )
    _USER_MENTIONED_ID_CAPTURE: Final[re.Pattern[str]] = re.compile(
        r"@" + _USER_AUTOCOMPLETED_ID_TEMPLATE
    )

    @staticmethod
    def get_captured_string_from_match(
        match: re.Match[str] | None, capture_group_id: int
    ) -> str | None:
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
        cls, patterns: list[tuple[re.Pattern[str], list[int]]], string: str
    ) -> list[str] | None:
        """Extract a substring from a string.

        Walk through the provided patterns, find the first that matchs
        the given string (fullmatch) and extract the capture groups with
        the given ids.
        Return None if there has been no matching pattern.
        """
        for pattern, group_ids in patterns:
            match: re.Match[str] | None = pattern.fullmatch(string)
            if match is None:
                continue
            result: list[str | None] = [
                cls.get_captured_string_from_match(match, group_id)
                for group_id in group_ids
            ]
            return None if None in result else cast(list[str], result)

        return None

    @classmethod
    def get_emoji_name(cls, string: str) -> str | None:
        """Extract the emoji name from a string.

        Match the whole string.
        Emoji names may be of the following forms:
           <name>, :<name>:

        Leading/trailing whitespace is discarded.
        Return None if no match could be found.
        """
        result: list[str] | None = cls.get_captured_strings_from_pattern_or(
            [(cls._EMOJI_AUTOCOMPLETED_CAPTURE, [1]), (cls._EMOJI, [0])], string.strip()
        )
        return None if not result else result[0]

    @classmethod
    def get_stream_name(cls, string: str) -> str | None:
        """Extract the stream name from a string.

        Match the whole string.
        There are two cases handled here:
           abc -> abc, #**abc** -> abc

        Leading/trailing whitespace is discarded.
        Return None if no match could be found.
        """
        result: list[str] | None = cls.get_captured_strings_from_pattern_or(
            [(cls._STREAM_AUTOCOMPLETED_CAPTURE, [1]), (cls._STREAM, [0])],
            string.strip(),
        )
        return None if not result else result[0]

    @classmethod
    def get_stream_and_topic_name(cls, string: str) -> tuple[str, str | None] | None:
        """Extract the stream and the topic name from a string.

        Match the whole string and try to be smart:
           direct topic links: #**stream name>topic name**
                            -> (stream name, topic name)
           stream links: #**stream_name** -> (stream_name, None)
           plain stream names: stream_name -> (stream_name, None)

        Leading/trailing whitespace is discarded.
        Return None if no match could be found.

        Note that there may not occur a `>`-character in the stram name.
        This is related to the current behavior of the Zulip server and
        would need to be changed there.
        """
        result: list[str] | None = cls.get_captured_strings_from_pattern_or(
            [
                (cls._STREAM_AND_TOPIC_AUTOCOMPLETED_CAPTURE, [1, 2]),
                (cls._STREAM_AUTOCOMPLETED_CAPTURE, [1]),
                (cls._STREAM, [0]),
            ],
            string.strip(),
        )
        return (
            None if not result else (result[0], result[1] if len(result) > 1 else None)
        )

    @classmethod
    def get_user_name(
        cls, string: str, get_user_id: bool = False
    ) -> str | tuple[str, int | None] | None:
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
        result: list[str] | None = cls.get_captured_strings_from_pattern_or(
            [
                (cls._USER_MENTIONED_ID_CAPTURE, [1, 2]),
                (cls._USER_LINKED_ID_CAPTURE, [1, 2]),
                (cls._USER_MENTIONED_CAPTURE, [1]),
                (cls._USER_LINKED_CAPTURE, [1]),
                (cls._USER, [0]),
            ],
            string.strip(),
        )
        if not result:
            return None
        if not get_user_id:
            return result[0]
        if len(result) == 1:
            # We wanted the user ID, but did not find it.
            return (result[0], None)
        return (result[0], int(result[1]))

    @staticmethod
    def match_user_argument(s: str) -> str:
        if Regex._USER_ARGUMENT_PATTERN.match(s):
            return s
        else:
            raise ValueError()

    @staticmethod
    def match_group_argument(s: str) -> str:
        if (
            Regex._USER_ARGUMENT_PATTERN.match(s)
            or Regex._STREAM_ARGUMENT_PATTERN.match(s)
            or Regex._REACTION_ARGUMENT_PATTERN.match(s)
        ):
            raise ValueError()
        return s
        # todo: enable as soo as zulip api allows usergroups
        # if Regex._GROUP_ARGUMENT_PATTERN.match(s):
        #     return s
        # else:
        #     raise ValueError()

    @staticmethod
    def match_stream_argument(s: str) -> str:
        if Regex._STREAM_ARGUMENT_PATTERN.match(s):
            return s
        else:
            raise ValueError()

    @staticmethod
    def match_reaction_argument(s: str) -> str:
        if Regex._REACTION_ARGUMENT_PATTERN.match(s):
            return s
        else:
            raise ValueError()


class CommandParser:
    """A simple shell-like command line parser.

    This command line parser can operate in two modes:
    1. Only parse positional arguments, no special treating for
       arguments preceded by "-".
    2. Additionally parse short options (preceded by "-").
       - Options always precede positional arguments.
       - Options can take an (optional) argument which has to directly
         follow the option character (no space(s) in-between).
       - Options cannot be grouped (such as in "ls -lah").
       - The order of the options does not matter.
       - Contrary to positional arguments (except the last one), options
         are always optional.
       - The preceding "-" can be escaped by two backslashes in order to
         prevent the following token to be considered as option.
    """

    class Args(Namespace):
        pass

    class Opts(Namespace):
        pass

    class IllegalCommandParserState(Exception):
        pass

    def __init__(self) -> None:
        self.commands: dict[
            str,
            tuple[
                dict[str, Callable[[str], Any] | None],
                dict[str, Callable[[str], Any]],
                dict[str, Callable[[str], Any]],
                dict[str, Callable[[str], Any]],
                str | None,
            ],
        ] = {}

    def add_subcommand(
        self,
        name: str,
        opts: dict[str, Callable[[str], Any] | None] = {},
        args: dict[str, Callable[[str], Any]] = {},
        optionals: dict[str, Callable[[str], Any]] = {},
        greedy: dict[str, Callable[[str], Any]] = {},
        description: str | None = None,
    ) -> bool:
        """Add a subcommand to the parser.

        Arguments:
        ----------
        name       The name of the subcommand to add.
                   In case that a subcommand with the given name has
                   already been added to this parser, the previous one
                   will be overwritten.
        opts       The options to be expected as dict mapping the
                   option name to the function that should be used
                   to parse the option argument string. The function
                   may be None if the option should be considered as
                   simple flag not accepting any argument. In this case,
                   a boolean value is associated with this option in the
                   return value of parse() which indicates whether the
                   flag has been present or not.
                   In case that the option should support an optional
                   parameter, the function has to be able to accept an
                   empty string as argument.
                   (default: {})
        args       The arguments to be expected as dict mapping the
                   argument name to the function that should be used
                   to get the argument value from the command string.
                   (default: {})
                   Note that the order matters! (Since 3.7, the
                   insertion order of dict keys is preserved, see
                   https://mail.python.org/pipermail/python-dev/
                   2017-December/151283.html)
        optionals  The optional arguments to be expected as dict mapping the
                   argument name to the function that should be used
                   to get the argument value from the command string.
                   (default: {})
        greedy     The greedy arguments that can consume more than one argument to be expected
                   as dict mapping the argument name to the function that should be used
                   to get the argument value from the command string.
                   (default: {})
        description todo:
        If the given arguments would lead to a broken state of the
        parser, an IllegalCommandParserState exception is thrown.
        """
        if not name:
            raise self.IllegalCommandParserState()

        self.commands[name] = (opts, args, optionals, greedy, description)
        return True

    @staticmethod
    def strip_quotes(s: str) -> str:
        s = s.strip()
        if s.startswith("'") and s.endswith("'"):
            return s[1:-1].strip()
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1].strip()
        return s

    def parse(self, command: str | None) -> tuple[str, Opts, Args] | None:
        """Parse the given command string.

        Return the parsed subcommand together with its options and
        arguments. When reorder is True, arguments are matched to the argument based on structure and name instead of order.
        """
        result_opts: tuple[dict[str, Any], list[str]] | None

        if not command or not self.commands:
            return None

        # Split on tokens.

        matches_opt: regex.regex.Match[str] | None = Regex._ARGUMENT_PATTERN.match(
            command
        )
        if not matches_opt:
            return None

        matches: regex.regex.Match[str] = matches_opt
        try:
            tokens: list[str] | None = [
                bytes(e, "Latin-1").decode("unicode-escape")
                for e in [
                    CommandParser.strip_quotes(e)
                    for e in matches.capturesdict()["args"]
                ]
                if e
            ]
        except Exception as e:
            return None
        if not tokens or len(tokens) == 0:
            return None
        # Get the fitting subcommand.
        subcommand: str = tokens[0]
        if subcommand not in self.commands:
            return None

        opts, positional, optional, greedy, description = self.commands[subcommand]

        optiones_first = []
        arguments_last = []

        optarg = False
        for t in tokens[1:]:
            if optarg:
                optiones_first.append(t)
                optarg = False
            elif t.startswith("-") and not t.startswith("--"):
                optiones_first.append(t)
                opt: str = t.lstrip(" -")
                if opt in opts and opts[opt] is not None:
                    optarg = True
            else:
                arguments_last.append(t)

        result_opts = self._parse_opts(opts, optiones_first + arguments_last)

        if result_opts is None:
            return None

        options = result_opts[0]
        match_result = CommandParser._match_arguments(
            positional, optional, greedy, result_opts[1]
        )

        if match_result is None:
            return None

        matched_args, remainder = match_result

        if len(remainder) > 0:
            return None
        return (subcommand, self.Opts(**options), self.Args(**matched_args))

    def generate_syntax(self) -> str:
        subcommands_str = [
            CommandParser._format_subcommand(name, args)
            for name, args in self.commands.items()
        ]
        return "Available commands:\n" + "\n\tor ".join(subcommands_str)

    def generate_description(self) -> str:
        return "\n".join(
            [
                f"## `{name}`\n{desc}"
                for name, (_, _, _, _, desc) in self.commands.items()
            ]
        )

    @staticmethod
    def _format_subcommand(
        name: str,
        arguments: tuple[
            dict[str, Callable[[Any], Any] | None],
            dict[str, Callable[[str], Any]],
            dict[str, Callable[[str], Any]],
            dict[str, Callable[[str], Any]],
            str | None,
        ],
    ) -> str:
        options, positional, optional, greedy, _ = arguments

        optarg: Callable[[str], str] = (
            lambda x: " arg" if x in options and options[x] is not None else ""
        )
        optstr: Callable[[str], str] = lambda x: "-" if len(x) == 1 else "--"

        options_strs = [f"[{optstr(o)}{o}{optarg(o)}]" for o in options]
        optional_strs = [f"[{o}]" for o in optional]
        arg_strs = [f"<{p}>" for p in positional]
        greedy_strs = [f"[{g}...]" for g in greedy]

        args_str = " ".join(options_strs + optional_strs + arg_strs + greedy_strs)
        if len(args_str) > 0:
            return f"{name} {args_str}"
        return f"{name}"

    @staticmethod
    def _convert_argument(
        target_name: str,
        arg: str,
        converter: Callable[[str], Any],
        solution: dict[str, Any],
    ) -> bool:
        try:
            value = converter(arg)
        except Exception:
            return False
        if target_name in solution and isinstance(solution[target_name], type([])):
            solution[target_name].append(value)
        elif target_name not in solution or solution[target_name] is None:
            solution.update({target_name: value})
        else:
            return False
        return True

    @staticmethod
    def _match_argument_to_target(
        target: dict[str, Any],
        arg: str,
        solution: dict[str, Any],
    ) -> bool:
        for target_name, converter in target.items():
            if CommandParser._convert_argument(target_name, arg, converter, solution):
                return True
        return False

    @staticmethod
    def _match_arguments(
        positional: dict[str, Any],
        optional: dict[str, Any],
        greedy: dict[str, Any],
        args: list[str],
    ) -> tuple[dict[str, Any], list[str]] | None:
        solution: dict[str, Any] = {}
        for key in optional:
            solution.update({key: None})
        for key in greedy:
            solution.update({key: []})

        remainder = {i: a for i, a in enumerate(args)}

        for i, arg in enumerate(args):
            if CommandParser._match_argument_to_target(positional, arg, solution):
                remainder.pop(i)
                continue
            elif CommandParser._match_argument_to_target(optional, arg, solution):
                remainder.pop(i)
                continue
            elif CommandParser._match_argument_to_target(greedy, arg, solution):
                remainder.pop(i)
                continue

        for key in positional:
            if key not in solution:
                return None

        return solution, list(remainder.values())

    def _parse_opts(
        self,
        opts: dict[str, Callable[[Any], Any] | None],
        tokens: list[str],
    ) -> tuple[dict[str, Any], list[str]] | None:
        """Parse options from tokens.

        Return the parsed options together with their converted
        arguments and the non-option tokens.
        Return None on error.
        """
        index: int = 0
        result: dict[str, Any] = {}
        token: str = ""

        opts_len: int = len(opts)
        if not opts_len:
            return ({}, tokens)

        skip_next_token = False
        for index in range(len(tokens)):
            if skip_next_token:
                skip_next_token = False
                continue
            token = tokens[index]
            # Stop at the first non-option token.
            if token[0] != "-":
                break

            opt: str
            if token.startswith("-") and not token.startswith("--"):
                opt = token[1]
            else:
                opt = token[2:]

            if not opt in opts:
                # Invalid option.
                return None
            try:
                converter: Callable[[Any], Any] | None = opts[opt]
                if converter is not None:
                    optarg: str | None
                    if token.startswith("-") and not token.startswith("--"):
                        optarg = token[2:]
                    else:
                        optarg = tokens[index + 1] if index + 1 < len(tokens) else None
                        skip_next_token = True
                    result[opt] = converter(optarg)

                else:
                    result[opt] = True
            except:
                return None

        # Skip last option if there have been only options.
        if token and token[0] == "-":
            index += 1

        # Mark all non-existant flags as False and fill the values of
        # all the other options which were not specified on the given
        # command line with None.
        for opt in opts:
            if opt not in result:
                result[opt] = False if opts[opt] is None else None

        # Remove all backslash escapes for "-".
        # Note that split() in self.parse() already converted the two
        # backslashes to a single one!
        return (result, [t[1:] if t[0:2] == r"\-" else t for t in tokens[index:]])


class Conf:
    _get_sql: str = "select Value from Conf where Key = ?"
    _list_sql: str = "select * from Conf"
    _remove_sql: str = "delete from Conf where Key = ?"
    _update_sql: str = "replace into Conf values (?,?)"

    def __init__(self, db: "DB | None" = None) -> None:
        self._db: DB = DB() if db is None else db
        self._db.checkout_table("Conf", "(Key text primary key, Value text not null)")

    def get(self, key: str) -> str | None:
        result: list[tuple[Any, ...]] = self._db.execute(self._get_sql, key)
        if not result or len(result[0]) != 1:
            return None
        return cast(str, result[0][0])

    def list(self) -> list[tuple[str, str]]:
        return cast(list[tuple[str, str]], self._db.execute(self._list_sql))

    def remove(self, key: str) -> None:
        self._db.execute(self._remove_sql, key, commit=True)

    def set(self, key: str, value: str) -> None:
        """Set a key.

        Note that a potential exception from the database is simply
        passed through.
        """
        self._db.execute(self._update_sql, key, value, commit=True)


class DB:
    """Simple wrapper class to conveniently access a sqlite database."""

    path: str | None = None

    def __init__(
        self,
        *args: Any,
        db_path: str | None = None,
        read_only: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the database connection.

        Arguments:
        ----------
        db_path       Overrides the global default DB path.
        read_only     Opens a read-only database connection.

        *args and **kwargs are forwarded to sqlite.connect().
        """
        if not db_path:
            if not DB.path:
                raise ValueError("no path to database given")
            db_path = DB.path
        if not isabs(db_path):
            raise ValueError("path to database is not absolute")

        self.read_only: bool = read_only
        if self.read_only:
            kwargs.update(uri=True)
            self.connection = sqlite.connect(
                "file:" + db_path + "?mode=ro", *args, **kwargs
            )
        else:
            self.connection = sqlite.connect(db_path, *args, **kwargs)

        self.cursor = self.connection.cursor()
        # Switch on foreign key support.
        self.execute("pragma foreign_keys = on")

    def checkout_table(self, table: str, schema: str) -> None:
        """Create table if it does not already exist.

        Arguments:
        ----------
        table   name of the table
        schema  schema of the table in the form of
                    '(Name Type, ...)' --> valid SQL!

        Since this is only for internal use, screw SQL injections :)
        """
        self.execute(f"create table if not exists {table} {schema};", commit=True)

    def close(self) -> None:
        self.connection.close()

    def execute(
        self, command: str, *args: Any, commit: bool = False
    ) -> list[tuple[Any, ...]]:
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


class Response:
    """Some useful methods for building a response message."""

    privilege_err_msg: str = cleandoc(
        """
        Hi {}!
        You don't have sufficient privileges to execute this command.
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
    request_msg: str = cleandoc(
        """
        Hi {}!
        Your input would lead to the execution of the following command.
        Do you want to execute this? If yes, please react with :check: to this message.
        original_message_id: {}
        command: {}
        """
    )
    greet_msg: str = "Hi {}! :-)"
    ok_emoji: str = "ok"
    no_emoji: str = "cross_mark"

    def __init__(self, message_type: MessageType, response: dict[str, Any]) -> None:
        self.message_type: MessageType = message_type
        self.response: dict[str, Any] = response

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return json.dumps(
            {"message_type": str(self.message_type), "response": str(self.response)}
        )

    def is_none(self) -> bool:
        """Check whether this response has the MessageType 'None'."""
        return self.message_type == MessageType.NONE

    @classmethod
    def build_message(
        cls,
        message: dict[str, Any] | None,
        content: str,
        msg_type: str | None = None,
        to: str | int | list[int] | list[str] | None = None,
        subject: str | None = None,
    ) -> "Response":
        """Build a message.

        Arguments:
        ----------
        message    The message to respond to.
                       May be explicitely set to None. In this case,
                       'msg_type', 'to' (and 'subject' if 'msg_type'
                       is 'stream') have to be specified.
        content   The content of the response.
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
        if message is None and (
            msg_type is None or to is None or (msg_type == "stream" and subject is None)
        ):
            return cls.none()

        if message is not None:
            if msg_type is None:
                msg_type = message["type"]
            private: bool = msg_type == "private"

            if to is None:
                to = message["sender_email"] if private else message["stream_id"]

            if subject is None:
                subject = message["subject"] if not private else ""

        # 'subject' field is ignored for private messages
        # see https://zulip.com/api/send-message#parameter-topic
        return cls(
            MessageType.MESSAGE,
            {"type": msg_type, "to": to, "subject": subject, "content": content},
        )

    @classmethod
    def build_reaction(cls, message: dict[str, Any], emoji: str) -> "Response":
        """Build a reaction response.

        Arguments:
        ----------
        message   The message to react on.
        emoji     The emoji to react with.
        """
        return cls(
            MessageType.EMOJI, {"message_id": message["id"], "emoji_name": emoji}
        )

    @classmethod
    def build_reaction_from_id(cls, message_id: int, emoji: str) -> "Response":
        """Build a reaction response.

        Arguments:
        ----------
        message_id   The id of the message to react on.
        emoji        The emoji to react with.
        """
        return cls(MessageType.EMOJI, {"message_id": message_id, "emoji_name": emoji})

    @classmethod
    def build_request_msg(cls, message: dict[str, Any], command: str) -> "Response":
        """Build a message requesting whether the user wants to execute a given command.

        Arguments:
        ----------
        message     The message sent by the user.
        command     The command that would have been executed, given
                    the message.
        """
        return cls.build_message(
            message,
            cls.request_msg.format(message["sender_full_name"], message["id"], command),
        )

    @classmethod
    def privilege_err(cls, message: dict[str, Any]) -> "Response":
        """The user has not sufficient rights.

        Tell the user that they have not sufficient privileges for a
        certain command.
        """
        return cls.build_message(
            message, cls.privilege_err_msg.format(message["sender_full_name"])
        )

    @classmethod
    def command_not_found(cls, message: dict[str, Any]) -> "Response":
        """Tell the user that his command could not be found."""
        return cls.build_reaction(message, "question")

    @classmethod
    def error(cls, message: dict[str, Any]) -> "Response":
        """Tell the user that an error occurred."""
        return cls.build_message(
            message, cls.error_msg.format(message["sender_full_name"])
        )

    @classmethod
    def exception(cls, message: dict[str, Any]) -> "Response":
        """Tell the user that an exception occurred."""
        return cls.build_message(
            message, cls.exception_msg.format(message["sender_full_name"])
        )

    @classmethod
    def greet(cls, message: dict[str, Any]) -> "Response":
        """Greet the user."""
        return cls.build_message(
            message, cls.greet_msg.format(message["sender_full_name"])
        )

    @classmethod
    def ok(cls, message: dict[str, Any]) -> "Response":
        """Return an "ok"-reaction."""
        return cls.build_reaction(message, cls.ok_emoji)

    @classmethod
    def no(cls, message: dict[str, Any]) -> "Response":
        """Return a "no"-reaction."""
        return cls.build_reaction(message, cls.no_emoji)

    @classmethod
    def none(cls) -> "Response":
        """No response."""
        return cls(MessageType.NONE, {})


def get_classes_from_path(module_path: str, class_type: Type[T]) -> Iterable[Type[T]]:
    plugin_classes: list[Type[T]] = []
    for _, module in getmembers(import_module(module_path), ismodule):
        for _, value in getmembers(module, isclass):
            if value.__module__ == module.__name__ and issubclass(value, class_type):
                plugin_classes.append(value)  # pyright: ignore

    return plugin_classes


def is_bot_owner(user_id: int, db: DB | None = None) -> bool:
    """Checks whether the given user id belongs to the bot owner."""
    conf: Conf = Conf(db=db)
    return conf.get("bot_owner") == str(user_id)


def split(
    string: str,
    sep: str | None = None,
    exact_split: int = 0,
    discard_empty: bool = True,
    converter: list[Callable[[str], Any]] | None = None,
) -> list[Any] | None:
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
        instream=string, posix=True, punctuation_chars=False
    )
    # Do not handle comments.
    parser.commenters = ""
    # Split only on the characters specified as "whitespace".
    parser.whitespace_split = True
    if sep:
        parser.whitespace = sep

    try:
        result: list[Any] = list(map(str.strip, parser))
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
            exec_converter(conv, token) for (conv, token) in zip(converter, result)
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
    return re.fullmatch(stream_reg, stream_name, flags=re.I) is not None


def validate_and_return_regex(regex: str | None) -> str | None:
    """Validate a regex and return it.

    Return None in case the regex is invalid.
    """
    if regex is None:
        return None
    try:
        re.compile(regex)
        return regex
    except re.error:
        return None
