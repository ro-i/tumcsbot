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
