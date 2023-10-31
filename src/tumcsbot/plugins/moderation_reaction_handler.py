#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Manage reactions on certain words or phrases with emojis.

Use the Zulip facility, see https://zulip.com/help/add-an-alert-word.
Provide also an interactive command so administrators are able to
change the alert words and specify the emojis to use for the reactions.
"""

from typing import Any, Iterable, Callable

from tumcsbot.lib import DB, Response
from tumcsbot.plugin import Event, PluginThread

import urllib


class ModerationReactionHandler(PluginThread):
    # pylint: disable=line-too-long
    _replace_dict: dict[
        str, tuple[Callable[[dict[str, Any], dict[str, Any]], str], str]
    ] = {
        "user": (
            lambda _, message: f"@**{message['sender_full_name']}|{message['sender_id']}**",
            "the sender of the message being reacted to",
        ),
        "mod": (
            lambda event_data, _: f"@**{event_data['user']['full_name']}|{event_data['user_id']}**",
            "the sender of the reaction",
        ),
        "stream": (
            lambda _, message: f"#**{message['display_recipient']}**",
            "the stream in which the reaction occurred",
        ),
        "topic": (
            lambda _, message: f"#**{message['display_recipient']}>{message['subject']}**",
            "the topic in which the reaction occurred",
        ),
        "escaped_topic": (
            lambda _, message: urllib.parse.quote(message["subject"]),
            "to topic as an html escaped string",
        ),
        "message": (
            lambda event_data, message: f"/#narrow/stream/{message['display_recipient']}/topic/{message['subject']}/near/{event_data['message_id']}",
            "link to the message being reacted to. Usage: `[Display Text]($message)`",
        ),
        "content": (
            lambda _, message: message["content"],
            "the content of the message being reacted to",
        ),
    }
    # pylint: enable=line-too-long

    _get_streams_sql = "select a.StreamId from GroupAuthorization where "
    _get_actions_sql = (
        "select Emote, Action, Message from ReactionConfig where UserId = ?"
    )

    description = None

    def _init_plugin(self) -> None:
        # Get own database connection.
        self._db: DB = DB()
        # Check for database table.
        self._db.checkout_table(
            "ReactionConfig",
            "(UserId integer not null, Emote text not null, Action text, Message text)",
        )

        self._db.checkout_table(
            "GroupAuthorization",
            "(GroupId integer not null, StreamId integer not null, primary key(GroupId, StreamId))",
        )
        self._db.checkout_table(
            "UserGroups",
            "(GroupId integer primary key autoincrement, UGroup text unique)",
        )
        self._db.checkout_table(
            "UserGroupMembers",
            "(GroupId integer not null, UserId integer not null, primary key (GroupId, UserId))",
        )

        self.client_id: int = self.client.id

    def is_responsible(self, event: Event) -> bool:
        return super().is_responsible(event) or (
            event.data["type"] == "reaction"
            and event.data["op"] == "add"
            and event.data["user_id"] != self.client_id
        )

    def handle_zulip_event(self, event: Event) -> Response | Iterable[Response]:
        uid: int = event.data["user_id"]
        mid: int = event.data["message_id"]

        message = self.client.call_endpoint(
            url=f"/messages/{mid}?apply_markdown=false", method="GET"
        )
        if message["result"] != "success":
            return Response.none()

        message = message["message"]

        if message["type"] != "stream":
            return Response.none()

        sid: int = message["stream_id"]

        authorized_streams = [
            t[0]
            for t in self._db.execute(
                "select a.StreamId from GroupAuthorization a, UserGroupMembers m where a.GroupId = m.GroupId and m.UserId = ?",
                uid,
            )
        ]
        if sid not in authorized_streams:
            return Response.none()

        actions = [
            (action, msg)
            for (reaction, action, msg) in self._db.execute(self._get_actions_sql, uid)
            if reaction == f":{event.data['emoji_name']}:"
        ]
        responses = []
        for action, msg in actions:
            if action == "delete":
                self.client.delete_message(mid)
            elif action == "respond":
                responses.append(
                    Response.build_message(
                        message,
                        content=ModerationReactionHandler._replace_placeholder(
                            msg, event.data, message
                        ),
                    )
                )
            elif action == "dm":
                responses.append(
                    Response.build_message(
                        message=None,
                        to=[message["sender_id"]],
                        msg_type="private",
                        content=ModerationReactionHandler._replace_placeholder(
                            msg, event.data, message
                        ),
                    )
                )

        if len(responses) == 0:
            return Response.none()
        return responses

    @staticmethod
    def _replace_placeholder(
        content: str, event_data: dict[str, Any], message: dict[str, Any]
    ) -> str:
        for k, (replacement, _) in ModerationReactionHandler._replace_dict.items():
            content = content.replace("$" + k, replacement(event_data, message))

        return content

    # TODO: replacement for zulip usergroups. Rreplace as soon as api allows bot requests for usergroups
    def user_id_by_identifier(self, identifier: int | str) -> int | None:
        if isinstance(identifier, int):
            return int(identifier)
        return self.client.get_user_id_by_name(str(identifier))

    def get_groups_for_user(self, user_identifier: int | str) -> list[int]:
        uid = self.user_id_by_identifier(user_identifier)
        res = self._db.execute(
            "select g.GroupId from UserGroups g, UserGroupMembers m where m.GroupId = g.GroupId and m.UserId = ?",
            uid,
        )
        if not res or len(res) == 0:
            return []
        return [i[0] for i in res]
