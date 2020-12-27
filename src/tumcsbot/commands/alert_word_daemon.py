#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""React on certain words or phrases with emojis.

Use the Zulip facility, see https://zulip.com/help/add-an-alert-word.
Provide also an interactive command so administrators are able to
change the alert words and specify the emojis to use for the reactions.
"""

from typing import Any, Dict, List, Union

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandDaemon):
    name: str = 'alert_word_daemon'
    events: List[str] = ['message']
    _select_sql: str = 'select * from Alerts'

    def __init__(self, zuliprc: str, **kwargs: Any) -> None:
        """Complete the constructor of the parent class."""
        super().__init__(zuliprc)
        # get own database connection
        self._db = lib.DB(check_same_thread = False)
        # check for database table
        self._db.checkout_table(
            table = 'Alerts',
            schema = '(Phrase varchar, Emoji varchar)'
        )
        self.thread.start()

    def is_responsible(
        self,
        client: Client,
        event: Dict[str, Any]
    ) -> bool:
        # 'flags' and 'has_alert_word' implies that the event is a message.
        # Do not react on own messages or private messages.
        return ('flags' in event
                and 'has_alert_word' in event['flags']
                and event['message']['sender_id'] != client.id
                and event['message']['type'] != private)

    def func(
        self,
        client: Client,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, List[lib.Response]]:
        responses: List[lib.Response] = []
        message: Dict[str, Any] = event['message']
        content: str = message['content']

        for (phrase, emoji) in self._db.execute(Command._select_sql):
            if phrase not in content:
                continue
            responses.append(lib.Response.build_reaction(
                message = event['message'], emoji = emoji
            ))

        return responses
