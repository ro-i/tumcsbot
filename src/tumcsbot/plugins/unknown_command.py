#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from typing import Any, Dict, Iterable, List, Union

from tumcsbot.lib import Response
from tumcsbot.plugin import PluginContext, Plugin


class UnknownCommand(Plugin):
    """Handle unknown commands."""
    plugin_name = 'unknown_command'
    events = ['message']

    def __init__(self, plugin_context: PluginContext, **kwargs: Any) -> None:
        super().__init__(plugin_context)
        self._command_names: List[str] = list(map(
            lambda p: p.plugin_name,
            plugin_context.command_plugin_classes
        ))

    def handle_event(
        self,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        return Response.build_reaction(event['message'], 'question')

    def is_responsible(self, event: Dict[str, Any]) -> bool:
        return (
            event['type'] == 'message'
            and (
                'command_name' in event['message']
                and event['message']['command_name']
                and event['message']['command_name'] not in self._command_names
            )
        )
