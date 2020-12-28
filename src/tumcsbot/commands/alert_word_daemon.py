#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""React on certain words or phrases with emojis.

Use the Zulip facility, see https://zulip.com/help/add-an-alert-word.
Provide also an interactive command so administrators are able to
change the alert words and specify the emojis to use for the reactions.
"""

import re
from typing import Any, Dict, Iterable, List, Pattern, Union

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandDaemon):
    name: str = 'alert_word_daemon'
    events: List[str] = ['message']
    _select_sql: str = 'select Phrase, Emoji from Alerts'

    def __init__(self, zuliprc: str, **kwargs: Any) -> None:
        super().__init__(zuliprc)
        # get own database connection
        self.db = lib.DB(check_same_thread = False)
        # check for database table
        self.db.checkout_table(
            table = 'Alerts',
            schema = '(Phrase varchar, Emoji varchar)'
        )
        # Cache for alert_phrase - emoji bindings.
        self._bindings: Dict[str, str] = {}
        # Cached pattern,
        self._pattern: Pattern[str] = re.compile('')

    def is_responsible(
        self,
        client: Client,
        event: Dict[str, Any]
    ) -> bool:
        # Do not react on own messages.
        return (event['type'] == 'message'
                and event['message']['sender_id'] != client.id)

    def func(
        self,
        client: Client,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, Iterable[lib.Response]]:
        responses: Iterable[lib.Response] = []

        self.update_pattern()
        if not self._bindings:
            return lib.Response.none()

        return map(
            lambda phrase: lib.Response.build_reaction(
                message = event['message'], emoji = self._bindings[phrase]
            ),
            set(self._pattern.findall(event['message']['content'].lower()))
        )

    def update_pattern(self) -> None:
        """Update the regex if necessary."""
        tmp: Dict[str, str] = dict(self.db.execute(Command._select_sql))
        if tmp == self._bindings:
            return
        self._pattern = re.compile('({})'.format(
            '|'.join(map(re.escape, tmp.keys()))
        ))
        self._bindings = tmp
