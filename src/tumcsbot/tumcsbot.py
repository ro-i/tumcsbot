#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import importlib
import logging
import os

from typing import Any, Dict, List, Optional, Set, Tuple

from .client import Client
from . import lib
from .command import Command, CommandInteractive


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

        # init Zulip client ...
        self.client: Client = Client(config_file = zuliprc)
        # ... and already calculate some constants we need later in
        # preprocess_and_check_if_responsible()
        self._client_id: int = self.client.get_profile()['user_id']
        self._client_mention: str = '@**{}**'.format(
            self.client.get_profile()['full_name']
        )
        self._client_mention_len: int = len(self._client_mention)
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
        self.commands: List[Command] = self.get_commands_from_path(['commands'])
        # register events
        self.events: List[str] = self.get_events_from_commands(self.commands)


    def get_commands_from_path(self, path: List[str]) -> List[Command]:
        '''
        Load all plugins (= commands) from "path".
        Pathes are relative here. All 'path' elements will be
        concatenated appropriately.
        Do not only receive the Command classes, but also their usage
        documentation string.client.get_profile()['user_id']:
        Prepare selfStats database entries.
        '''
        commands: List[Command] = []
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
            command: Command = module.Command()
            commands.append(command)
            # collect usage information
            if isinstance(command, CommandInteractive):
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


    def message_preprocess(
        self,
        message: Dict[str, Any]
    ) -> None:
        '''
        Check if the message is
          - a private message to the bot.
          - a message starting with mentioning the bot.
        If those conditions are met, add "interactive = True" to the
        message object and a "command" field containing the actual
        command without the mention.
        Rationale: instances of command.CommandInteractive are only
        interested in messages to the bot.
        '''
        interactive: bool = False

        if message['sender_id'] == self._client_id:
            # message from the bot itself
            pass
        elif message['content'].startswith(self._client_mention):
            # message starts with mentioning the bot; remove the mention
            message['command'] = message['content'][self._client_mention_len:]
            interactive = True
        elif message['type'] == 'private':
            # private message to the bot (no mention needed)
            message['command'] = message['content']
            interactive = True

        message['interactive'] = interactive


    def process_event(self, event: Dict[str, Any]) -> None:
        response: Optional[Tuple[str, Dict[str, Any]]] = None

        if event['type'] == 'message':
            self.message_preprocess(event['message'])

        for command in self.commands:
            if command.is_responsible(self.client, event):
                response = command.func(self.client, event)
                self._db.execute(
                    TumCSBot._update_selfStats_sql.format(command.name),
                    commit = True
                )
                break

        if response is None:
            if event['type'] == 'message' and event['message']['interactive']:
                response = lib.Response.command_not_found(event['message'])
            else:
                return

        self.send_response(response)


    def get_events_from_commands(self, commands: List[Command]) -> List[str]:
        '''
        Every command decides on its own which events it likes to receive.
        '''
        events: Set[str] = set()

        for command in commands:
            for event in command.events:
                events.add(event)

        return list(events)


    def run(self, event: Dict[str, Any]) -> None:
        logging.debug('Received event: ' + str(event))
        try:
            self.process_event(event)
        except Exception as e:
            logging.exception(e)


    def send_response(self, response: Tuple[str, Dict[str, Any]]) -> None:
        logging.debug('send_response: ' + str(response))

        if response[0] == lib.MessageType.MESSAGE:
            self.client.send_message(response[1])
        elif response[0] == lib.MessageType.EMOJI:
            self.client.add_reaction(response[1])


    def start(self) -> None:
        logging.debug('Listening on events: ' + str(self.events))
        self.client.call_on_each_event(
            lambda event: self.run(event),
            event_types = self.events
        )
