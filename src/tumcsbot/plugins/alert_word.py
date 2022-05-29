#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Manage reactions on certain words or phrases with emojis.

Use the Zulip facility, see https://zulip.com/help/add-an-alert-word.
Provide also an interactive command so administrators are able to
change the alert words and specify the emojis to use for the reactions.
"""

from inspect import cleandoc
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from tumcsbot.lib import CommandParser, DB, Regex, Response
from tumcsbot.plugin import PluginCommand, PluginThread


class AlertWord(PluginCommand, PluginThread):
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
    _update_sql: str = 'replace into Alerts values (?,?)'
    _remove_sql: str = 'delete from Alerts where Phrase = ?'
    _list_sql: str = 'select * from Alerts'

    def _init_plugin(self) -> None:
        # Get own database connection.
        self._db: DB = DB()
        # Check for database table.
        self._db.checkout_table(
            table = 'Alerts', schema = '(Phrase text primary key, Emoji text not null)'
        )
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand('add', args={
            'alert_phrase': str, 'emoji': Regex.get_emoji_name
        })
        self.command_parser.add_subcommand('remove', args={'alert_phrase': str})
        self.command_parser.add_subcommand('list')

    def handle_message(self, message: Dict[str, Any]) -> Union[Response, Iterable[Response]]:
        result: Optional[Tuple[str, CommandParser.Opts, CommandParser.Args]]
        result_sql: List[Tuple[Any, ...]]

        if not self.client().user_is_privileged(message['sender_id']):
            return Response.admin_err(message)

        # Get command and parameters.
        result = self.command_parser.parse(message['command'])
        if result is None:
            return Response.command_not_found(message)
        command, _, args = result

        if command == 'list':
            result_sql = self._db.execute(self._list_sql)
            response: str = 'Alert word or phrase | Emoji\n---- | ----'
            for (phrase, emoji) in result_sql:
                response += '\n`{0}` | {1} :{1}:'.format(phrase, emoji)
            return Response.build_message(message, response)

        # Use lowercase -> no need for case insensitivity.
        alert_phrase: str = args.alert_phrase.lower()

        if command == 'add':
            # Add binding to database or update it.
            self._db.execute(self._update_sql, alert_phrase, args.emoji, commit = True)
        elif command == 'remove':
            self._db.execute(self._remove_sql, alert_phrase, commit = True)

        return Response.ok(message)
