#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Simple wrapper around Zulip's Client class.

Classes:
--------
Client   A thin wrapper around zulip.Client.
"""

import logging

from typing import Any, Dict, Iterable, List, Optional
from zulip import Client as ZulipClient


class Client(ZulipClient):
    """Wrapper around zulip.Client."""

    # TODO: client_gravater etc. for better performance?

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Override the constructor of the parent class.

        Additional attributes:
          id          direct access to get_profile()['user_id']
        """
        super().__init__(*args, **kwargs)
        self.__profile: Dict[str, Any] = super().get_profile()
        self.id = self.get_profile()['user_id']
        self.__stream_names: Dict[int, str] = {} # see self.get_stream_name()

    def get_messages(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Override zulip.Client.get_messages.

        Defaults to 'apply_markdown' = False.
        """
        request['apply_markdown'] = False
        return super().get_messages(request)

    def get_profile(
        self,
        request: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Override zulip.Client.get_profile with a caching version.

        Assume that the profile of the bot does not change while it is
        online.
        Currently, the 'request' parameter is not used by the Zulip
        code. In case that this changes, implement a small check and
        fall back to the get_profile() of the superclass if the
        'request' parameter is not None.
        """
        if request is not None:
            return super().get_profile(request)
        return self.__profile

    def get_stream_name(self, stream_id: int) -> Optional[str]:
        """Get stream name for provided stream id.

        Return the stream name as string or None if the stream name
        could not be determined.
        Cache the results in order to minimize the expensive requests.
        """
        def cache_lookup(stream_id: int) -> Optional[str]:
            if stream_id in self.__stream_names:
                return self.__stream_names[stream_id]
            return None

        # Check if the stream name is already in the cache.
        stream_name: Optional[str] = cache_lookup(stream_id)
        if stream_name is not None:
            return stream_name

        # If not, update cache.

        # Get a list of all active streams.
        result: Dict[str, Any] = self.get_streams(include_all_active = True)
        if result['result'] != 'success':
            return None
        for stream in result['streams']:
            self.__stream_names[stream['stream_id']] = stream['name']

        return cache_lookup(stream_id)

    def register(
        self,
        event_types: Optional[Iterable[str]] = None,
        narrow: Optional[List[List[str]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Override zulip.Client.register.

        Override the parent method in order to register events of all
        public streams.
        See https://zulip.com/api/register-queue#parameter-all_public_streams
        """
        logging.debug("Client.register - event_types: {}, narrow: {}".format(
            str(event_types), str(narrow)
        ))
        return super().register(
            event_types, narrow, all_public_streams = True,
        )
