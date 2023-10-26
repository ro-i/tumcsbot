#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from typing import Final, Iterable, cast

from tumcsbot.lib import DB, Response, get_classes_from_path
from tumcsbot.plugin import Event, PluginThread, _Plugin


class UnknownCommand(PluginThread):
    """Handle unknown commands."""

    # This plugin depends on all the others because it needs their db entries.
    dependencies = [
        plugin_class.plugin_name()
        for plugin_class in get_classes_from_path("tumcsbot.plugins", _Plugin)  # type: ignore
        if plugin_class.plugin_name() != "help"
    ]

    zulip_events = ["message"]
    _select_sql: Final[str] = "select name from Plugins"

    def _init_plugin(self) -> None:
        self._command_names: Iterable[str] = list(
            map(lambda t: cast(str, t[0]), DB(read_only=True).execute(self._select_sql))
        )

    def handle_zulip_event(self, event: Event) -> Response | Iterable[Response]:
        return Response.build_reaction(event.data["message"], "question")

    def is_responsible(self, event: Event) -> bool:
        return event.data["type"] == "message" and (
            "command_name" in event.data["message"]
            and event.data["message"]["command_name"]
            and event.data["message"]["command_name"] not in self._command_names
        )
