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
from typing import Any, Callable, Dict, List, Optional, Tuple
from zulip import Client

from . import lib


class TumCSBot:
    '''
    This bot is currently especially intended for administrative tasks.
    It supports several commands which can be written to the bot using
    a private message or a message starting with @mentioning the bot.
    '''
    _update_selfStats_sql = (
        'update SelfStats set Count = Count + 1 where Command = "{}"'
    )

    def __init__(
        self,
        zuliprc: str,
        db_path: str,
        debug: bool = False,
        logfile: Optional[str] = None,
        **kwargs: str
    ) -> None:
        if debug:
            logging.basicConfig(level = logging.DEBUG, filename = logfile)
        else:
            logging.basicConfig(filename = logfile)

        # init Zulip client
        self.client: Client = Client(config_file = zuliprc)
        # init database handler
        lib.DB.path = db_path
        # get an own database connection
        self._db = lib.DB()
        # check for database table
        self._db.checkout_table(
            table = 'selfStats',
            schema = '(Command varchar, Count integer, Since varchar)'
        )

        # register plugins
        self.commands: List[lib.Command] = self.get_all_commands_from_path(
            ['commands']
        )


    def process_message(self, message: Dict[str, Any]) -> None:
        if message['content'] == '':
            self.send_response(lib.Response.greet(message))
            return

        response: Optional[Tuple[str, Dict[str, Any]]] = None

        for command in self.commands:
            if command.is_responsible(message):
                response = command.func(self.client, message)
                self._db.execute(
                    TumCSBot._update_selfStats_sql.format(command.name)
                )
                break

        if response is None:
            response = lib.Response.command_not_found(message)

        self.send_response(response)


    def get_all_commands_from_path(self, path: List[str]) -> List[lib.Command]:
        '''
        Load all plugins (= commands) from "path".
        Pathes are relative here. All 'path' elements will be
        concatenated appropriately.
        Do not only receive the Command classes, but also their usage
        documentation string.
        Prepare selfStats database entries.
        '''
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
            # check for corresponding row in database
            self._db.checkout_row(
                table = 'selfStats',
                key_column = 'Command',
                key = command.name,
                default_values = '("{}", 0, date())'.format(command.name)
            )

        lib.Helper.extend_command_docs(docs)

        return commands


    def preprocess_and_check_if_responsible(
        self,
        message: Dict[str, Any]
    ) -> bool:
        '''
        Check if I should handle the message given by the argument
        "message" and remove the starting mention to me if necessary.

        Important issues to consider:
          1) do not react on messages from the bot itself
             cf. is_private_message_but_not_group_pm() in
          https://github.com/zulip/python-zulip-api/blob/master/zulip_bots/zulip_bots/lib.py
          2) remove mention
             cf. extract_query_without_mention() in
          https://github.com/zulip/python-zulip-api/blob/master/zulip_bots/zulip_bots/lib.py
        '''
        my_id: int = self.client.get_profile()['user_id']

        if message['sender_id'] == my_id:
            logging.debug('received message from self')
            return False

        mention: str = '@**' + self.client.get_profile()['full_name'] + '**'

        if message['content'].startswith(mention):
            message['full_content'] = message['content']
            message['content'] = message['full_content'][len(mention):]
            logging.debug('received message with mention')
            return True
        elif message['type'] != 'private':
            logging.debug('received stream message without mention '
                          'or not starting with mention')
            return False

        # Now, I know that the message is private and does not start with
        # mentioning me. Check if it is a direct message to me.
        for recipient in message['display_recipient']:
            if recipient['id'] == my_id:
                logging.debug('received private message')
                return True

        logging.debug('received private message not starting with mention')
        return False


    def run(self, message: Dict[str, Any]) -> None:
        if not self.preprocess_and_check_if_responsible(message):
            return

        try:
            self.process_message(message)
        except Exception as e:
            logging.exception(e)
            self.send_response(lib.Response.exception(message))


    def send_response(self, response: Tuple[str, Dict[str, Any]]) -> None:
        logging.debug('send_response: ' + str(response))

        if response[0] == lib.ResponseType.MESSAGE:
            self.client.send_message(response[1])
        elif response[0] == lib.ResponseType.EMOJI:
            self.client.add_reaction(response[1])


    def start(self) -> None:
        self.client.call_on_each_message(lambda msg: self.run(msg))

