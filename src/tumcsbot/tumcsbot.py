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

import atexit
import importlib
import logging
import os
import signal

from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

from .client import Client
from . import lib
from .command import Command, CommandDaemon, CommandInteractive, CommandOneShot


CommandType = Union[CommandDaemon, CommandInteractive, CommandOneShot]


def sigterm_handler(signum: int, frame: Any) -> None:
    raise SystemExit()


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
        self.commands_daemon: List[CommandType] = []
        self.commands_interactive: List[CommandType] = []
        self.commands_oneshot: List[CommandType] = []

        # Register exit handler.
        atexit.register(self.exit_handler)
        signal.signal(signal.SIGTERM, sigterm_handler)

        # Init logging.
        logging_level: int = logging.WARNING
        if debug:
            logging_level = logging.DEBUG
        logging.basicConfig(
            format='%(asctime)s %(message)s', level = logging_level, filename = logfile
        )

        # Init Zulip client ...
        self.client: Client = Client(config_file = zuliprc)
        # ... and already calculate some constants we need later in
        # preprocess_and_check_if_responsible().
        self._client_mention: str = '@**{}**'.format(
            self.client.get_profile()['full_name']
        )
        self._client_mention_len: int = len(self._client_mention)
        # Init database handler.
        lib.DB.path = db_path
        # Get an own database connection.
        self._db = lib.DB()
        # Check for database table.
        self._db.checkout_table(
            table = 'selfStats',
            schema = '(Command varchar, Count integer, Since varchar)'
        )

        # Register plugins.
        self.commands_daemon = self.get_commands_from_path(
            ['commands'], CommandDaemon, **{'zuliprc': zuliprc}
        )
        # The daemon plugins need to have their own client.
        self.commands_interactive = self.get_commands_from_path(
            ['commands'], CommandInteractive
        )
        self.commands_oneshot = self.get_commands_from_path(
            ['commands'], CommandOneShot
        )
        # Register events.
        self.events: List[str] = self.get_events_from_commands(self.commands_oneshot)
        self.events.extend(self.get_events_from_commands(self.commands_interactive))

    def exit_handler(self) -> None:
        """Terminate all attached processes.

        Needs to be idempotent."""
        for process in self.commands_daemon:
            if not process.is_alive():
                continue
            process.terminate()
            process.join()

    def event_callback(self, event: Dict[str, Any]) -> None:
        """Simple callback wrapper for processing one event.

        Catch all Exception objects and logs them.
        Note: Exceptions inheriting directly from BaseException (such as
        SystemExit) are not catched (and must not be catched!).
        """
        logging.debug('Received event: ' + str(event))
        try:
            self.process_event(event)
        except Exception as e:
            logging.exception(e)

    def get_commands_from_path(
        self,
        path: List[str],
        superclass: Any,
        **kwargs: Any
    ) -> List[CommandType]:
        """Load all plugins (= commands) from "path".

        Pathes are relative here. All 'path' elements will be
        concatenated appropriately.
        Load only those plugins which are subclasses of 'superclass'.
        Pass 'kwargs' to the __init__ method of the plugins.

        Do not only receive the Command objects, but also their usage
        documentation string if they are subclasses of
        CommandInteractive.
        Prepare selfStats database entries.
        """
        commands: List[CommandType] = []
        command: CommandType
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
            if not issubclass(module.Command, superclass):
                continue
            command = module.Command(**kwargs)
            # Neither docs nor selfStats entries have to be prepared for
            # daemon plugins.
            if not isinstance(command, CommandDaemon):
                # collect usage information and add to appropriate result list
                if isinstance(command, CommandInteractive):
                    docs.append(command.get_usage())
                # check for corresponding row in database
                self._db.checkout_row(
                    table = 'selfStats',
                    key_column = 'Command',
                    key = command.name,
                    default_values = '("{}", 0, date())'.format(command.name)
                )
            commands.append(command)
            # Start plugin.
            logging.debug('Start command ' + command.name)
            command.start()

        lib.Helper.extend_command_docs(docs)

        return commands

    def get_events_from_commands(
        self,
        commands: List[CommandType]
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

        if message['sender_id'] == self.client.id:
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
        # Command palette defaults to the one-shot commands.
        command_palette: List[CommandType] = self.commands_oneshot
        # As a result, interactive is false.
        interactive: bool = False
        responses: List[Union[lib.Response, Iterable[lib.Response]]] = []

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

            # As multiple commands may be executed for one event, catch
            # the exceptions of one command
            try:
                responses.append(command.func(self.client, event))

                # update self stats
                self._db.execute(
                    TumCSBot._update_selfStats_sql.format(command.name),
                    commit = True
                )
            except Exception as e:
                logging.exception(e)

            # Allow only one interactive command.
            if interactive:
                break

        # Inform the user if no suitable command could be found.
        # Only relevant for interactive commands.
        if not responses and interactive:
            responses.append(lib.Response.command_not_found(event['message']))

        if responses:
            lib.send_responses(self.client, responses)

    def start(self) -> None:
        """Start the bot."""
        logging.debug('Listening on events: ' + str(self.events))
        self.client.call_on_each_event(
            lambda event: self.event_callback(event),
            event_types = self.events,
            all_public_streams = True
        )
