#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""PluginManager - a class that manage plugins on a per-thread basis.

Classes:
--------
PluginManager
"""

import logging
import threading

from typing import Any, Dict, List, Type

from tumcsbot.client import Client
from tumcsbot.plugin import PluginContext, Plugin


class PluginManager(threading.local):
    """A thread-local plugin manager.

    Note that modifications of thread-local objects are only visible
    within the same thread.
    (See https://github.com/python/cpython/blob/master/Lib/_threading_local.py)
    """
    def __init__(
        self,
        plugin_classes: List[Type[Plugin]],
        **kwargs: Any
    ) -> None:
        """Initialize plugin manager.

        Arguments:
        ----------
        plugin_classes    The plugins to instantiate per thread.
        """
        super().__init__()
        self.plugin_classes: List[Type[Plugin]] = plugin_classes
        self.plugins: List[Plugin] = []

    def instantiate(
        self,
        plugin_context: PluginContext,
        *args: Any
    ) -> None:
        """Do the per-thread instantiation of the plugins.

        Pass kwargs to the constructor of the plugin classes in
        addition to the reference to the internal client instance.
        """
        # Get own per-thread client instance.
        plugin_context.client = Client(config_file = plugin_context.zuliprc)
        self.client: Client = plugin_context.client
        self.plugins = [
            plugin_class(plugin_context) for plugin_class in self.plugin_classes
        ]

    def event_callback(self, event: Dict[str, Any]) -> None:
        """Process one event."""
        logging.debug('received event %s', str(event))

        try:
            event = self._event_preprocess(event)
        except Exception as e:
            logging.exception(e)
            return

        for plugin in self.plugins:
            try:
                plugin.event_callback(event)
            except Exception as e:
                logging.exception(e)

    def _event_preprocess(
        self,
        event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Preprocess an event.

        Check if the event could be an interactive command (to be
        handled by a CommandPlugin instance).

        Check if one of the following requirements are met by the event:
          - It is a private message to the bot.
          - It is a message starting with mentioning the bot.
        The sender of the message must not be the bot itself.

        If this event may be a command, add two new fields to the
        message dict:
          command_name     The name of the command.
          command          The command without the name.
        """
        startswithping: bool = False

        if (event['type'] == 'message'
                and event['message']['content'].startswith(self.client.ping)):
            startswithping = True

        if (event['type'] != 'message'
                or event['message']['sender_id'] == self.client.id
                or (event['message']['type'] != 'private' and not startswithping)
                or (event['message']['type'] == 'private' and startswithping)):
            return event

        content: str
        message: Dict[str, Any] = event['message']

        if startswithping:
            content = message['content'][self.client.ping_len:]
        else:
            content = message['content']

        cmd: List[str] = content.split(maxsplit = 1)
        logging.debug('received command line %s', str(cmd))

        event['message'].update(
            command_name = cmd[0] if len(cmd) > 0 else '',
            command = cmd[1] if len(cmd) > 1 else ''
        )

        return event
