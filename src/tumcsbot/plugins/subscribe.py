#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Dict, Iterable, Optional, Tuple, Union

from tumcsbot.lib import CommandParser, Regex, Response
from tumcsbot.plugin import PluginContext, CommandPlugin


class Subscribe(CommandPlugin):
    plugin_name = 'subscribe'
    syntax = 'subscribe <stream_name1> <stream_name2> [description]'
    description = cleandoc(
        """
        Subscribe all subscribers of `stream_name1` to `stream_name2`.
        If `stream_name2` does not exist yet, create it with the \
        optional description.
        The stream names may be of the form `#<stream_name>` or \
        `#**<stream_name>**` (autocompleted stream name).
        Note that the bot must have the permissions to access both \
        streams.
        [administrator rights needed]
        """
    )

    def __init__(self, plugin_context: PluginContext, **kwargs: Any) -> None:
        super().__init__(plugin_context)
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand(
            'subscribe', {'from_stream': Regex.get_stream_name,
                          'to_stream': Regex.get_stream_name, 'desc': str},
            optional = True
        )

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        result: Optional[Tuple[str, CommandParser.Args]]

        if not self.client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return Response.admin_err(message)

        result = self.command_parser.parse('subscribe ' + message['command'])
        if result is None:
            return Response.command_not_found(message)
        _, args = result

        if not self.client.subscribe_all_from_stream_to_stream(
                args.from_stream, args.to_stream, args.desc):
            return Response.error(message)

        return Response.ok(message)
