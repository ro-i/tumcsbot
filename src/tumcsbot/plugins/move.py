#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Dict, Iterable, Optional, Tuple, Union

from tumcsbot.lib import CommandParser, Regex, Response
from tumcsbot.plugin import CommandPlugin, PluginContext


class Move(CommandPlugin):
    plugin_name = 'move'
    syntax = cleandoc(
        """
        move <destination stream>
          or move -m[count] <destination topic>
        """
    )
    description = cleandoc(
        """
        - `move <destination stream`:
        Move the current topic to `destination stream` and notify the \
        creator of the topic by a private message.
        **Note**: This works only if the bot has access to both streams!
        - `move -m[count] <destination topic>`:
        Move the last `count` posts of the current topic to the given \
        topic in the current stream. The topic will be created if it \
        does not already exist. `count` defaults to 1.

        [administrator/moderator rights needed]
        """
    )
    msg_template_stream: str = (
        'Hi {}, I moved your topic "{}" to stream #**{}** because I '
        'think that it might be more appropriate there :smile:'
    )
    msg_template_topic: str = (
        'Hi {}, I moved your post from #**{}** to #**{}** because I '
        'think that it might be more appropriate there :smile:'
    )

    def __init__(self, plugin_context: PluginContext) -> None:
        super().__init__(plugin_context)
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand(
            'move', opts={'m': lambda m: int(m) if m else 1}, args={'dest': str}
        )

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        result: Optional[Tuple[str, CommandParser.Opts, CommandParser.Args]]

        if not self.client.user_is_privileged(message['sender_id']):
            return Response.admin_err(message)

        if 'stream_id' not in message:
            return Response.build_message(message, 'Error: Not a stream topic.')

        result = self.command_parser.parse('move ' + message['command'])
        if result is None:
            return Response.command_not_found(message)
        _, opts, args = result

        if opts.m is not None:
            return self._move_topic(message, args.dest, opts.m)
        return self._move_stream(message, args.dest)

    def _move_topic(
        self,
        message: Dict[str, Any],
        dest: str,
        count: int
    ) -> Union[Response, Iterable[Response]]:
        if count < 1:
            return Response.build_message(message, 'Error: Message count must be >= 1.')

        # Get the stream id ...
        stream_id: int = message['stream_id']
        # ... and the topic of the current message.
        topic: str = message['subject']

        # Get the message that is count "hops" before the given message
        # in this topic.
        request: Dict[str, Any] = {
            'anchor': 'newest',
            'num_before': count + 1,
            'num_after': 0,
            'narrow': [
                {'operator': 'stream', 'operand': stream_id},
                {'operator': 'topic', 'operand': topic},
                {'operator': 'near', 'operand': str(message['id'])}
            ]
        }
        result = self.client.get_messages(request)
        if result['result'] != 'success':
            return Response.error(message)
        if len(result['messages']) < 2:
            return Response.build_message(message, 'No message to move.')
        first_message: Dict[str, Any] = result['messages'][0]

        # Move message (and all following in the same topic) to the new topic.
        request = {
            'message_id': first_message['id'],
            'topic': dest,
            'stream_id': stream_id,
            'send_notification_to_old_thread': False,
            'send_notification_to_new_thread': False,
            'propagate_mode': 'change_later'
        }
        result = self.client.update_message(request)
        if result['result'] != 'success':
            return Response.error(message)

        # Remove requesting message.
        self.client.delete_message(message['id'])

        # Get current stream name.
        stream_name: Optional[str] = self.client.get_stream_name(stream_id)
        from_loc: str = (stream_name if stream_name is not None else "unknown") + ">" + topic
        to_loc: str = (stream_name if stream_name is not None else "unknown") + ">" + dest

        return Response.build_message(
            first_message,
            self.msg_template_topic.format(first_message['sender_full_name'], from_loc, to_loc),
            msg_type = 'private'
        )

    def _move_stream(
        self,
        message: Dict[str, Any],
        dest: str
    ) -> Union[Response, Iterable[Response]]:
        # Get destination stream name.
        dest_stream: Optional[str] = Regex.get_stream_name(dest)
        if dest_stream is None:
            return Response.command_not_found(message)

        # Get destination stream id.
        result: Dict[str, Any] = self.client.get_stream_id(dest_stream)
        if result['result'] != 'success':
            return Response.error(message)
        dest_stream_id: int = result['stream_id']

        # Get the stream id ...
        src_stream_id: int = message['stream_id']
        # ... and the topic of the current message.
        topic: str = message['subject']

        # Get message which started the topic.
        request: Dict[str, Any] = {
            'anchor': 'oldest',
            'num_before': 0,
            'num_after': 1,
            'narrow': [
                { 'operator': 'stream', 'operand': src_stream_id },
                { 'operator': 'topic', 'operand': topic }
            ]
        }
        result = self.client.get_messages(request)
        if result['result'] != 'success':
            return Response.error(message)
        first_message: Dict[str, Any] = result['messages'][0]

        # Move message (and all following in the same topic) = move topic.
        request = {
            'message_id': first_message['id'],
            'topic': topic,
            'stream_id': dest_stream_id,
            'send_notification_to_old_thread': False,
            'propagate_mode': 'change_all'
        }
        result = self.client.update_message(request)
        if result['result'] != 'success':
            return Response.error(message)

        # Remove requesting message.
        self.client.delete_message(message['id'])

        return Response.build_message(
            first_message,
            self.msg_template_stream.format(first_message['sender_full_name'], topic, dest_stream),
            msg_type = 'private'
        )
