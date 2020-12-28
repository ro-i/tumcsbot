#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Keep the bot subscribed to all public streams.

As the 'all_public_streams' parameter of the event API [1] does not
seem to work properly, we need a work-around in order to be able to
receive eventy for all public streams.

[1] https://zulip.com/api/register-queue#parameter-all_public_streams
"""

from time import sleep
from typing import Any, Dict, Iterable, List, Union

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandDaemon):
    name: str = 'autosubscriber'
    events: List[str] = []
    # interval in seconds to run periodically
    interval: int = 1800

    def __init__(self, zuliprc: str, **kwargs: Any) -> None:
        super().__init__(zuliprc)

    def event_callback(self, event: Dict[str, Any]) -> None:
        """Override CommandDaemon.event_callback."""
        try:
            self.func(self.client, event)
        except Exception as e:
            self.logger.exception(e)

    def wait_for_event(self) -> None:
        """Override CommandDaemon.wait_for_event.

        Do not wait for any event, but for timer to expire.
        """
        while True:
            try:
                self.event_callback({})
            except Exception as e:
                self.logger.exception(e)
            sleep(type(self).interval)

    def func (
        self,
        client: Client,
        event: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, Iterable[lib.Response]]:
        """Do the actual subscribing."""
        result: Dict[str, Any]

        result = client.get_streams(
            include_public = True,
            include_web_public = True,
            include_subscribed = False,
            include_default = True
        )
        if result['result'] != 'success':
            self.logger.warning(
                'AutoSubscriber.run(): Cannot get list of all streams: '
                + str(result)
            )

        streams: List[Dict[str, Any]] = [
            { 'name': stream['name'] } for stream in result['streams']
        ]

        result = client.add_subscriptions(streams = streams)
        if result['result'] != 'success':
            self.logger.warning(
                'AutoSubscriber.run(): Cannot subscribe to some streams: '
                + str(result)
            )

        return lib.Response.none()
