#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Iterable

from tumcsbot.lib import CommandParser, Conf, Response
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class ConfPlugin(PluginCommandMixin, PluginThread):
    syntax = cleandoc(
        """
        conf set <key> <value>
          or conf remove <key>
          or conf list
        """
    )
    description = cleandoc(
        """
        Set/get/remove bot configuration variables.
        [administrator/moderator rights needed]
        """
    )

    def _init_plugin(self) -> None:
        self._conf: Conf = Conf()
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand("list")
        self.command_parser.add_subcommand("set", args={"key": str, "value": str})
        self.command_parser.add_subcommand("remove", args={"key": str})

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        result: tuple[str, CommandParser.Opts, CommandParser.Args] | None

        if not self.client().user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        result = self.command_parser.parse(message["command"])
        if result is None:
            return Response.command_not_found(message)
        command, _, args = result

        if command == "list":
            response: str = "Key | Value\n ---- | ----"
            for key, value in self._conf.list():
                response += f"\n{key} | {value}"
            return Response.build_message(message, response)

        if command == "remove":
            self._conf.remove(args.key)
            return Response.ok(message)

        if command == "set":
            try:
                self._conf.set(args.key, args.value)
            except Exception as exc:
                self.logger.exception(exc)
                return Response.build_message(message, f"Failed: {exc}")
            return Response.ok(message)

        return Response.command_not_found(message)
