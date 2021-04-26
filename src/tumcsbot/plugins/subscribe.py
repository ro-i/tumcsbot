#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import cast, Any, Dict, Iterable, List, Optional, Tuple, Union

from tumcsbot.lib import CommandParser, Regex, Response
from tumcsbot.plugin import PluginContext, CommandPlugin


class Subscribe(CommandPlugin):
    plugin_name = 'subscribe'
    syntax = cleandoc(
        """
        [beta]
        subscribe streams <destination_stream_name> <stream_names>...
          or subscribe users <destination_stream_name> <user_names>...
        """
    )
    description = cleandoc(
        """
        - `streams`
        Subscribe all subscribers of the given streams to the \
        destination stream.
        [administrator rights needed]
        - `users`
        Subscribe all given user names to the description stream.

        If the destination stream does not exist yet, it will be \
        automatically created (with an empty description).
        The stream names may be of the form `<stream_name>` or \
        `#**<stream_name>**` (autocompleted stream name).
        The user names may be of the form `<user_name>`, \
        `@**<user_name>**`, `@_**<user_name>**`, \
        `@**<user_name>|<user_id>**`, `@_**<user_name>|<user_id>**` \
        (autocompleted user names, possibly with the user id (an int)).

        **Stream or user names containing whitespace need to be quoted.**
        Note that the bot must have the permissions to invite users to \
        the destination stream. Also note that there may exist multiple \
        users with the same name and **all** of them will be subscribed \
        if you do not provide a user id for an ambiguous user name. If \
        you use Zulip's autocomplete feature for user names, the user \
        id is automatically added if neccessary.

        ````text
        subscribe streams "destination stream" "#**test stream**" mystream
        ````
        """
    )

    def __init__(self, plugin_context: PluginContext) -> None:
        super().__init__(plugin_context)
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand(
            'streams', {'dest_stream': Regex.get_stream_name, 'streams': Regex.get_stream_name},
            greedy = True
        )
        self.command_parser.add_subcommand(
            'users', {
                'dest_stream': Regex.get_stream_name,
                'users': lambda string: Regex.get_user_name(string, get_user_id = True)
            },
            greedy = True
        )

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        result: Optional[Tuple[str, CommandParser.Args]]

        result = self.command_parser.parse(message['command'])
        if result is None:
            return Response.command_not_found(message)
        command, args = result

        if command == 'streams':
            if not self.client.get_user_by_id(message['sender_id'])['user']['is_admin']:
                return Response.admin_err(message)

            for stream in args.streams:
                if not self.client.subscribe_all_from_stream_to_stream(
                        stream, args.dest_stream, None):
                    return Response.error(message)
        elif command == 'users':
            user_ids: Optional[List[int]] = self.client.get_user_ids_from_display_names(
                filter(lambda o: isinstance(o, str), args.users)
            )
            if user_ids is None:
                return Response.build_message(message, 'error: could not get the user ids.')

            user_ids.extend(map(
                lambda t: cast(int, t[1]), filter(lambda o: isinstance(o, tuple), args.users)
            ))

            if not self.client.subscribe_users(user_ids, args.dest_stream):
                return Response.error(message)

        return Response.ok(message)
