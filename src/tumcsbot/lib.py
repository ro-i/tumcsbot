#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing
import urllib.parse
import urllib.request

from abc import ABC, abstractmethod
from inspect import cleandoc
from typing import Any, Dict, List, Optional, Tuple
from zulip import Client


######################
## Begin: constants ##
######################

class Pattern:
    FILE_CAPTURE: typing.Pattern[str] = re.compile(
        '\[[^\[\]]*\]\(([^\(\)]*)\)', re.I
    )


class Regex:
    FILE: str = '\[[^\[\]]*\]\([^\(\)]*\)'
    OPT_ASTERISKS: str = '(?:\*\*|)'
    STREAM: str = '[^*#]*'


class ResponseType:
    MESSAGE: str = 'message'
    EMOJI: str = 'emoji'
    NONE: str = 'none'

######################
## End: constants ##
######################


class BaseCommand(ABC):

    @abstractmethod
    def __init__(self, **kwargs: Any) -> None:
        self._pattern: typing.Pattern[str]
        pass

    @abstractmethod
    def func(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Tuple[str, Dict[str, Any]]:
        '''
        Process request and return a tuple containing the type of the
        response (cf. Response) and the response request itself.
        '''
        pass

    def is_responsible(self, message: Dict[str, Any]) -> bool:
        return self._pattern.fullmatch(message['content']) is not None


class Command(BaseCommand):
    syntax: str
    description: str

    def get_usage(self) -> Tuple[str, str]:
        '''
        Return a tuple containing:
        - the syntax of the command
        - its description.
        Example:
            ('command [OPTION]... [FILE]...',
            'this command does a lot of interesting stuff...')
        The description may contain Zulip-compatible markdown.
        Newlines in the description will be removed.
        The syntax string is formatted as code (using backticks) automatically.
        '''
        return (type(self).syntax, type(self).description)


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
        match: Optional[typing.Match[Any]] = Pattern.FILE_CAPTURE.match(file)
        if match is None:
            continue
        files.append(match.group(1))

    return files

