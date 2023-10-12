#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Iterable

from tumcsbot.lib import CommandParser, Response
from tumcsbot.plugin import Event, PluginCommandMixin, PluginThread


class Plugin(PluginCommandMixin, PluginThread):
    syntax = cleandoc(
        """
        plugin (reload|start|stop) <plugin>
        """
    )
    description = cleandoc(
        """
        [administrator/moderator rights needed]
        """
    )

    def _init_plugin(self) -> None:
        super()._init_plugin()
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand("reload", args={"plugin": str})
        self.command_parser.add_subcommand("start", args={"plugin": str})
        self.command_parser.add_subcommand("stop", args={"plugin": str})

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        result: tuple[str, CommandParser.Opts, CommandParser.Args] | None

        if not self.client().user_is_privileged(message["sender_id"]):
            return Response.admin_err(message)

        result = self.command_parser.parse(message["command"])
        if result is None:
            return Response.command_not_found(message)
        command, _, args = result

        if command == "reload":
            self.plugin_context.push_loopback(
                Event.reload_event(self.plugin_name(), args.plugin)
            )
            return Response.ok(message)
        if command == "start":
            self.plugin_context.push_loopback(
                Event.start_event(self.plugin_name(), args.plugin)
            )
            return Response.ok(message)
        if command == "stop":
            self.plugin_context.push_loopback(
                Event.stop_event(self.plugin_name(), args.plugin)
            )
            return Response.ok(message)

        return Response.command_not_found(message)
