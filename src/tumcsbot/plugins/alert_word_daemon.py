#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""React on certain words or phrases with emojis.

This plugin works together with the plugin "aler_word" and relies on
its database table.
"""

import re

from typing import Any, Dict, Iterable, List, Pattern, Tuple, Union

from tumcsbot.lib import DB, Response
from tumcsbot.plugin import PluginContext, SubBotPlugin


class AlertWordDaemon(SubBotPlugin):
    plugin_name = 'alert_word_daemon'
    events = ['message']
    _select_sql: str = 'select Phrase, Emoji from Alerts'

    def __init__(self, plugin_context: PluginContext, **kwargs: Any) -> None:
        super().__init__(plugin_context)
        # Get pattern and the alert_phrase - emoji bindings.
        self._bindings: List[Tuple[Pattern[str], str]] = self._get_bindings()
        # Replace markdown links by their textual representation.
        self._markdown_links: Pattern[str] = re.compile(r'\[([^\]]*)\]\([^\)]+\)')

    def _get_bindings(self) -> List[Tuple[Pattern[str], str]]:
        """Compile the regexes and bind them to their emojis."""

        # Get a database connection.
        self._db = DB()

        bindings: List[Tuple[Pattern[str], str]] = []

        # Verify every regex and only use the valid ones.
        for regex, emoji in self._db.execute(self._select_sql):
            try:
                pattern: Pattern[str] = re.compile(regex)
            except re.error:
                continue
            bindings.append((pattern, emoji))

        return bindings

    def handle_event(
        self,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        if not self._bindings:
            return Response.none()

        # Get message content.
        # Replace markdown links by their textual representation.
        # Convert to lowercase.
        content: str = self._markdown_links\
            .sub(r'\1', event['message']['content'])\
            .lower()

        return [
            Response.build_reaction(message = event['message'], emoji = emoji)
            for pattern, emoji in self._bindings
            if pattern.search(content) is not None
        ]

    def is_responsible(self, event: Dict[str, Any]) -> bool:
        # Do not react on own messages or on private messages where we
        # are not the only recipient.
        return (event['type'] == 'message'
                and event['message']['sender_id'] != self.client.id
                and (event['message']['type'] == 'stream'
                     or self.client.is_only_pm_recipient(event['message'])))
