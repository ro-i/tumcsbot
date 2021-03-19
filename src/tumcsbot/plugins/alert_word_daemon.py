#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""React on certain words or phrases with emojis.

This plugin works together with the plugin "aler_word" and relies on
its database table.
"""

import re

from typing import cast, Any, Dict, Iterable, List, Optional, Pattern, Tuple, Union

from tumcsbot.lib import DB, Response
from tumcsbot.plugin import PluginContext, SubBotPlugin


class AlertWordDaemon(SubBotPlugin):
    plugin_name = 'alert_word_daemon'
    events = ['message']
    _select_sql: str = 'select Phrase, Emoji from Alerts'

    def __init__(self, plugin_context: PluginContext, **kwargs: Any) -> None:
        super().__init__(plugin_context)
        # Get pattern and the alert_phrase - emoji bindings.
        (self._pattern, self._bindings) = self._build_pattern()
        # Replace markdown links by their textual representation.
        self._markdown_links: Pattern[str] = re.compile(r'\[([^\]]*)\]\([^\)]+\)')

    def _build_pattern(self) -> Tuple[Optional[Pattern[str]], Dict[str, str]]:
        """Build a regex containing the alert phrases."""

        # Get a database connection.
        self._db = DB()

        try:
            bindings: Dict[str, str] = dict(cast(
                List[Tuple[str,str]], self._db.execute(self._select_sql)
            ))
        except:
            return (None, {})

        pattern: Pattern[str] = re.compile('({})'.format(
            '|'.join(map(re.escape, bindings.keys()))
        ))

        return (pattern, bindings)

    def handle_event(
        self,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        if not self._pattern or not self._bindings:
            return Response.none()

        # Get message content.
        # Replace markdown links by their textual representation.
        # Convert to lowercase.
        content: str = self._markdown_links\
            .sub(r'\1', event['message']['content'])\
            .lower()

        return map(
            lambda phrase: Response.build_reaction(
                message = event['message'], emoji = self._bindings[phrase]
            ),
            set(self._pattern.findall(content))
        )

    def is_responsible(self, event: Dict[str, Any]) -> bool:
        # Do not react on own messages.
        return (event['type'] == 'message'
                and cast(bool, event['message']['sender_id'] != self.client.id))
