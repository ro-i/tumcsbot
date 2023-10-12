#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Manage reactions on certain words or phrases with emojis.

Use the Zulip facility, see https://zulip.com/help/add-an-alert-word.
Provide also an interactive command so administrators are able to
change the alert words and specify the emojis to use for the reactions.
"""

from random import randint
import re
from inspect import cleandoc
from typing import Any, Iterable

from tumcsbot.lib import CommandParser, DB, Regex, Response
from tumcsbot.plugin import Event, PluginCommandMixin, PluginProcess


class AlertWord(PluginCommandMixin, PluginProcess):
    syntax = cleandoc(
        """
        alert_word add '<alert phrase>' <emoji>
          or alert_word remove '<alert phrase>'
          or alert_word list
        """
    )
    description = cleandoc(
        """
        Add an alert word / phrase together with the emoji the bot \
        should use to react on messages containing the corresponding \
        alert phrase.
        For the new alert phrases to take effect, please restart the \
        bot.
        Note that an alert phrase may be any regular expression.
        Hint: `\\b` represents word boundaries.
        [administrator/moderator rights needed]
        """
    )
    _list_sql: str = "select * from Alerts"
    _remove_sql: str = "delete from Alerts where Phrase = ?"
    _select_sql: str = "select Phrase, Emoji from Alerts"
    _update_sql: str = "replace into Alerts values (?,?)"

    def _init_plugin(self) -> None:
        # Get own database connection.
        self._db: DB = DB()
        # Check for database table.
        self._db.checkout_table(
            table="Alerts", schema="(Phrase text primary key, Emoji text not null)"
        )

        # Initialize the plugin's command part.
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand(
            "add", args={"alert_phrase": str, "emoji": Regex.get_emoji_name}
        )
        self.command_parser.add_subcommand("remove", args={"alert_phrase": str})
        self.command_parser.add_subcommand("list")

        # Initialize the plugin's daemon part.
        # Get pattern and the alert_phrase - emoji bindings.
        self._bindings: list[tuple[re.Pattern[str], str]] = self._get_bindings()
        # Replace markdown links by their textual representation.
        self._markdown_links: re.Pattern[str] = re.compile(r"\[([^\]]*)\]\([^\)]+\)")

        self._received_command: bool = False

    def _get_bindings(self) -> list[tuple[re.Pattern[str], str]]:
        """Compile the regexes and bind them to their emojis."""
        bindings: list[tuple[re.Pattern[str], str]] = []

        # Verify every regex and only use the valid ones.
        for regex, emoji in self._db.execute(self._select_sql):
            try:
                pattern: re.Pattern[str] = re.compile(regex)
            except re.error:
                continue
            bindings.append((pattern, emoji))

        return bindings

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        result: tuple[str, CommandParser.Opts, CommandParser.Args] | None
        result_sql: list[tuple[Any, ...]]

        if not self.client().user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        # Get command and parameters.
        result = self.command_parser.parse(message["command"])
        if result is None:
            return Response.command_not_found(message)
        command, _, args = result

        if command == "list":
            result_sql = self._db.execute(self._list_sql)
            response: str = "Alert word or phrase | Emoji\n---- | ----"
            for phrase, emoji in result_sql:
                response += f"\n`{phrase}` | {emoji} :{emoji}:"
            return Response.build_message(message, response)

        # Use lowercase -> no need for case insensitivity.
        alert_phrase: str = args.alert_phrase.lower()

        if command == "add":
            # Add binding to database or update it.
            self._db.execute(self._update_sql, alert_phrase, args.emoji, commit=True)
        elif command == "remove":
            self._db.execute(self._remove_sql, alert_phrase, commit=True)

        return Response.ok(message)

    def handle_zulip_event(self, event: Event) -> Response | Iterable[Response]:
        if self._received_command:
            self._received_command = False
            return self.handle_message(event.data["message"])

        if not self._bindings:
            return Response.none()

        # Get message content.
        # Replace markdown links by their textual representation.
        # Convert to lowercase.
        content: str = self._markdown_links.sub(
            r"\1", event.data["message"]["content"]
        ).lower()

        return [
            Response.build_reaction(message=event.data["message"], emoji=emoji)
            for pattern, emoji in self._bindings
            if randint(1, 6) == 3 and pattern.search(content) is not None
        ]

    def is_responsible(self, event: Event) -> bool:
        # First check whether the command mixin part is responsible.
        if super().is_responsible(event):
            self._received_command = True
            return True

        # Do not react on own messages or on private messages where we
        # are not the only recipient.
        return (
            event.data["type"] == "message"
            and event.data["message"]["sender_id"] != self.client().id
            and (
                event.data["message"]["type"] == "stream"
                or self.client().is_only_pm_recipient(event.data["message"])
            )
        )

    def reload(self) -> None:
        self._bindings = self._get_bindings()
        return super().reload()
