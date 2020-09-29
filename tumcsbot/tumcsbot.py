#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import argparse
import logging
import re
import typing
import urllib
import zulip

from typing import Any, Callable, Dict, List, Tuple
from zulip import Client


description: str = '''
This bot is currently especially intended for administrative tasks.
It supports several commands which can be written to the bot using
a private message or a message starting with @mentioning the bot.
'''

command_not_found_msg: str = '''Hi {}!
Unfortunately, I currently cannot understand what you wrote to me.
Try "help" to get a glimpse of what I am capable of. :-)'''

exception_msg: str = '''Hi {}!
An exception occurred while executing your request.
Did you try to hack me? ;-)'''

give_help_msg: str = '''Hi {}!
Currently, I understand the following commands:

| command     | description
| ----------- | -----------
| **help**    | post this help as reply in the current context `*`
| **help me** | post this help as private message to the requesting user
| **source**  | post the link to the repository of my source code

`*` *i.e. as private message if you wrote a private message to me or as stream \
message otherwise*

Have a nice day! :-)
'''

subscribe_msg: str = '''Hi {}!
There was an error, I could not execute your command successfully.
Most likely, I do not have sufficient permissions in order to access one of \
the streams.'''


def build_message(message: Dict[str, Any], response: str, type: str = None,
                  to: str = None, subject: str = None) -> Dict[str, Any]:
    if type is None:
        type = message['type']
    private: bool = type == 'private'

    if to is None:
        to = message['sender_email'] if private else message['stream_id']

    if subject is None:
        subject = message['subject'] if not private else ''

    return dict(
        type = type,
        to = to,
        subject = subject,
        content = response
    )


# important issues to consider:
# 1)
# - do not react on messages from the bot itself
# cf. is_private_message_but_not_group_pm() in
# https://github.com/zulip/python-zulip-api/blob/master/zulip_bots/zulip_bots/lib.py
# 2)
# - remove mention
# cf. extract_query_without_mention() in
# https://github.com/zulip/python-zulip-api/blob/master/zulip_bots/zulip_bots/lib.py
def preprocess_and_check_if_responsible(client: Client,
                                        message: Dict[str, Any]) -> bool:
    if message['sender_id'] == client.get_profile()['user_id']:
        # message from self
        logging.debug("message from self")
        return False

    mention: str = '@**' + client.get_profile()['full_name'] + '**'

    if message['content'].startswith(mention):
        message['full_content'] = message['content']
        message['content'] = message['full_content'][len(mention):]
    elif message['type'] != 'private':
        # stream message without mention
        logging.debug("stream message without mention")
        return False

    return True


def eval_message(client: Client, message: Dict[str, Any]) -> None:
    response: Dict[str, Any] = None

    for (pattern, command, kwargs) in commands:
        if pattern.fullmatch(message['content']):
            response = command(client, message, **kwargs)
            break

    if response is None:
        if message['content'] == '':
            response = greet(client, message)
        else:
            response = command_not_found(client, message)

    client.send_message(response)


def exception_occurred(client: Client, message: Dict[str, Any],
                       **kwargs) -> Dict[str, Any]:
    client.send_message(build_message(
        message,
        exception_msg.format(message['sender_full_name'])
    ))


def get_file(client: Client, file_path: str) -> str:
    url: str = client.get_server_settings()['realm_uri'] + file_path

    data = urllib.parse.urlencode({ 'api_key': client.api_key })

    with urllib.request.urlopen(url + '?' + data) as file:
        content: str = file.read().decode()

    return content


def parse_filenames(s: str) -> List[str]:
    return [
        file_capture_pattern.match(file).group(1)
        for file in re.findall(file_regex, s, re.I)
    ]


def run(client: Client, message: Dict[str, Any]) -> None:
    if not preprocess_and_check_if_responsible(client, message):
        return

    try:
        eval_message(client, message)
    except Exception as e:
        logging.exception(e)
        exception_occurred(client, message)


##############################
## BEGIN: command functions ##
##############################

def cat(client: Client, message: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    file_path: str = parse_filenames(message['content'])[0]

    content: str = get_file(client, file_path)

    return build_message(message, '```\n{}\n```'.format(content))


def command_not_found(client: Client, message: Dict[str, Any],
                      **kwargs) -> Dict[str, Any]:
    return build_message(
        message,
        command_not_found_msg.format(
            message['sender_full_name'], message['content']
        )
    )


def debug_message(client: Client, message: Dict[str, Any],
                  **kwargs) -> Dict[str, Any]:
    # reset message content
    return build_message(message, '```\n{}\n```'.format(str(message)))


def debug_mode(client: Client, message: Dict[str, Any],
               **kwargs) -> Dict[str, Any]:
    return build_message(message, str(DEBUG_MODE))


def give_help(client: Client, message: Dict[str, Any], me = False,
              **kwargs) -> Dict[str, Any]:
    return build_message(
        message,
        give_help_msg.format(message['sender_full_name']),
        type = 'private' if me else None,
        to = message['sender_email'] if me else None
    )


def greet(client: Client, message: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    return build_message(
        message,
        'Hi {}! :-)'.format(message['sender_full_name'])
    )


def source(client: Client, message: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    return build_message(message, 'https://github.com/ro-i/tumcsbot')


def subscribe(client: Client, message: Dict[str, Any],
              **kwargs) -> Dict[str, Any]:
    (from_stream, to_stream) = subscribe_capture_pattern.match(
        message['content']).groups()

    subs: List[Dict[str, Any]] = client.get_subscribers(stream = from_stream)

    result: Dict[str, Any] = client.add_subscriptions(
        streams = [{'name': to_stream, 'description': 'my stream'}], # TODO
        principals = subs
    )

    if result['result'] == 'success':
        return build_message(message, 'OK')
    else:
        return build_message(message, subscribe_msg)

############################
## END: command functions ##
############################


def main() -> None:
    global DEBUG_MODE

    argument_parser = argparse.ArgumentParser(
        description = description,
        formatter_class = argparse.RawTextHelpFormatter
    )
    argument_parser.add_argument(
        'zuliprc', metavar = 'ZULIPRC', nargs = 1,
        help = 'zuliprc file containing the bot\'s configuration'
    )
    argument_parser.add_argument(
        '-d', '--debug', action = 'store_true',
        help = 'print debug information on the console'
    )
    argument_parser.add_argument(
        '-l', '--logfile', help = 'use LOGFILE for logging output'
    )
    args: argparse.Namespace = argument_parser.parse_args()

    if args.debug:
        logging.basicConfig(level = logging.DEBUG, filename = args.logfile)
        commands.extend(debug_commands)
        DEBUG_MODE = True
    else:
        logging.basicConfig(filename = args.logfile)

    client = Client(config_file = args.zuliprc[0])
    client.call_on_each_message(lambda msg: run(client, msg))


file_regex: str = '\[[^\[\]]*\]\([^\(\)]*\)'
stream_regex: str = '\w*'

file_capture_pattern: re.Pattern = re.compile(
    '\[[^\[\]]*\]\(([^\(\)]*)\)', re.I
)
subscribe_pattern: re.Pattern = re.compile(
    '\s*subscribe\s*{}\s*to\s*{}\s*'.format(stream_regex, stream_regex), re.I
)
subscribe_capture_pattern: re.Pattern = re.compile(
    '\s*subscribe\s*({})\s*to\s*({})\s*'.format(stream_regex, stream_regex),
    re.I
)

commands: List[Tuple[re.Pattern, Callable, Dict[str, Any]]] = [
    (re.compile('\s*help\s*me\s*', re.I), give_help, { 'me': True }),
    (re.compile('\s*help\s*', re.I), give_help, {}),
    (re.compile('\s*source\s*', re.I), source, {}),
    (subscribe_pattern, subscribe, {}),
]

debug_commands: List[Tuple[re.Pattern, Callable, Dict[str, Any]]] = [
    (re.compile('\s*debug\s*message.*', re.I), debug_message, {}),
    (re.compile('\s*debug\s*mode\s*', re.I), debug_mode, {}),
    (re.compile('\s*cat\s*' + file_regex + '\s*', re.I), cat, {}),
]

DEBUG_MODE: bool = False


if __name__ == '__main__':
    main()
