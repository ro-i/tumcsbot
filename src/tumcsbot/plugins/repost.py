#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Final, Iterable

from tumcsbot.lib import DB, Response
from tumcsbot.plugin import Event, PluginThread


class Repost(PluginThread):
    """Handle unknown commands."""

    dependencies = ["conf"]
    zulip_events = ["reaction"]

    _msg_template: Final[str] = cleandoc(
        """
        Hi {} :) An administrator marked your following post as repost:
        ```quote
        {}
        ```
        As a result, I removed the message above :)
        """
    )

    def _init_plugin(self) -> None:
        super()._init_plugin()
        self._repost_emoji: str | None = None
        self.reload()

    def reload(self) -> None:
        super().reload()
        db: DB = DB()
        result: list[tuple[Any, ...]] = db.execute(
            "select value from Conf where Key = 'RepostEmoji'"
        )
        self._repost_emoji = None if not result else result[0][0]

    def handle_zulip_event(self, event: Event) -> Response | Iterable[Response]:
        # Check that the reacting user has sufficient rights.
        if not self.client.user_is_privileged(event.data["user_id"]):
            return Response.none()

        # Get message content.
        result: dict[str, Any] = self.client.get_raw_message(
            event.data["message_id"], apply_markdown=False
        )
        # Verify also that the message is a stream message.
        if result["result"] != "success" or not "stream_id" in result["message"]:
            return Response.none()
        orig_msg: dict[str, Any] = result["message"]

        # Remove message.
        result = self.client.delete_message(event.data["message_id"])
        if result["result"] != "success":
            return Response.none()

        # Write to the original author.
        return Response.build_message(
            message=None,
            content=self._msg_template.format(
                orig_msg["sender_full_name"], orig_msg["content"]
            ),
            msg_type="private",
            to=[orig_msg["sender_id"]],
        )

    def is_responsible(self, event: Event) -> bool:
        return (
            super().is_responsible(event)
            and event.data["type"] == "reaction"
            and event.data["op"] == "add"
            and event.data["emoji_name"] == self._repost_emoji
        )
