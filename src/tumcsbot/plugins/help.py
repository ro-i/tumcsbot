#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Iterable

from tumcsbot.lib import DB, Response, get_classes_from_path
from tumcsbot.plugin import PluginCommandMixin, _Plugin, PluginThread


class Help(PluginCommandMixin, PluginThread):
    """Provide a help command plugin."""

    # This plugin depends on all the others because it needs their db entries.
    dependencies = PluginCommandMixin.dependencies + [
        plugin_class.plugin_name()
        for plugin_class in get_classes_from_path("tumcsbot.plugins", _Plugin)  # type: ignore
    ]
    syntax = "help"
    description = "Post a help message to the requesting user."
    _help_overview_template: str = cleandoc(
        """
        Hi {}!

        Use `help <command name>` to get more information about a \
        certain command.
        Please consider that my command line parsing is comparable to \
        the POSIX shell. So in order to preserve arguments containing \
        whitespace characters from splitting, they need to be quoted. \
        Special strings such as regexes containing backslash sequences \
        may require single quotes instead of double quotes.

        Currently, I understand the following commands:

        {}

        Have a nice day! :-)
        """
    )
    _get_usage_all_sql: str = "select name, syntax, description from Plugins"
    _get_usage_name_sql: str = (
        "select name, syntax, description from Plugins where name = ?"
    )

    def _init_plugin(self) -> None:
        self.help_info: list[tuple[str, str, str]] = self._get_help_info()

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        command: str = message["command"].strip()
        if not command:
            return self._help_overview(message)
        return self._help_command(message, command)

    @staticmethod
    def _format_description(description: str) -> str:
        """Format the usage description of a command."""
        # Remove surrounding whitespace.
        description.strip()
        return description

    @staticmethod
    def _format_syntax(syntax: str) -> str:
        """Format the syntax string of a command."""
        return "```text\n" + syntax.strip() + "\n```\n"

    def _get_help_info(self) -> list[tuple[str, str, str]]:
        """Get help information from each command.

        Return a list of tuples (command name, syntax, description).
        """
        db: DB = DB()
        result_sql: list[tuple[Any, ...]] = db.execute(self._get_usage_all_sql)
        db.close()
        result: list[tuple[str, str, str]] = [
            (name, self._format_syntax(syntax), self._format_description(description))
            for name, syntax, description in result_sql
            if syntax is not None and description is not None
        ]
        # Sort by name.
        return sorted(result, key=lambda tuple: tuple[0])

    def _help_command(
        self, message: dict[str, Any], command: str
    ) -> Response | Iterable[Response]:
        info_tuple: tuple[str, str, str] | None = None

        for ituple in self.help_info:
            if ituple[0] == command:
                info_tuple = ituple
                break
        if info_tuple is None:
            return Response.command_not_found(message)

        help_message: str = "\n".join(info_tuple[1:])

        return Response.build_message(
            message, help_message, msg_type="private", to=message["sender_email"]
        )

    def _help_overview(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        # Get the command names.
        help_message: str = "\n".join(
            map(lambda tuple: "- " + tuple[0], self.help_info)
        )

        return Response.build_message(
            message,
            self._help_overview_template.format(
                message["sender_full_name"], help_message
            ),
            msg_type="private",
            to=message["sender_email"],
        )
