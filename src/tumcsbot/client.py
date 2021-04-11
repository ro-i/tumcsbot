#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Wrapper around Zulip's Client class.

Classes:
--------
Client   A wrapper around zulip.Client to be used by the plugins.
         See the class doc for the additional attributes and methods.
"""

import logging
import re
import time

from collections.abc import Iterable
from typing import cast, Any, Callable, Dict, IO, Iterable, List, Pattern, Optional, Union
from zulip import Client as ZulipClient

from tumcsbot.lib import DB, Response, MessageType


class Client(ZulipClient):
    """Wrapper around zulip.Client.

    Additional attributes:
      id         direct access to get_profile()['user_id']
      ping       string used to ping the bot "@**<bot name>**"
      ping_len   len(ping)

    Additional Methods:
    -------------------
    get_public_stream_names   Get the names of all public streams.
    get_streams_from_regex    Get the names of all public streams
                              matching a regex.
    get_stream_name           Get stream name for provided stream id.
    private_stream_exists     Check if there is a private stream with
                              the given name.
    send_response             Send one single response.
    send_responses            Send a list of responses.
    subscribe_all_from_stream_to_stream
                              Try to subscribe all users from one public
                              stream to another.
    subscribe_users           Subscribe a list of user ids to a public
                              stream.
    """

    # TODO: client_gravater etc. for better performance?

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Override the constructor of the parent class."""
        super().__init__(*args, **kwargs)
        self.id: int = self.get_profile()['user_id']
        self.ping: str = '@**{}**'.format(self.get_profile()['full_name'])
        self.ping_len: int = len(self.ping)
        self.register_params: Dict[str, Any] = {}
        self._db = DB()
        self._db.checkout_table(
            'PublicStreams', '(StreamName text primary key, Subscribed integer not null)'
        )

    def call_endpoint(
        self,
        url: Optional[str] = None,
        method: str = "POST",
        request: Optional[Dict[str, Any]] = None,
        longpolling: bool = False,
        files: Optional[List[IO[Any]]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Override zulip.Client.call_on_each_event.

        This is the backend for almost all API-user facing methods.
        Automatically resend requests if they failed because of the
        API rate limit.
        """
        result: Dict[str, Any]

        while True:
            result = super().call_endpoint(url, method, request, longpolling, files, timeout)
            if not (result['result'] == 'error'
                    and 'code' in result
                    and result['code'] == 'RATE_LIMIT_HIT'):
                break
            secs: float = result['retry-after'] if 'retry-after' in result else 1
            logging.warning('hit API rate limit, waiting for %f seconds...', secs)
            time.sleep(secs)

        return result

    def call_on_each_event(
        self,
        callback: Callable[[Dict[str, Any]], None],
        event_types: Optional[List[str]] = None,
        narrow: Optional[List[List[str]]] = None,
        **kwargs: Any
    ) -> None:
        """Override zulip.Client.call_on_each_event.

        Add additional parameters to pass to register().
        See https://zulip.com/api/register-queue for the parameters
        the register() method accepts.
        """
        self.register_params = kwargs
        super().call_on_each_event(callback, event_types, narrow)

    def get_messages(self, message_filters: Dict[str, Any]) -> Dict[str, Any]:
        """Override zulip.Client.get_messages.

        Defaults to 'apply_markdown' = False.
        """
        message_filters['apply_markdown'] = False
        return super().get_messages(message_filters)

    def get_public_stream_names(self, use_db: bool = True) -> List[str]:
        """Get the names of all public streams.

        Use the database in conjunction with the plugin "autosubscriber"
        to avoid unnecessary network requests.
        In case of an error, return an empty list.
        """
        def without_db() -> List[str]:
            result: Dict[str, Any] = self.get_streams(
                include_public = True, include_subscribed = False
            )
            if result['result'] != 'success':
                return []
            return list(map(lambda d: cast(str, d['name']), result['streams']))

        if not use_db:
            return without_db()

        try:
            return list(map(
                lambda t: cast(str, t[0]),
                self._db.execute('select StreamName from PublicStreams')
            ))
        except Exception as e:
            logging.exception(e)
            return without_db()

    def get_streams_from_regex(self, regex: str) -> List[str]:
        """Get the names of all public streams matching a regex.

        The regex has to match the full stream name.
        Return an empty list if the regex is not valid.
        """
        if not regex:
            return []

        try:
            pat: Pattern[str] = re.compile(regex)
        except re.error:
            return []

        return [
            stream_name for stream_name in self.get_public_stream_names()
            if pat.fullmatch(stream_name)
        ]

    def get_stream_name(self, stream_id: int) -> Optional[str]:
        """Get stream name for provided stream id.

        Return the stream name as string or None if the stream name
        could not be determined.
        """
        result: Dict[str, Any] = self.get_streams(include_all_active = True)
        if result['result'] != 'success':
            return None

        for stream in result['streams']:
            if stream['stream_id'] == stream_id:
                return cast(str, stream['name'])

        return None

    def is_only_pm_recipient(self, message: Dict[str, Any]) -> bool:
        """Check whether the bot is the only recipient of the given pm.

        Check whether the message is a private message and the bot is
        the only recipient.
        """
        if not message['type'] == 'private' or message['sender_id'] == self.id:
            return False

        # Note that the list of users who received the pm includes the sender.

        recipients: List[Dict[str, Any]] = message['display_recipient']
        if len(recipients) != 2:
            return False

        return self.id in [recipients[0]['id'], recipients[1]['id']]

    def private_stream_exists(self, stream_name: str) -> bool:
        """Check if there is a private stream with the given name.

        Return true if there is a private stream with the given name.
        Return false if there is no stream with this name or if the
        stream is not private.
        """
        result: Dict[str, Any] = self.get_streams(include_all_active = True)
        if result['result'] != 'success':
            return False # TODO?

        for stream in result['streams']:
            if stream['name'] == stream_name:
                return bool(stream['invite_only'])

        return False

    def register(
        self,
        event_types: Optional[Iterable[str]] = None,
        narrow: Optional[List[List[str]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Override zulip.Client.register.

        Override the parent method in order to enable additional
        parameters for the register() call internally used by
        call_on_each_event.
        """
        logging.debug('event_types: %s, narrow: %s', str(event_types), str(narrow))
        return super().register(event_types, narrow, **self.register_params)

    def send_response(self, response: Response) -> Dict[str, Any]:
        """Send one single response."""
        logging.debug('send_response: %s', str(response))

        if response.message_type == MessageType.MESSAGE:
            return self.send_message(response.response)
        elif response.message_type == MessageType.EMOJI:
            return self.add_reaction(response.response)
        return {}

    def send_responses(
        self,
        responses: Union[
            Response,
            Iterable[Union[Response, Iterable[Response]]],
            Union[Response, Iterable[Response]]
        ]
    ) -> None:
        """Send the given responses."""
        if responses is None:
            logging.debug('responses is None, this should never happen')
            return

        if not isinstance(responses, Iterable):
            self.send_response(responses)
            return

        for response in responses:
            self.send_responses(response)


    def subscribe_all_from_stream_to_stream(
        self,
        from_stream: str,
        to_stream: str,
        description: Optional[str] = None
    ) -> bool:
        """Try to subscribe all users from one public stream to another.

        Arguments:
        ----------
        from_stream   An existant public stream.
        to_stream     The stream to subscribe to.
                      Must be public, if already existant. If it does
                      not already exists, it will be created.
        description   An optional description to be used to
                      create the stream first.

        Return true on success or false otherwise.
        """
        if (self.private_stream_exists(from_stream)
                or self.private_stream_exists(to_stream)):
            return False

        subs: Dict[str, Any] = self.get_subscribers(stream = from_stream)
        if subs['result'] != 'success':
            return False

        return self.subscribe_users(subs['subscribers'], to_stream, description)

    def subscribe_users(
        self,
        user_ids: List[int],
        stream_name: str,
        description: Optional[str] = None
    ) -> bool:
        """Subscribe a list of user ids to a public stream.

        Arguments:
        ----------
        user_ids      The list of user ids to subscribe.
        stream_name   The name of the stream to subscribe to.
        description   An optional description to be used to
                      create the stream first.

        Return true on success or false otherwise.
        """
        subscription: Dict[str, str] = {'name': stream_name}
        if description is not None:
            subscription.update(description = description)

        # Use chunks of 500 users. TODO: non-existant users
        for i in range(0, len(user_ids), 500):
            result: Dict[str, Any] = self.add_subscriptions(
                streams = [subscription],
                principals = user_ids[i:i + 500]
                # (a too large index will be automatically reduced to len())
            )
            if result['result'] != 'success':
                return False

        return True

#    def subscribe_user(
#        self,
#        user_id: int,
#        stream_name: str
#    ) -> bool:
#        """Subscribe a user to a public stream.
#
#        The subscription is only executed if the user is not yet
#        subscribed to the stream with the given name.
#        See docs: https://zulip.com/api/get-events#stream-add.
#        Do not subscribe to private streams.
#
#        Return True if the user has already subscribed to the given
#        stream or if they now are subscribed and False otherwise.
#        """
#        result: Dict[str, Any]
#
#        if self.private_stream_exists(stream_name):
#            return False
#
#        result = self.get_stream_id(stream_name)
#        if result['result'] != 'success':
#            return False
#        stream_id: int = result['stream_id']
#
#        # Check whether the user has already subscribed to that stream.
#        result = self.call_endpoint(
#            url = '/users/{}/subscriptions/{}'.format(user_id, stream_id),
#            method = 'GET'
#        )
#        # If the request failed, we try to subscribe anyway.
#        if result['result'] == 'success' and result['is_subscribed']:
#            return True
#        elif result['result'] != 'success':
#            logging.warning('failed subscription status check, stream_id %s', stream_id)
#
#        success: bool = self.subscribe_users([user_id], stream_name)
#        if not success:
#            logging.warning('cannot subscribe %s to stream: %s', user_id, str(result))
#
#        return success
