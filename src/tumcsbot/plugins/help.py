#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, Union

from tumcsbot.lib import Response
from tumcsbot.plugin import PluginContext, CommandPlugin


class Help(CommandPlugin):
    """Provide a help command plugin."""

    plugin_name = 'help'
    syntax = 'help'
    description = 'Post a help message to the requesting user.'
    _help_overview_template: str = cleandoc(
        """
        Hi {}!

        Use `help <command name>` to get more information about a \
        certain command.
        Please consider that my command line parsing is comparable to \
        the POSIX shell. So in order to preserve arguments containing \
        whitespace characters from splitting, they need to be quoted. \
        Special strings such as regexes containing backslash sequences \
        may require single quotes instead of double quotes.

        Currently, I understand the following commands:

        {}

        Have a nice day! :-)
        """
    )

    def __init__(self, plugin_context: PluginContext) -> None:
        super().__init__(plugin_context)
        self.help_info: List[Tuple[str, str, str]] = self._get_help_info(
            plugin_context.command_plugin_classes
        )

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        command: str = message['command'].strip()
        if not command:
            return self._help_overview(message)
        return self._help_command(message, command)

    @staticmethod
    def _format_description(description: str) -> str:
        """Format the usage description of a command."""
        # Remove surrounding whitespace.
        description.strip()
        return description

    @staticmethod
    def _format_syntax(syntax: str) -> str:
        """Format the syntax string of a command."""
        return '```text\n' + syntax.strip() + '\n```\n'

    def _get_help_info(
        self,
        commands: List[Type[CommandPlugin]]
    ) -> List[Tuple[str, str, str]]:
        """Get help information from each command.

        Return a list of tuples (command name, syntax, description).
        """
        result: List[Tuple[str, str, str]] = []

        for command in commands:
            name: str = command.plugin_name
            syntax_data, description_data = command.get_usage()
            syntax: str = self._format_syntax(syntax_data)
            description: str = self._format_description(description_data)
            result.append((name, syntax, description))

        # Sort by name.
        return sorted(result, key = lambda tuple: tuple[0])

    def _help_command(
        self,
        message: Dict[str, Any],
        command: str
    ) -> Union[Response, Iterable[Response]]:
        info_tuple: Optional[Tuple[str, str, str]] = None

        for ituple in self.help_info:
            if ituple[0] == command:
                info_tuple = ituple
                break
        if info_tuple is None:
            return Response.command_not_found(message)

        help_message: str = '\n'.join(info_tuple[1:])

        return Response.build_message(
            message, help_message, msg_type = 'private', to = message['sender_email']
        )

    def _help_overview(
        self,
        message: Dict[str, Any]
    ) -> Union[Response, Iterable[Response]]:
        # Get the command names.
        help_message: str = '\n'.join(map(lambda tuple: '- ' + tuple[0], self.help_info))

        return Response.build_message(
            message,
            self._help_overview_template.format(message['sender_full_name'], help_message),
            msg_type = 'private',
            to = message['sender_email']
        )
