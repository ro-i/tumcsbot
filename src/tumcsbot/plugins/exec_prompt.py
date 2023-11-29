#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Execute a prompt by the bot which has been approved by a user.

Some command plugins do not immediately execute the requested action
but instead build the actual command which would have been executed
and asks the user whether they want to execute it like that. The
user can then react with a (configurable) approve emoji.
This plugin will catch the reaction event and execute the command in
the message the user has reacted to.
In order to prevent misuse, the reacting user has to have the same
user id as the original requesting user.

Request messages crafted by the bot look like this:
```
Hi XXX!
Your input would lead to the execution of the following command.
Do you want to execute this? If yes, please react with :check: to this message.
original_message_id: XXX
command: XXX
```
"""

from inspect import cleandoc
import re
from typing import Any, Final, Iterable

from tumcsbot.lib import Conf, Response
from tumcsbot.plugin import Event, EventType, PluginThread


class ExecPrompt(PluginThread):
    dependencies = ["conf"]
    zulip_events = ["reaction"]

    _approve_emoji: Final[str] = "check"

    def handle_zulip_event(self, event: Event) -> Response | Iterable[Response]:
        result: dict[str, Any]

        # Get request message content.
        result = self.client.get_raw_message(
            event.data["message_id"], apply_markdown=False
        )
        if result["result"] != "success":
            self.logger.error(
                "could not get request message with id %d", event.data["message_id"]
            )
            return Response.none()
        request_msg: dict[str, Any] = result["message"]

        # The original message id, so the id of the message that triggered the
        # request message.
        message_id_m: re.Match[str] | None = re.search(
            r"^original_message_id: (\d+)$", request_msg["content"], re.MULTILINE
        )
        command_m: re.Match[str] | None = re.search(
            r"^command: (.*)", request_msg["content"], re.DOTALL | re.MULTILINE
        )
        if message_id_m is None or command_m is None:
            self.logger.error("could not parse %s", request_msg["content"])
            return Response.none()

        message_id: int = int(message_id_m.group(1))
        command: str = command_m.group(1)

        # Get the original message.
        result = self.client.get_raw_message(message_id, apply_markdown=False)
        if result["result"] != "success":
            self.logger.error(
                "could not get original message with id %d", event.data["message_id"]
            )
            return Response.none()
        orig_msg: dict[str, Any] = result["message"]

        # Fake the content of the original message and replace it with the
        # crafted command from the request message.
        orig_msg["content"] = command

        # Create a fake Zulip event, such as returned by client.get_events(),
        # see https://zulip.com/api/get-events#message.
        fake_event: dict[str, Any] = {
            "id": -1,  # not important
            "flags": [],  # not important
            "type": "message",
            "message": orig_msg,
        }

        self.plugin_context.push_loopback(
            Event(self.plugin_name(), EventType.ZULIP, data=fake_event)
        )

        return Response.none()

    def is_responsible(self, event: Event) -> bool:
        return (
            super().is_responsible(event)
            and event.data["type"] == "reaction"
            and event.data["op"] == "add"
            and event.data["emoji_name"] == self._approve_emoji
        )
