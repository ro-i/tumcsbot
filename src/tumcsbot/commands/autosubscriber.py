#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Keep the bot subscribed to all public streams.

Reason:
As the 'all_public_streams' parameter of the event API [1] does not
seem to work properly, we need a work-around in order to be able to
receive events for all public streams.

[1] https://zulip.com/api/register-queue#parameter-all_public_streams
"""

from time import sleep
from typing import Any, Dict, Iterable, List, Union

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandDaemon):
    name: str = 'autosubscriber'
    events: List[str] = ['stream']

    def __init__(self, zuliprc: str, **kwargs: Any) -> None:
        super().__init__(zuliprc)

    def event_callback(self, event: Dict[str, Any]) -> None:
        """Override CommandDaemon.event_callback."""
        try:
            self.func(self.client, event)
        except Exception as e:
            self.logger.exception(e)

    def func (
        self,
        client: Client,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, Iterable[lib.Response]]:
        """Do the actual subscribing."""
        result: Dict[str, Any]

        # Check whether the event indicates a new stream.
        if event['op'] != 'create':
            return lib.Response.none()

        for stream in event['streams']:
            # Do not autosubscribe to private streams.
            if stream['invite_only']:
                continue
            result = client.add_subscriptions(streams = [{'name': stream['name']}])
            if result['result'] != 'success':
                self.logger.warning(
                    'AutoSubscriber.run(): Cannot subscribe to stream: ' + str(result)
                )

        return lib.Response.none()
