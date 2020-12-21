#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""TUM CS Bot - a generic Zulip bot.

This bot is currently especially intended for administrative tasks.
It supports several commands which can be written to the bot using
a private message or a message starting with @mentioning the bot.

This module contains the main class TumCSBot and a (hopefully
temporary) helper class AutoSubscriber which subscribes the bot
to all public streams periodically.
"""

import importlib
import logging
import os
import threading

from time import sleep
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from .client import Client
from . import lib
from .command import Command, CommandInteractive


class AutoSubscriber(threading.Thread):
    """Keep the bot subscribed to all public streams.

    As the 'all_public_streams' parameter of the event API [1] does not
    seem to work properly, we need a work-around in order to be able to
    receive eventy for all public streams.

    [1] https://zulip.com/api/register-queue#parameter-all_public_streams
    """

    # interval in seconds to run periodically
    interval: int = 1800

    def __init__(self, client: Client) -> None:
        """Override the constructor of the parent class."""
        super().__init__()
        self.daemon = True
        self._client = client

    def run(self) -> None:
        """The thread's activity.

        Override the method of the parent class threading.Thread.
        """
        while True:
            try:
                self.subscribe()
            except Exception as e:
                logging.exception(e)
            sleep(AutoSubscriber.interval)

    def subscribe(self) -> None:
        """Do the actual subscribing."""
        result: Dict[str, Any]

        result = self._client.get_streams(
            include_public = True,
            include_web_public = True,
            include_subscribed = False,
            include_default = True
        )
        if result['result'] != 'success':
            logging.warning(
                'AutoSubscriber.run(): Cannot get list of all streams: '
                + str(result)
            )

        streams: List[Dict[str, Any]] = [
            { 'name': stream['name'] } for stream in result['streams']
        ]

        result = self._client.add_subscriptions(streams = streams)
        if result['result'] != 'success':
            logging.warning(
                'AutoSubscriber.run(): Cannot subscribe to some streams: '
                + str(result)
            )


class TumCSBot:
    """Main Bot class.

    Use start() to start the bot.
    """

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
        (self.commands, self.commands_interactive) = \
            self.get_commands_from_path(['commands'])
        # register events
        self.events: List[str] = self.get_events_from_commands(self.commands)
        self.events.extend(self.get_events_from_commands(self.commands_interactive))

        # start AutoSubscriber
        self._auto_subscriber = AutoSubscriber(self.client)
        self._auto_subscriber.start()

    def event_callback(self, event: Dict[str, Any]) -> None:
        """Simple callback wrapper for processing one event.

        Catches all Exceptions and logs them.
        """
        logging.debug('Received event: ' + str(event))
        try:
            self.process_event(event)
        except Exception as e:
            logging.exception(e)

    def get_commands_from_path(
        self,
        path: List[str]
    ) -> Tuple[List[Command], List[CommandInteractive]]:
        """Load all plugins (= commands) from "path".

        Pathes are relative here. All 'path' elements will be
        concatenated appropriately.
        Do not only receive the Command classes, but also their usage
        documentation string.client.get_profile()['user_id']:
        Prepare selfStats database entries.
        """
        commands: Tuple[List[Command], List[CommandInteractive]] = ([], [])
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
            # collect usage information and add to appropriate result list
            if isinstance(command, CommandInteractive):
                docs.append(command.get_usage())
                commands[1].append(command)
            else:
                commands[0].append(command)
            # check for corresponding row in database
            self._db.checkout_row(
                table = 'selfStats',
                key_column = 'Command',
                key = command.name,
                default_values = '("{}", 0, date())'.format(command.name)
            )

        lib.Helper.extend_command_docs(docs)

        return commands

    def get_events_from_commands(
        self,
        commands: Union[List[Command], List[CommandInteractive]]
    ) -> List[str]:
        """Get all events to listen to from the commands.

        Every command decides on its own which events it likes to receive.
        """
        events: Set[str] = set()

        for command in commands:
            for event in command.events:
                events.add(event)

        return list(events)

    def message_preprocess(
        self,
        message: Dict[str, Any]
    ) -> None:
        """Preprocess a message event.

        Check if the message is
          - a private message to the bot.
          - a message starting with mentioning the bot.
        If those conditions are met, add "interactive = True" to the
        message object and a "command" field containing the actual
        command without the mention.
        Rationale: instances of command.CommandInteractive are only
        interested in messages to the bot.
        """
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
        """Process one event."""
        command_palette: Sequence[Union[Command, CommandInteractive]] = self.commands
        interactive: bool = False
        responses: List[lib.Response] = []
        response: Union[lib.Response, List[lib.Response]]

        # Check if the message contains a command for the bot, i.e.
        # needs to be handled by an interactive command.
        if event['type'] == 'message':
            self.message_preprocess(event['message'])
            if event['message']['interactive']:
                command_palette = self.commands_interactive
                interactive = True

        for command in command_palette:
            if not command.is_responsible(self.client, event):
                continue

            response = command.func(self.client, event)
            if isinstance(response, list):
                responses.extend(response)
            else:
                responses.append(response)

            # update self stats
            self._db.execute(
                TumCSBot._update_selfStats_sql.format(command.name),
                commit = True
            )

            # allow only one interactive command
            if interactive:
                break

        # Inform the user if no suitable command could be found.
        # Only relevant for interactive commands.
        if not responses and interactive:
            responses.append(lib.Response.command_not_found(event['message']))

        if responses:
            self.send_responses(responses)

    def send_responses(self, responses: List[lib.Response]) -> None:
        """Send the given responses."""
        logging.debug('send_responses: ' + str(responses))

        for response in responses:
            if response.message_type == lib.MessageType.MESSAGE:
                self.client.send_message(response.response)
            elif response.message_type == lib.MessageType.EMOJI:
                self.client.add_reaction(response.response)

    def start(self) -> None:
        """Start the bot."""
        logging.debug('Listening on events: ' + str(self.events))
        self.client.call_on_each_event(
            lambda event: self.event_callback(event),
            event_types = self.events
        )
