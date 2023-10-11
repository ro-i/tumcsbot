#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Wrapper around Zulip's Client class."""

import logging
import re
import time
from collections.abc import Iterable as IterableClass
from typing import cast, Any, Callable, IO, Iterable

from zulip import Client as ZulipClient

from tumcsbot.lib import stream_names_equal, DB, Response, MessageType


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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Override the constructor of the parent class."""
        super().__init__(*args, **kwargs)
        self.id: int = self.get_profile()["user_id"]
        self.ping: str = "@**{}**".format(self.get_profile()["full_name"])
        self.ping_len: int = len(self.ping)
        self.register_params: dict[str, Any] = {}
        self._db: DB = DB()
        self._db.checkout_table(
            "PublicStreams",
            "(StreamName text primary key, Subscribed integer not null)",
        )

    def call_endpoint(
        self,
        url: str | None = None,
        method: str = "POST",
        request: dict[str, Any] | None = None,
        longpolling: bool = False,
        files: list[IO[Any]] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Override zulip.Client.call_on_each_event.

        This is the backend for almost all API-user facing methods.
        Automatically resend requests if they failed because of the
        API rate limit.
        """
        result: dict[str, Any]

        while True:
            result = super().call_endpoint(
                url, method, request, longpolling, files, timeout
            )
            if not (
                result["result"] == "error"
                and "code" in result
                and result["code"] == "RATE_LIMIT_HIT"
            ):
                break
            secs: float = result["retry-after"] if "retry-after" in result else 1
            logging.warning("hit API rate limit, waiting for %f seconds...", secs)
            time.sleep(secs)

        return result

    def call_on_each_event(
        self,
        callback: Callable[[dict[str, Any]], None],
        event_types: list[str] | None = None,
        narrow: list[list[str]] | None = None,
        **kwargs: Any,
    ) -> None:
        """Override zulip.Client.call_on_each_event.

        Add additional parameters to pass to register().
        See https://zulip.com/api/register-queue for the parameters
        the register() method accepts.
        """
        self.register_params = kwargs
        super().call_on_each_event(callback, event_types, narrow)

    def get_messages(self, message_filters: dict[str, Any]) -> dict[str, Any]:
        """Override zulip.Client.get_messages.

        Defaults to 'apply_markdown' = False.
        """
        message_filters["apply_markdown"] = False
        return super().get_messages(message_filters)

    def get_public_stream_names(self, use_db: bool = True) -> list[str]:
        """Get the names of all public streams.

        Use the database in conjunction with the plugin "autosubscriber"
        to avoid unnecessary network requests.
        In case of an error, return an empty list.
        """

        def without_db() -> list[str]:
            result: dict[str, Any] = self.get_streams(
                include_public=True, include_subscribed=False
            )
            if result["result"] != "success":
                return []
            return list(map(lambda d: cast(str, d["name"]), result["streams"]))

        if not use_db:
            return without_db()

        try:
            return list(
                map(
                    lambda t: cast(str, t[0]),
                    self._db.execute("select StreamName from PublicStreams"),
                )
            )
        except Exception as e:
            logging.exception(e)
            return without_db()

    def get_raw_message(
        self, message_id: int, apply_markdown: bool = True
    ) -> dict[str, str]:
        """Adapt original code and add apply_markdown."""
        return self.call_endpoint(
            url=f"messages/{message_id}",
            method="GET",
            request={"apply_markdown": apply_markdown},
        )

    def get_streams_from_regex(self, regex: str) -> list[str]:
        """Get the names of all public streams matching a regex.

        The regex has to match the full stream name.
        Note that Zulip handles stream names case insensitively at the
        moment.

        Return an empty list if the regex is not valid.
        """
        if not regex:
            return []

        try:
            pat: re.Pattern[str] = re.compile(regex, flags=re.I)
        except re.error:
            return []

        return [
            stream_name
            for stream_name in self.get_public_stream_names()
            if pat.fullmatch(stream_name)
        ]

    def get_stream_name(self, stream_id: int) -> str | None:
        """Get stream name for provided stream id.

        Return the stream name as string or None if the stream name
        could not be determined.
        """
        result: dict[str, Any] = self.get_streams(include_all_active=True)
        if result["result"] != "success":
            return None

        for stream in result["streams"]:
            if stream["stream_id"] == stream_id:
                return cast(str, stream["name"])

        return None

    def get_user_ids_from_attribute(
        self, attribute: str, values: Iterable[Any], case_sensitive: bool = True
    ) -> list[int] | None:
        """Get the user ids from a given user attribute.

        Get and return a list of user ids of all users whose profiles
        contain the attribute "attribute" with a value present in
        "values.
        If case_sensitive is set to False, the values will be
        interpreted as strings and compared case insensitively.
        Return None on error.
        """
        result: dict[str, Any] = self.get_users()
        if result["result"] != "success":
            return None

        if not case_sensitive:
            values = map(lambda x: str(x).lower(), values)

        value_set: set[Any] = set(values)

        return [
            user["user_id"]
            for user in result["members"]
            if attribute in user
            and (
                user[attribute] in value_set
                if case_sensitive
                else str(user[attribute]).lower() in value_set
            )
        ]

    def get_user_ids_from_display_names(
        self, display_names: Iterable[str]
    ) -> list[int] | None:
        """Get the user id from a user display name.

        Since there may be multiple users with the same display name,
        the returned list of user ids may be longer than the given list
        of user display names.
        Return None on error.
        """
        return self.get_user_ids_from_attribute("full_name", display_names)

    def get_user_ids_from_emails(self, emails: Iterable[str]) -> list[int] | None:
        """Get the user id from a user email address.

        Return None on error.
        """
        return self.get_user_ids_from_attribute(
            "delivery_email", emails, case_sensitive=False
        )

    def get_users(self, request: dict[str, Any] | None = None) -> dict[str, Any]:
        """Override method from parent class."""
        # Try to minimize the network traffic.
        if request is not None:
            request.update(client_gravatar=True, include_custom_profile_fields=False)
        return super().get_users(request)

    def is_only_pm_recipient(self, message: dict[str, Any]) -> bool:
        """Check whether the bot is the only recipient of the given pm.

        Check whether the message is a private message and the bot is
        the only recipient.
        """
        if not message["type"] == "private" or message["sender_id"] == self.id:
            return False

        # Note that the list of users who received the pm includes the sender.

        recipients: list[dict[str, Any]] = message["display_recipient"]
        if len(recipients) != 2:
            return False

        return self.id in [recipients[0]["id"], recipients[1]["id"]]

    def private_stream_exists(self, stream_name: str) -> bool:
        """Check if there is a private stream with the given name.

        Return true if there is a private stream with the given name.
        Return false if there is no stream with this name or if the
        stream is not private.
        """
        result: dict[str, Any] = self.get_streams(include_all_active=True)
        if result["result"] != "success":
            return False  # TODO?

        for stream in result["streams"]:
            if stream_names_equal(stream["name"], stream_name):
                return bool(stream["invite_only"])

        return False

    def register(
        self,
        event_types: Iterable[str] | None = None,
        narrow: list[list[str]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Override zulip.Client.register.

        Override the parent method in order to enable additional
        parameters for the register() call internally used by
        call_on_each_event.
        """
        logging.debug("event_types: %s, narrow: %s", str(event_types), str(narrow))
        return super().register(event_types, narrow, **self.register_params, **kwargs)

    def send_response(
        self, response: Response, internal: bool = False
    ) -> dict[str, Any]:
        """Send one single response."""
        logging.debug("send_response: %s", str(response))

        # TODO: Handle internal!
        if internal:
            return {}

        if response.message_type == MessageType.MESSAGE:
            return self.send_message(response.response)
        if response.message_type == MessageType.EMOJI:
            return self.add_reaction(response.response)
        return {}

    def send_responses(
        self,
        responses: Response | Iterable[Response | Iterable[Response]],
        internal: bool = False,
    ) -> None:
        """Send the given responses."""
        if responses is None:
            logging.debug("responses is None, this should never happen")
            return

        if not isinstance(responses, IterableClass):
            self.send_response(responses, internal)
            return

        for response in responses:
            self.send_responses(response, internal)

    def subscribe_all_from_stream_to_stream(
        self, from_stream: str, to_stream: str, description: str | None = None
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
        if self.private_stream_exists(from_stream) or self.private_stream_exists(
            to_stream
        ):
            return False

        subs: dict[str, Any] = self.get_subscribers(stream=from_stream)
        if subs["result"] != "success":
            return False

        return self.subscribe_users(subs["subscribers"], to_stream, description)

    def subscribe_users(
        self,
        user_ids: list[int],
        stream_name: str,
        description: str | None = None,
        allow_private_streams: bool = False,
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
        chunk_size: int = 100
        success: bool = True

        if not allow_private_streams and self.private_stream_exists(stream_name):
            return False

        subscription: dict[str, str] = {"name": stream_name}
        if description is not None:
            subscription.update(description=description)

        for i in range(0, len(user_ids), chunk_size):
            # (a too large index will be automatically reduced to len())
            user_id_chunk: list[int] = user_ids[i : i + chunk_size]

            while True:
                result: dict[str, Any] = self.add_subscriptions(
                    streams=[subscription], principals=user_id_chunk
                )
                if result["result"] == "success":
                    break
                if result["code"] == "UNAUTHORIZED_PRINCIPAL" and "principal" in result:
                    user_id_chunk.remove(result["principal"])
                    continue
                logging.warning(str(result))
                success = False
                break

        return success

    def user_is_privileged(self, user_id: int, allow_moderator: bool = False) -> bool:
        """Check whether a user is allowed to perform privileged commands.

        Arguments:
        ----------
            user_id          The user_id to examine.
            allow_moderator  Whether the moderator role should be
                             considered as privileged, too.
                             Defaults to False.
        """
        result: dict[str, Any] = self.get_user_by_id(user_id)
        if result["result"] != "success":
            return False
        user: dict[str, Any] = result["user"]

        return (
            "role" in user
            and isinstance(user["role"], int)
            and user["role"] in [100, 200]
            or (allow_moderator and user["role"] == 300)
        )
