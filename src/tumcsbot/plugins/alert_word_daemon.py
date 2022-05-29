#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""React on certain words or phrases with emojis.

This plugin works together with the plugin "aler_word" and relies on
its database table.
"""

import re

from random import randint
from typing import Iterable, List, Pattern, Tuple, Union

from tumcsbot.lib import DB, Response
from tumcsbot.plugin import Event, PluginProcess


class AlertWordDaemon(PluginProcess):
    zulip_events = ['message']
    _select_sql: str = 'select Phrase, Emoji from Alerts'

    def _init_plugin(self) -> None:
        # Get pattern and the alert_phrase - emoji bindings.
        self._bindings: List[Tuple[Pattern[str], str]] = self._get_bindings()
        # Replace markdown links by their textual representation.
        self._markdown_links: Pattern[str] = re.compile(r'\[([^\]]*)\]\([^\)]+\)')

    def _get_bindings(self) -> List[Tuple[Pattern[str], str]]:
        """Compile the regexes and bind them to their emojis."""
        # Get a database connection.
        db: DB = DB()

        bindings: List[Tuple[Pattern[str], str]] = []

        # Verify every regex and only use the valid ones.
        for regex, emoji in db.execute(self._select_sql):
            try:
                pattern: Pattern[str] = re.compile(regex)
            except re.error:
                continue
            bindings.append((pattern, emoji))

        db.close()

        return bindings

    def handle_zulip_event(self, event: Event) -> Union[Response, Iterable[Response]]:
        if not self._bindings:
            return Response.none()

        # Get message content.
        # Replace markdown links by their textual representation.
        # Convert to lowercase.
        content: str = self._markdown_links\
            .sub(r'\1', event.data['message']['content'])\
            .lower()

        return [
            Response.build_reaction(message = event.data['message'], emoji = emoji)
            for pattern, emoji in self._bindings
            if randint(1, 6) == 3 and pattern.search(content) is not None
        ]

    def is_responsible(self, event: Event) -> bool:
        # Do not react on own messages or on private messages where we
        # are not the only recipient.
        return (
            event.data['type'] == 'message'
            and event.data['message']['sender_id'] != self.client().id
            and (
                event.data['message']['type'] == 'stream'
                or self.client().is_only_pm_recipient(event.data['message'])
            )
        )
