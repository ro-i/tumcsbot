#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import importlib
import inspect
import logging
import os
import re
import typing

from inspect import cleandoc
from typing import Any, Callable, Dict, List, Tuple
from zulip import Client

from . import lib


class TumCSBot:
    '''
    This bot is currently especially intended for administrative tasks.
    It supports several commands which can be written to the bot using
    a private message or a message starting with @mentioning the bot.
    '''

    def __init__(
        self,
        zuliprc: str,
        debug: bool = False,
        logfile: str = None,
        **kwargs
    ) -> None:
        if debug:
            logging.basicConfig(level = logging.DEBUG, filename = logfile)
        else:
            logging.basicConfig(filename = logfile)

        self.client: Client = Client(config_file = zuliprc)

        self.commands: List[lib.Command] = self.get_all_commands_from_path(
            ['commands']
        )
        if debug:
            self.commands.extend(
                self.get_all_commands_from_path(['commands', 'debug'])
            )


    def process_message(self, message: Dict[str, Any]) -> None:
        if message['content'] == '':
            self.client.send_message(lib.Messages.greet(message))
            return

        response: Dict[str, Any] = None

        for command in self.commands:
            if command.is_responsible(message):
                response = command.func(self.client, message)
                break

        if response is None:
            response = lib.Messages.command_not_found(message)

        self.client.send_message(response)


    # Pathes are relative here! All 'path' elements will be concatenated
    # appropriately.
    # Do not only receive the Command classes, but also their usage
    # documentation string.
    def get_all_commands_from_path(self, path: List[str]) -> List[lib.Command]:
        commands: List[lib.Command] = []
        docs: List[Tuple[str, str]] = []

        # directory path to our package ('path/to/package')
        file_path: str = os.path.join(os.path.dirname(__file__), *path)
        # module path to our package ('path.to.package')
        module_path: str = '.'.join([__name__.rsplit('.', 1)[-1], *path])

        for entry in os.listdir(file_path):
            if not entry.endswith('.py') or entry.startswith('_'):
                continue
            # remove .py extension
            module_name: str = entry[:-3]
            # import from all modules the Command class
            module = importlib.__import__(
                '.'.join([module_path, module_name]), fromlist = ['Command']
            )
            command: lib.Command = module.Command()
            commands.append(command)
            # collect usage information
            if lib.Command in inspect.getmro(type(command)):
                docs.append(command.get_usage())

        lib.Helper.extend_command_docs(docs)

        return commands


    # important issues to consider:
    # 1)
    # - do not react on messages from the bot itself
    # cf. is_private_message_but_not_group_pm() in
    # https://github.com/zulip/python-zulip-api/blob/master/zulip_bots/zulip_bots/lib.py
    # 2)
    # - remove mention
    # cf. extract_query_without_mention() in
    # https://github.com/zulip/python-zulip-api/blob/master/zulip_bots/zulip_bots/lib.py
    def preprocess_and_check_if_responsible(
        self,
        message: Dict[str, Any]
    ) -> bool:
        if message['sender_id'] == self.client.get_profile()['user_id']:
            # message from self
            logging.debug("message from self")
            return False

        mention: str = '@**' + self.client.get_profile()['full_name'] + '**'

        if message['content'].startswith(mention):
            message['full_content'] = message['content']
            message['content'] = message['full_content'][len(mention):]
        elif message['type'] != 'private':
            # stream message without mention
            logging.debug("stream message without mention")
            return False

        return True


    def run(self, message: Dict[str, Any]) -> None:
        if not self.preprocess_and_check_if_responsible(message):
            return

        try:
            self.process_message(message)
        except Exception as e:
            logging.exception(e)
            lib.Messages.exception(message)


    def start(self) -> None:
        self.client.call_on_each_message(lambda msg: self.run(msg))

