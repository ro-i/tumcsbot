#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import logging

from inspect import cleandoc
from typing import cast, Any, Callable, Dict, Iterable, List, Optional, Pattern, Set, \
    Tuple, Union
from sqlite3 import IntegrityError

from tumcsbot.lib import CommandParser, DB, Regex, Response
from tumcsbot.plugin import PluginContext, CommandPlugin


class Group(CommandPlugin):
    plugin_name = 'group'
    events = ['message', 'reaction']
    syntax = cleandoc(
        """
        group (un)subscribe <group_id>
          or group add <group_id> <emoji>
          or group remove <group_id>
          or group add_streams <group_id> <stream_pattern>...
          or group remove_streams <group_id> <stream_pattern>...
          or group list
          or group claim <group_id>
          or group unclaim <group_id> <message_id>
          or group announce
          or group unannounce <message_id>
        """
    )
    description = cleandoc(
        """
        Manage stream groups using identifiers.
        **Note that "streams" here only cover public streams!**

        Subscribe to / unsubscribe from a group using \
        `group (un)subscribe`.

        Create/remove a stream group with `group add`/`group remove` by \
        specifing an identifier and an emoji. Note that removing a stream \
        group has no other consequences than removing the associations \
        in the bot!
        Use `group add_streams` to add a newline-separated list of \
        regexes representing the streams which should be considered as \
        part of this stream group. Use `group remove_streams` to do the \
        opposite. Note that you have to quote the regexes!
        With `group list`, you get a list of all group ids with their \
        associated stream patterns.
        Use `group claim` to make a message "special" for a given \
        group. If a user reacts on a "special" message with the emoji \
        that is assigned to the group the message is special for, the \
        user gets subscribed to all streams belonging to this group. \
        A message with the `group claim` command in the first line may \
        also contain arbitrary other text.
        Finally, `group announce` triggers a message from the bot \
        which will be "special" for all groups and in which the bot \
        will maintain a list of all groups.

        [administrator rights needed except for (un)subscribe]
        """
    )
    _announcement_msg: str = cleandoc(
        """
        Hi! :smile:

        I have the pleasure to announce some stream groups here.
        You may subscribe to a stream group in order to be automatically \
        subscribed to all streams belonging to that group. Also, you \
        will be kept updated when new streams are added to the group.
        Just react to this message with the emoji of the stream group \
        you like to subscribe to. Remove your emoji to unsubscribe \
        from this group. (Note that this will not unsubscribe you from \
        the streams of this group.)

        stream group | emoji
        ------------ | -----
        {}
        *to be continued*

        In case the emojis do not work for you, you may write me a PM:
        - `group subscribe <group_id>`
        - `group unsubscribe <group_id>`

        Have a nice day! :sunglasses:
        """
    )
    _announcement_msg_table_row_fmt: str = '%s | :%s:'
    _announcement_msg_table_row_regex: str = r'\n*%s \| :[^:]+:\s*\n*'
    _claim_all_sql: str = 'insert into GroupClaimsAll values (?)'
    _claim_group_sql: str = 'insert into GroupClaims values (?,?)'
    _get_all_emojis_sql: str = 'select Emoji from Groups'
    _get_claims_for_all_sql: str = 'select MessageId from GroupClaimsAll'
    _get_claims_for_group: str = 'select MessageId from GroupClaims where GroupId = ?'
    _get_emoji_from_group_sql: str = 'select Emoji from Groups where Id = ?'
    _get_group_from_emoji_sql: str = 'select Id from Groups where Emoji = ?'
    _get_group_subscribers_sql: str = 'select UserId from GroupUsers where GroupId = ?'
    _get_streams_sql: str = 'select Streams from Groups where Id = ? collate nocase'
    _insert_sql: str = 'insert into Groups values (?,?,?)'
    _is_group_claimed_by_msg_sql: str = (
        'select * from GroupClaims where GroupId = ? and MessageId = ?'
    )
    _is_message_announcement_sql: str = 'select * from GroupClaimsAll where MessageId = ?'
    _list_sql: str = 'select * from Groups'
    _remove_sql: str = 'delete from Groups where Id = ? collate nocase'
    _subscribe_user_sql: str = 'insert into GroupUsers values (?,?)'
    _update_streams_sql: str = 'update Groups set Streams = ? where Id = ? collate nocase'
    _unclaim_msg_from_group_sql: str = (
        'delete from GroupClaims where MessageId = ? and GroupId = ?'
    )
    _unclaim_msg_for_all_sql: str = 'delete from GroupClaimsAll where MessageId = ?'
    _unsubscribe_user_sql: str = 'delete from GroupUsers where UserId = ? and GroupId = ?'

    def __init__(self, plugin_context: PluginContext) -> None:
        super().__init__(plugin_context)
        # Get own database connection.
        self._db = DB()
        # Check for database tables.
        self._db.checkout_table(
            table = 'Groups',
            schema = '(Id text primary key, Emoji text not null unique, Streams text not null)'
        )
        self._db.checkout_table(
            table = 'GroupUsers',
            schema = ('(UserId integer not null, GroupId text, '
                      'foreign key(GroupId) references Groups(ID) on delete cascade, '
                      'primary key(UserId, GroupID))')
        )
        self._db.checkout_table(
            table = 'GroupClaims',
            schema = ('(MessageId integer not null, GroupId text, '
                      'foreign key(GroupId) references Groups(ID) on delete cascade, '
                      'primary key(MessageId, GroupId))')
        )
        self._db.checkout_table('GroupClaimsAll', '(MessageId integer primary key)')

        # Init command parsing.
        self.command_parser = CommandParser()
        self.command_parser.add_subcommand('subscribe', {'group_id': str})
        self.command_parser.add_subcommand('unsubscribe', {'group_id': str})
        self.command_parser.add_subcommand('add', {'group_id': str, 'emoji': Regex.get_emoji_name})
        self.command_parser.add_subcommand('remove', {'group_id': str})
        self.command_parser.add_subcommand(
            'add_streams', {'group_id': str, 'streams': str}, greedy = True
        )
        self.command_parser.add_subcommand(
            'remove_streams', {'group_id': str, 'streams': str}, greedy = True
        )
        self.command_parser.add_subcommand('list')
        self.command_parser.add_subcommand(
            'claim', {'group_id': str, 'text': str}, greedy = True, optional = True
        )
        self.command_parser.add_subcommand('unclaim', {'group_id': str, 'message_id': int})
        self.command_parser.add_subcommand('announce')
        self.command_parser.add_subcommand('unannounce', {'message_id': int})

        # Init some usefule constants.
        self._get_emoji: Pattern[str] = re.compile(r'\s*:?([^:]+):?\s*')
        # (removing trailing 'api/' from host url).
        self.message_link: str = '[{0}](' + self.client.base_url[:-4] + '#narrow/id/{0})'

    def handle_event(
        self,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        if event['type'] == 'reaction':
            return self.handle_reaction_event(event)
        if event['type'] == 'stream':
            return self.handle_stream_event(event)
        return self.handle_message(event['message'])

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        result: Optional[Tuple[str, CommandParser.Args]]

        # Get command and parameters.
        result = self.command_parser.parse(message['command'])
        if result is None:
            return Response.command_not_found(message)
        command, args = result

        if command == 'subscribe':
            return self._subscribe(message['sender_id'], args.group_id, message)
        if command == 'unsubscribe':
            return self._unsubscribe(message['sender_id'], args.group_id, message)

        if not self.client.get_user_by_id(message['sender_id'])['user']['is_admin']:
            return Response.admin_err(message)

        if command == 'list':
            return self._list(message)
        if command == 'announce':
            if message['type'] != 'stream':
                return Response.build_message(message, 'Claim only stream messages.')
            return self._announce(message)
        if command == 'unannounce':
            return self._unannounce(message, args.message_id)
        if command == 'claim':
            if message['type'] != 'stream':
                return Response.build_message(message, 'Claim only stream messages.')
            return self._claim(message, args.group_id)
        if command == 'unclaim':
            return self._unclaim(message, args.group_id, args.message_id)
        if command == 'add':
            return self._add(message, args.group_id, args.emoji)
        if command == 'remove':
            return self._remove(message, args.group_id)
        if command in ['add_streams', 'remove_streams']:
            return self._change_streams(message, args.group_id, command, args.streams)

        return Response.command_not_found(message)

    def handle_reaction_event(
        self,
        event: Dict[str, Any],
    ) -> Union[Response, Iterable[Response]]:
        group_id: Optional[str] = self._get_group_id_from_emoji_event(
            event['message_id'], event['emoji_name']
        )

        if group_id is None:
            return Response.none()
        if event['op'] == 'add':
            return self._subscribe(event['user_id'], group_id)
        if event['op'] == 'remove':
            return self._unsubscribe(event['user_id'], group_id)

        return Response.none()

    def handle_stream_event(
        self,
        event: Dict[str, Any],
    ) -> Union[Response, Iterable[Response]]:
        for stream in event['streams']:
            # Get all the groups this stream belongs to.
            group_ids: List[str] = self._get_group_ids_from_stream(stream['name'])
            # Get all user ids to subscribe to this new stream ...
            user_ids: List[int] = self._get_group_subscribers(group_ids)
            # ... and subscribe them.
            self.client.subscribe_users(user_ids, stream['name'])

        return Response.none()

    def is_responsible(
        self,
        event: Dict[str, Any]
    ) -> bool:
        return (
            super().is_responsible(event)
            or (event['type'] == 'reaction'
                and event['op'] in ['add', 'remove']
                and event['user_id'] != self.client.id)
            or (event['type'] == 'stream' and event['op'] == 'create')
        )

    def _add(
        self,
        message: Dict[str, Any],
        group_id: str,
        emoji: str
    ) -> Union[Response, Iterable[Response]]:
        """Command `group add <id> <emoji>`."""
        if '\n' in group_id:
            return Response.build_message(message, 'The group id must not contain newlines.')

        try:
            self._db.execute(
                self._insert_sql, group_id, emoji, '', commit = True
            )
        except IntegrityError as e:
            return Response.build_message(message, str(e))

        # Update the announcement messages.
        if not self._announcements_add_group(group_id):
            return Response.build_message(
                message, 'Group added, but announcement failed for some messages.'
            )

        return Response.ok(message)

    def _announce(
        self,
        message: Dict[str, Any]
    ) -> Union[Response, Iterable[Response]]:
        table: str = '\n'.join(
            self._announcement_msg_table_row_fmt % (group_id, emoji)
            for group_id, emoji, _ in self._db.execute(self._list_sql)
        )

        # Remove the requesting message.
        self.client.delete_message(message['id'])

        # Send own message.
        result: Dict[str, Any] = self.client.send_response(
            Response.build_message(message, self._announcement_msg.format(table))
        )
        if result['result'] != 'success':
            return Response.none()

        # Insert the id of the bot's message into the database.
        try:
            self._db.execute(self._claim_all_sql, result['id'], commit = True)
        except Exception as e:
            return Response.build_message(message, str(e))

        # Get all the currently existant emojis.
        result_sql: List[Tuple[Any, ...]] = self._db.execute(self._get_all_emojis_sql)
        if not result_sql:
            return Response.none()

        # React with all those emojis on this message.
        for emoji in map(lambda t: cast(str, t[0]), result_sql):
            self.client.send_response(Response.build_reaction_from_id(result['id'], emoji))

        return Response.none()

    def _announcements_add_group(
        self,
        group_id: str
    ) -> bool:
        """Add the given group to all announcement messages."""
        emoji: Optional[str] = self._get_emoji_from_group(group_id)
        if not emoji:
            return False
        to_insert: str = self._announcement_msg_table_row_fmt % (group_id, emoji)

        pattern: Pattern[str] = re.compile(r'\n*\*to be continued\*\n*')

        return self._do_for_all_announcement_messages([
            lambda msg: msg.update(content = pattern.sub(
                '\n' + to_insert + '\n*to be continued*\n\n', msg['content']
            )),
            lambda msg: self.client.send_response(
                Response.build_reaction(msg, cast(str, emoji))
            )
        ])

    def _announcements_remove_group(
        self,
        group_id: str
    ) -> bool:
        """Remove the given group from all announcement messages."""
        emoji: Optional[str] = self._get_emoji_from_group(group_id)
        if not emoji:
            return False

        pattern: Pattern[str] = re.compile(
            self._announcement_msg_table_row_regex % re.escape(group_id)
        )

        return self._do_for_all_announcement_messages([
            lambda msg: msg.update(content = pattern.sub('\n', msg['content'])),
            lambda msg: self.client.remove_reaction(
                {'message_id': msg['id'], 'emoji_name': cast(str, emoji)}
            )
        ])

    def _change_streams(
        self,
        message: Dict[str, Any],
        group_id: str,
        command: str,
        change_stream_regs: List[str]
    ) -> Union[Response, Iterable[Response]]:
        """Command `group (add_streams|remove_streams) <id> <stream>...`."""
        # Validate the regexes.
        for reg in change_stream_regs:
            try:
                re.compile(reg)
            except re.error as e:
                return Response.build_message(message, 'invalid regex: %s\n%s', reg, str(e))

        result_sql: List[Tuple[Any, ...]] = self._db.execute(
            self._get_streams_sql, group_id, commit = True
        )
        if not result_sql:
            return Response.build_message(message, f'Group {group_id} does not exist.')

        # Current stream patterns.
        stream_list: List[str] = result_sql[0][0].split('\n')
        # The string containing the new list of stream patterns (newline separated).
        # The patterns have to be non-empty.
        new_streams: str = '\n'.join(filter(
            bool,
            set(stream_list + change_stream_regs) if command == 'add_streams' else
            [s for s in stream_list if s not in change_stream_regs]
        ))

        try:
            self._db.execute(self._update_streams_sql, new_streams, group_id, commit = True)
        except Exception as e:
            logging.exception(e)
            return Response.build_message(message, str(e))

        # Subscribe the group subscribers to the new streams.
        self._subscribe_users_to_stream_regexes(
            self._get_group_subscribers([group_id]), change_stream_regs
        )

        return Response.ok(message)

    def _claim(
        self,
        message: Dict[str, Any],
        group_id: Optional[str],
    ) -> Union[Response, Iterable[Response]]:
        """Command `group claim [id]`."""
        if group_id:
            self._db.execute(self._claim_group_sql, message['id'], group_id, commit = True)
        else:
            self._db.execute(self._claim_all_sql, message['id'], commit = True)

        return Response.ok(message)

    def _do_for_all_announcement_messages(
        self,
        funcs: List[Callable[[Dict[str, Any]], Any]]
    ) -> bool:
        """Apply functions to all announcement messages.

        The return values of the functions will be ignored. The message
        dict may be modified inplace.
        """
        success: bool = True

        for (msg_id,) in self._db.execute(self._get_claims_for_all_sql):
            request: Dict[str, Any] = {
                'anchor': msg_id, 'num_before': 0, 'num_after': 1,
            }
            result: Dict[str, Any] = self.client.get_messages(request)
            if result['result'] != 'success' or not result['messages']:
                logging.warning('could not get message %s', str(request))
                success = False
                continue
            msg: Dict[str, Any] = result['messages'][0]
            for func in funcs:
                func(msg)
            self.client.update_message({'message_id': msg_id, 'content': msg['content']})

        return success

    def _get_emoji_from_group(self, group_id: str) -> Optional[str]:
        """Get the emoji for a given group id."""
        result_sql: List[Tuple[Any, ...]] = self._db.execute(
            self._get_emoji_from_group_sql, group_id
        )
        if not result_sql:
            logging.debug('no emoji found for group %s', group_id)
            return None
        return cast(str, result_sql[0][0])

    def _get_group_id_from_emoji_event(
        self,
        message_id: int,
        emoji: str
    ) -> Optional[str]:
        result_sql: List[Tuple[Any, ...]]

        result_sql = self._db.execute(self._get_group_from_emoji_sql, emoji)
        if not result_sql:
            return None
        group_id: str = cast(str, result_sql[0][0])

        # Check whether the message is claimed by this group.
        result_sql = self._db.execute(self._is_group_claimed_by_msg_sql, group_id, message_id)
        if not result_sql:
            result_sql = self._db.execute(self._is_message_announcement_sql, message_id)

        return group_id if result_sql else None


    def _get_group_ids_from_stream(self, stream_name: str) -> List[str]:
        """Get the ids of the groups the given stream name belongs to."""
        result: List[str] = []

        for group_id, _, stream_regs_str in self._db.execute(self._list_sql):
            stream_regs: List[str] = stream_regs_str.split('\n')
            for stream_reg in stream_regs:
                if not re.fullmatch(stream_reg, stream_name):
                    continue
                result.append(group_id)
                break

        return result

    def _get_group_subscribers(self, group_ids: List[str]) -> List[int]:
        """Get the user_ids of all subscribers of the given groups.

        Return no duplicate user_ids.
        """
        result: Set[int] = set()

        for group_id in group_ids:
            result = result.union(set(
                user_id for (user_id,) in
                self._db.execute(self._get_group_subscribers_sql, group_id)
            ))

        return list(result)

    def _list(
        self,
        message: Dict[str, Any]
    ) -> Union[Response, Iterable[Response]]:
        """Command `group list`."""
        response: str = 'Group Id | Emoji | Streams | ClaimedBy\n---- | ---- | ---- | ----'

        for (group_id, emoji, streams) in self._db.execute(self._list_sql):
            streams_concat: str = ', '.join(
                '"{}"'.format(s) for s in streams.split('\n')
            )
            claims: str = ', '.join([
                self.message_link.format(msg_id)
                for (msg_id,) in self._db.execute(self._get_claims_for_group, group_id)
            ])
            response += '\n{0} | {1} :{1}: | `{2}` | {3}'.format(
                group_id, emoji, streams_concat, claims
            )

        response += '\n\nMessages claimed for all groups: ' + ', '.join(
            self.message_link.format(msg_id)
            for msg_id, in self._db.execute(self._get_claims_for_all_sql)
        )

        return Response.build_message(message, response)

    def _remove(
        self,
        message: Dict[str, Any],
        group_id: str,
    ) -> Union[Response, Iterable[Response]]:
        msg_success: bool = self._announcements_remove_group(group_id)

        self._db.execute(self._remove_sql, group_id, commit = True)

        if msg_success:
            return Response.ok(message)

        return Response.build_message(
            message, 'Group removed, but removal failed for some announcement messages.'
        )

    def _subscribe(
        self,
        user_id: int,
        group_id: str,
        message: Optional[Dict[str, Any]] = None
    ) -> Union[Response, Iterable[Response]]:
        """Subscribe a user to a group."""
        msg: str

        try:
            self._db.execute(self._subscribe_user_sql, user_id, group_id, commit = True)
        except IntegrityError as e:
            logging.exception(e)
            # User already subscribed.
            msg = f'I think you are already subscribed to group {group_id}.'
            if message:
                return Response.build_message(message, msg)
            return Response.build_message(
                message = None, content = msg, msg_type = 'private', to = [user_id]
            )

        stream_regs: List[str] = []
        for (stream_regs_str,) in self._db.execute(self._get_streams_sql, group_id):
            if not stream_regs_str:
                continue
            stream_regs.extend(stream_regs_str.split('\n'))

        no_success: List[str] = self._subscribe_users_to_stream_regexes([user_id], stream_regs)

        if not no_success:
            if message is not None:
                return Response.ok(message)
            return Response.build_message(
                message = None, content = f'Subscribed to group {group_id}.',
                msg_type = 'private', to = [user_id]
            )

        msg = 'Failed to subscribe you to the following streams: %s.' % str(no_success)

        if message is not None:
            return Response.build_message(message, msg)
        # Write a private message to the user.
        return Response.build_message(
            message = None, content = msg, msg_type = 'private', to = [user_id]
        )

    def _subscribe_users_to_stream_regexes(
        self,
        user_ids: List[int],
        stream_regs: List[str]
    ) -> List[str]:
        """Subscribe the given group to all streams matching the regexes.

        Return a list of streams to which the users could not be
        subscribed.
        """
        no_success: List[str] = []

        for stream_reg in stream_regs:
            for stream in self.client.get_streams_from_regex(stream_reg):
                if not self.client.subscribe_users(user_ids, stream):
                    no_success.append(stream)

        return no_success

    def _unannounce(
        self,
        message: Dict[str, Any],
        message_id: str
    ) -> Union[Response, Iterable[Response]]:
        self._db.execute(self._unclaim_msg_for_all_sql, message_id, commit = True)
        return Response.ok(message)

    def _unclaim(
        self,
        message: Dict[str, Any],
        group_id: str,
        message_id: str
    ) -> Union[Response, Iterable[Response]]:
        try:
            msg_id: int = int(message_id)
        except ValueError:
            return Response.build_message(message, f'{message_id} is not an integer.')
        self._db.execute(
            self._unclaim_msg_from_group_sql, msg_id, group_id, commit = True
        )
        return Response.ok(message)

    def _unsubscribe(
        self,
        user_id: int,
        group_id: str,
        message: Optional[Dict[str, Any]] = None
    ) -> Union[Response, Iterable[Response]]:
        """Unsubscribe a user from a group."""
        self._db.execute(self._unsubscribe_user_sql, user_id, group_id, commit = True)
        if message is not None:
            return Response.ok(message)
        return Response.build_message(
            message = None, content = f'Unsubscribed from group {group_id}.',
            msg_type = 'private', to = [user_id]
        )
