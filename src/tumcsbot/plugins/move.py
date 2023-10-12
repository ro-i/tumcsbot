#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Iterable

from tumcsbot.lib import CommandParser, Regex, Response
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class Move(PluginCommandMixin, PluginThread):
    syntax = cleandoc(
        """
        move <destination>
          or move -m[count] <destination>
        """
    )
    description = cleandoc(
        """
        - `move <destination>`:
        Move the current topic to the `destination` and notify the \
        creator of the topic by a private message. Change the topic \
        name to destination topic if present, otherwise keep the \
        topic name.
        `destination` is parsed according to the following cases:
          - `stream_name` → `stream_name`, no topic
          - `#**stream_name**` → `stream_name`, no topic
          - `#**stream_name>topic**` → `stream_name`, `topic`
        - `move -m[count] <destination>`:
        Same as above, but only move the last `count` messages of the \
        current topic instead of the whole topic.
        `count` defaults to 1.

        [administrator/moderator rights needed]

        **Note**:
        - This works only if the bot has access to the participating \
        streams!
        - This command does not work if the destination stream name \
        contains a `>` -> an issue that needs to be fixed in the Zulip \
        server.
        """
    )
    msg_template: str = (
        "Hi {}, I moved your post from #**{}** to #**{}** because I "
        "think that it might be more appropriate there :smile:"
    )

    def _init_plugin(self) -> None:
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand(
            self.plugin_name(),
            opts={"m": lambda m: int(m) if m else 1},
            args={"dest": str},
            greedy=True,
        )

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        result: tuple[str, CommandParser.Opts, CommandParser.Args] | None

        if not self.client().user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        if "stream_id" not in message:
            return Response.build_message(message, "Error: not in a stream.")

        result = self.command_parser.parse(
            self.plugin_name() + " " + message["command"]
        )
        if result is None:
            return Response.command_not_found(message)
        _, opts, args = result

        # TODO: discards additional spaces
        dest: tuple[str, str | None] | None = Regex.get_stream_and_topic_name(
            " ".join(args.dest)
        )

        if dest is None:
            return Response.build_message(message, "cannot parse " + message["command"])

        return self._move(message, dest[0], dest[1], opts.m)

    def _move(
        self,
        message: dict[str, Any],
        dest_stream: str,
        dest_topic: str | None,
        count: int | None,
    ) -> Response | Iterable[Response]:
        if count is not None and count < 1:
            return Response.build_message(message, "Error: message count must be >= 1.")

        # Get the stream id ...
        stream_id: int = message["stream_id"]
        # ... and the topic of the current message.
        topic: str = message["subject"]

        # Get the message that is count "hops" before the given message
        # in this topic if count is give, else the first message in the topic.
        request: dict[str, Any] = {
            "anchor": "newest" if count is not None else "oldest",
            "num_before": (count + 1) if count is not None else 0,
            "num_after": 0 if count is not None else 1,
            "narrow": [
                {"operator": "stream", "operand": stream_id},
                {"operator": "topic", "operand": topic},
            ]
            + (
                [{"operator": "near", "operand": str(message["id"])}]
                if count is not None
                else []
            ),
        }
        result = self.client().get_messages(request)
        if result["result"] != "success":
            return Response.error(message)
        if (count is not None and len(result["messages"]) < 2) or (
            count is None and len(result["messages"]) < 1
        ):
            return Response.build_message(message, "No message to move.")
        first_message: dict[str, Any] = result["messages"][0]

        # Get destination stream id.
        result = self.client().get_stream_id(dest_stream)
        if result["result"] != "success":
            return Response.error(message)
        dest_stream_id: int = result["stream_id"]

        # Move message (and all following in the same topic) to the new topic.
        request = {
            "message_id": first_message["id"],
            "topic": dest_topic if dest_topic is not None else topic,
            "stream_id": dest_stream_id,
            "send_notification_to_old_thread": False,
            "propagate_mode": "change_later" if count is not None else "change_all",
        }
        result = self.client().update_message(request)
        if result["result"] != "success":
            return Response.error(message)

        # Remove requesting message.
        self.client().delete_message(message["id"])

        # Get current stream name.
        stream_name: str | None = self.client().get_stream_name(stream_id)
        from_loc: str = (
            (stream_name if stream_name is not None else "unknown") + ">" + topic
        )
        to_loc: str = (
            dest_stream + ">" + (dest_topic if dest_topic is not None else topic)
        )

        return Response.build_message(
            first_message,
            self.msg_template.format(
                first_message["sender_full_name"], from_loc, to_loc
            ),
            msg_type="private",
        )
