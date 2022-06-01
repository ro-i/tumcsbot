#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Dict, Iterable, Union

from tumcsbot.lib import CommandParser, Response
from tumcsbot.plugin import PluginCommand, PluginThread


class Debug(PluginCommand, PluginThread):
    syntax = cleandoc(
        """
        debug
        """
    )
    description = cleandoc(
        """
        [administrator/moderator rights needed]
        """
    )

    def _init_plugin(self) -> None:
        super()._init_plugin()
        self.command_parser: CommandParser = CommandParser(self.plugin_name)
        self.command_parser.add_argument('args', metavar='STR', type=str, nargs='+')

    def handle_message(self, message: Dict[str, Any]) -> Union[Response, Iterable[Response]]:
        if not self.client().user_is_privileged(message['sender_id']):
            return Response.admin_err(message)

        result = self.command_parser.parse_args(message['command'])
        if result is None:
            result = self.command_parser.get_messages()
        else:
            result = str(result.args)

        return Response.build_message(message, result)
