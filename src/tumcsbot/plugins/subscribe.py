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
        subscribe streams <destination_stream_name> <stream_name>...
          or subscribe users <destination_stream_name> <user_name>...
          or subscribe user_emails <destination_stream_name> <user_email>...
          or subscribe all_users <destination_stream_name>
        """
    )
    description = cleandoc(
        """
        - `streams`
        Subscribe all subscribers of the given streams to the \
        destination stream.
        - `users`
        Subscribe all users with the specified names to the \
        destination stream.
        - `user_emails`
        Subscribe all users with the specified email addresses to the \
        destination stream. Note thet the email addresses need to match \
        the `delivery_email` field. Check if you and me are having \
        access to it. (In the Organization Settings of your Zulip \
        Server, the value of `Who can access user email addresses` needs \
        to be at least `Admins only`.)
        - `all_users`
        Subscribe all users to the destination stream.

        [administrator/moderator rights needed]

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
        subscribe user_emails "destination stream" "foo@bar.com" "user42@zulip.org"
        ````
        """
    )

    def __init__(self, plugin_context: PluginContext) -> None:
        super().__init__(plugin_context)
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand(
            'streams', args={
                'dest_stream': Regex.get_stream_name, 'streams': Regex.get_stream_name
            },
            greedy = True
        )
        self.command_parser.add_subcommand(
            'users', args={
                'dest_stream': Regex.get_stream_name,
                'users': lambda string: Regex.get_user_name(string, get_user_id = True)
            },
            greedy = True
        )
        self.command_parser.add_subcommand(
            'user_emails', args={
                'dest_stream': Regex.get_stream_name, 'user_emails': str,
            },
            greedy = True
        )
        self.command_parser.add_subcommand('all_users', args={'dest_stream': Regex.get_stream_name})

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        result: Optional[Tuple[str, CommandParser.Opts, CommandParser.Args]]

        result = self.command_parser.parse(message['command'])
        if result is None:
            return Response.command_not_found(message)
        command, _, args = result

        if command == 'streams':
            return self.subscribe_streams(message, args.dest_stream, args.streams)
        if command == 'users':
            return self.subscribe_users(message, args.dest_stream, args.users)
        if command == 'user_emails':
            return self.subscribe_user_emails(message, args.dest_stream, args.user_emails)
        if command == 'all_users':
            return self.subscribe_all_users(message, args.dest_stream)

        return Response.command_not_found(message)

    def subscribe_all_users(
        self,
        message: Dict[str, Any],
        dest_stream: str,
    ) -> Union[Response, Iterable[Response]]:
        if not self.client.user_is_privileged(message['sender_id']):
            return Response.admin_err(message)

        result: Dict[str, Any] = self.client.get_users()
        if result['result'] != 'success':
            return Response.error(message)
        user_ids: List[int] = [ user['user_id'] for user in result['members'] ]

        if not self.client.subscribe_users(user_ids, dest_stream):
            return Response.error(message)

        return Response.ok(message)

    def subscribe_streams(
        self,
        message: Dict[str, Any],
        dest_stream: str,
        streams: List[str]
    ) -> Union[Response, Iterable[Response]]:
        if not self.client.user_is_privileged(message['sender_id']):
            return Response.admin_err(message)

        failed: List[str] = []

        for stream in streams:
            if not self.client.subscribe_all_from_stream_to_stream(stream, dest_stream, None):
                failed.append(stream)

        if not failed:
            return Response.ok(message)

        return Response.build_message(
            message, 'Failed to subscribe the following streams:\n' + '\n'.join(failed)
        )

    def subscribe_user_emails(
        self,
        message: Dict[str, Any],
        dest_stream: str,
        user_emails: List[str]
    ) -> Union[Response, Iterable[Response]]:
        user_ids: Optional[List[int]] = self.client.get_user_ids_from_emails(user_emails)
        if user_ids is None:
            return Response.build_message(message, 'error: could not get the user ids.')

        if not self.client.subscribe_users(user_ids, dest_stream, allow_private_streams=True):
            return Response.error(message)

        return Response.ok(message)

    def subscribe_users(
        self,
        message: Dict[str, Any],
        dest_stream: str,
        users: List[Union[str, Tuple[str, Optional[int]]]]
    ) -> Union[Response, Iterable[Response]]:
        # First, get all the ids of the users whose ids we do not already know.
        user_ids: Optional[List[int]] = self.client.get_user_ids_from_display_names(map(
            lambda o: o[0] if isinstance(o, tuple) else o,
            filter(
                lambda o: isinstance(o, str) or (isinstance(o, tuple) and o[1] is None), users
            )
        ))
        if user_ids is None:
            return Response.build_message(message, 'error: could not get the user ids.')

        user_ids.extend(map(
            lambda t: cast(int, t[1]),
            filter(lambda o: isinstance(o, tuple) and isinstance(o[1], int), users)
        ))

        if not self.client.subscribe_users(user_ids, dest_stream):
            return Response.error(message)

        return Response.ok(message)
