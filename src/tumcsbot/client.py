#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Wrapper around Zulip's Client class."""

import functools
import logging
import re
from threading import RLock
import time
from collections.abc import Iterable as IterableClass
from typing import cast, Any, Callable, IO, Iterable

from zulip import Client as ZulipClient

from tumcsbot.lib import stream_names_equal, DB, Response, MessageType, Regex


def synchronized(lock: RLock) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _synchronized(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with lock:
                return func(*args, **kwargs)

        return wrapper

    return _synchronized


class Client(ZulipClient):
    """Wrapper around zulip.Client.

    Additional attributes:
      id         direct access to get_profile()['user_id']
      ping       string used to ping the bot "@**<bot name>**"
      ping_len   len(ping)

    Additional Methods:
    -------------------
    get_public_stream_names   Get the names of all public streams.
    get_raw_message           Adapt original code and add apply_markdown.
    get_streams_from_regex    Get the names of all public streams
                              matching a regex.
    get_stream_name           Get stream name for provided stream id.
    get_user_ids_from_attribute
        Get the user ids from a given user attribute.
    get_user_ids_from_display_names
        Get the user id from a user display name.
    get_user_ids_from_emails
        Get the user id from a user email address.
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
        self.ping: str = f"@**{self.get_profile()['full_name']}**"
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

    def send_response(self, response: Response) -> dict[str, Any]:
        """Send one single response."""
        logging.debug("send_response: %s", str(response))

        if response.message_type == MessageType.MESSAGE:
            return self.send_message(response.response)
        if response.message_type == MessageType.EMOJI:
            return self.add_reaction(response.response)
        return {}

    def send_responses(
        self,
        responses: Response | Iterable[Response | Iterable[Response]],
    ) -> None:
        """Send the given responses."""
        if responses is None:
            logging.debug("responses is None, this should never happen")
            return

        if not isinstance(responses, IterableClass):
            self.send_response(responses)
            return

        for response in responses:
            self.send_responses(response)

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

    def get_user_id_by_name(self, username: str) -> int | None:
        request = {
            "content": username,
        }

        result = self.render_message(request)
        if result["result"] != "success":
            return None

        match = re.search(Regex._USER_ID_PATTERN, result["rendered"])
        if not match:
            return None
        return int(match.groupdict()["id"])

    def get_stream_id_by_name(self, stream_name: str) -> int | None:
        request = {
            "content": stream_name,
        }

        result = self.render_message(request)
        if result["result"] != "success":
            return None

        match = re.search(Regex._STREAM_ID_PATTERN, result["rendered"])
        if not match:
            return None
        return int(match.groupdict()["id"])

    def get_group_id_by_name(self, group_name: str) -> int | None:
        request = {
            "content": group_name,
        }

        result = self.render_message(request)
        if result["result"] != "success":
            return None

        match = re.search(Regex._USER_GROUP_ID_PATTERN, result["rendered"])
        if not match:
            return None
        return int(match.groupdict()["id"])

    def get_stream_by_id(self, stream_id: int) -> dict[str, Any] | None:
        stream_result = self.call_endpoint(url=f"/streams/{stream_id}", method="GET")

        if stream_result["result"] != "success":
            return None

        stream_data: dict[str, Any] = stream_result["stream"]
        return stream_data

    # TODO: add these functions as soon as the zulip api allow bot requests
    # def get_groups(self) -> list[dict[str, Any]]:
    #     request_result = self.get_user_groups()
    #     if request_result["result"] != "success":
    #         return []
    #     groups_dict: list[dict[str, Any]] = request_result["user_groups"]
    #     return groups_dict
    #
    # def create_group(self, name: str, description: str) -> bool:
    #     request = {
    #         "name": name,
    #         "description": description,
    #         "members": [],
    #     }
    #
    #     request_result = self.call_endpoint(
    #         f"/user_groups/create", method="POST", request=request
    #     )  # self.create_user_group(request)
    #     if request_result["result"] != "success":
    #         return False
    #     return True
    #
    # def delete_group(self, identifyer: int | str) -> bool:
    #     group_id = self._group_id_by_identifier(identifyer)
    #
    #     if group_id is None:
    #         return False
    #
    #     request_result = self.remove_user_group(group_id)
    #     if request_result["result"] != "success":
    #         return False
    #     return True
    #
    # def _group_id_by_identifier(self, identifyer: int | str) -> int | None:
    #     if isinstance(identifyer, int):
    #         return int(identifyer)
    #     return self.get_group_id_by_name(str(identifyer))
    #
    # def _user_id_by_identifier(self, identifyer: int | str) -> int | None:
    #     if isinstance(identifyer, int):
    #         return int(identifyer)
    #     return self.get_user_id_by_name(str(identifyer))
    #
    # def _update_user_group_members(
    #     self,
    #     user_group_identifier: int | str,
    #     add: list[int | str],
    #     remove: list[int | str],
    # ) -> bool:
    #     request = {
    #         "delete": [self._user_id_by_identifier(u) for u in remove],
    #         "add": [self._user_id_by_identifier(u) for u in add],
    #     }
    #     gid = self._group_id_by_identifier(user_group_identifier)
    #
    #     if gid is None:
    #         return False
    #
    #     request_result = self.update_user_group_members(int(gid), request)
    #
    #     if request_result["result"] != "success":
    #         return False
    #     return True
    #
    # def remove_user_from_group(
    #     self, user_identifier: int | str, group_identifier: int | str
    # ) -> bool:
    #     return self._update_user_group_members(group_identifier, [], [user_identifier])
    #
    # def add_user_to_group(
    #     self, user_identifier: int | str, group_identifier: int | str
    # ) -> bool:
    #     return self._update_user_group_members(group_identifier, [user_identifier], [])
    #
    # def get_group_members(self, group_identifier: int | str) -> dict[str, Any] | None:
    #     group_id: int = self._group_id_by_identifier(group_identifier)
    #     request_result = self.call_endpoint(
    #         f"/user_groups/{group_id}/members", method="GET"
    #     )
    #
    #     if request_result["result"] != "success":
    #         return None
    #     members: int = request_result["members"]
    #     return members
    #
    # def get_groups_for_user(self, user_identifier: int | str) -> list[int]:
    #     result: list[int] = []
    #     groups = self.get_groups()
    #     uid = self._user_id_by_identifier(user_identifier)
    #
    #     if groups is None or uid is None:
    #         return result
    #
    #     for group in groups:
    #         members: list[int] = group["members"]
    #         if uid in members:
    #             result.append(group["id"])
    #     return result


# This wrapper is kinda redundant, but this allows for better static analysis
# than less verbose techniques...
class SharedClient:
    """A thread-safe wrapper around the Client class."""

    _shared_client_lock: RLock = RLock()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._client: Client = Client(*args, **kwargs)

    @property
    def base_url(self) -> str:
        return self._client.base_url

    @property
    def id(self) -> int:
        return self._client.id

    @property
    def ping(self) -> str:
        return self._client.ping

    @property
    def ping_len(self) -> int:
        return self._client.ping_len

    @synchronized(_shared_client_lock)
    def add_subscriptions(
        self, streams: Iterable[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        return self._client.add_subscriptions(streams=streams, **kwargs)

    @synchronized(_shared_client_lock)
    def call_endpoint(
        self,
        url: str | None = None,
        method: str = "POST",
        request: dict[str, Any] | None = None,
        longpolling: bool = False,
        files: list[IO[Any]] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        return self._client.call_endpoint(
            url=url,
            method=method,
            request=request,
            longpolling=longpolling,
            files=files,
            timeout=timeout,
        )

    @synchronized(_shared_client_lock)
    def delete_message(self, message_id: int) -> dict[str, Any]:
        return self._client.delete_message(message_id=message_id)

    @synchronized(_shared_client_lock)
    def delete_stream(self, stream_id: int) -> dict[str, Any]:
        return self._client.delete_stream(stream_id=stream_id)

    @synchronized(_shared_client_lock)
    def get_messages(self, message_filters: dict[str, Any]) -> dict[str, Any]:
        return self._client.get_messages(message_filters=message_filters)

    @synchronized(_shared_client_lock)
    def get_public_stream_names(self, use_db: bool = True) -> list[str]:
        return self._client.get_public_stream_names(use_db=use_db)

    @synchronized(_shared_client_lock)
    def get_raw_message(
        self, message_id: int, apply_markdown: bool = True
    ) -> dict[str, str]:
        return self._client.get_raw_message(
            message_id=message_id, apply_markdown=apply_markdown
        )

    @synchronized(_shared_client_lock)
    def get_stream_id(self, stream: str) -> dict[str, Any]:
        return self._client.get_stream_id(stream=stream)

    @synchronized(_shared_client_lock)
    def get_stream_name(self, stream_id: int) -> str | None:
        return self._client.get_stream_name(stream_id=stream_id)

    @synchronized(_shared_client_lock)
    def get_streams_from_regex(self, regex: str) -> list[str]:
        return self._client.get_streams_from_regex(regex)

    @synchronized(_shared_client_lock)
    def get_user_ids_from_attribute(
        self, attribute: str, values: Iterable[Any], case_sensitive: bool = True
    ) -> list[int] | None:
        return self._client.get_user_ids_from_attribute(
            attribute=attribute, values=values, case_sensitive=case_sensitive
        )

    @synchronized(_shared_client_lock)
    def get_user_ids_from_display_names(
        self, display_names: Iterable[str]
    ) -> list[int] | None:
        return self._client.get_user_ids_from_display_names(display_names=display_names)

    @synchronized(_shared_client_lock)
    def get_user_ids_from_emails(self, emails: Iterable[str]) -> list[int] | None:
        return self._client.get_user_ids_from_emails(emails=emails)

    @synchronized(_shared_client_lock)
    def get_users(self, request: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._client.get_users(request=request)

    @synchronized(_shared_client_lock)
    def is_only_pm_recipient(self, message: dict[str, Any]) -> bool:
        return self._client.is_only_pm_recipient(message=message)

    @synchronized(_shared_client_lock)
    def private_stream_exists(self, stream_name: str) -> bool:
        return self._client.private_stream_exists(stream_name=stream_name)

    @synchronized(_shared_client_lock)
    def remove_reaction(self, reaction_data: dict[str, Any]) -> dict[str, Any]:
        return self._client.remove_reaction(reaction_data=reaction_data)

    @synchronized(_shared_client_lock)
    def send_response(self, response: Response) -> dict[str, Any]:
        return self._client.send_response(response=response)

    @synchronized(_shared_client_lock)
    def send_responses(
        self,
        responses: Response | Iterable[Response | Iterable[Response]],
    ) -> None:
        return self._client.send_responses(responses=responses)

    @synchronized(_shared_client_lock)
    def subscribe_all_from_stream_to_stream(
        self, from_stream: str, to_stream: str, description: str | None = None
    ) -> bool:
        return self._client.subscribe_all_from_stream_to_stream(
            from_stream=from_stream, to_stream=to_stream, description=description
        )

    @synchronized(_shared_client_lock)
    def subscribe_users(
        self,
        user_ids: list[int],
        stream_name: str,
        description: str | None = None,
        allow_private_streams: bool = False,
    ) -> bool:
        return self._client.subscribe_users(
            user_ids=user_ids,
            stream_name=stream_name,
            description=description,
            allow_private_streams=allow_private_streams,
        )

    @synchronized(_shared_client_lock)
    def update_message(self, message_data: dict[str, Any]) -> dict[str, Any]:
        return self._client.update_message(message_data=message_data)

    @synchronized(_shared_client_lock)
    def update_stream(self, stream_data: dict[str, Any]) -> dict[str, Any]:
        return self._client.update_stream(stream_data=stream_data)

    @synchronized(_shared_client_lock)
    def user_is_privileged(self, user_id: int, allow_moderator: bool = False) -> bool:
        return self._client.user_is_privileged(
            user_id=user_id, allow_moderator=allow_moderator
        )

    @synchronized(_shared_client_lock)
    def get_user_by_id(self, user_id: int) -> dict[str, Any]:
        return self._client.get_user_by_id(user_id)

    @synchronized(_shared_client_lock)
    def get_user_id_by_name(self, username: str) -> int | None:
        return self._client.get_user_id_by_name(username)

    @synchronized(_shared_client_lock)
    def get_stream_id_by_name(self, stream_name: str) -> int | None:
        return self._client.get_stream_id_by_name(stream_name)

    @synchronized(_shared_client_lock)
    def get_stream_by_id(self, stream_id: int) -> dict[str, Any] | None:
        return self._client.get_stream_by_id(stream_id)

    # TODO: add these functions as soon as the zulip api allow bot requests
    # @synchronized(_shared_client_lock)
    # def get_groups(self) -> list[dict[str, Any]]:
    #     return self._client.get_groups()
    #
    # @synchronized(_shared_client_lock)
    # def create_group(self, name: str, description: str) -> bool:
    #     return self._client.create_group(name, description)
    #
    # @synchronized(_shared_client_lock)
    # def delete_group(self, identifyer: int | str) -> bool:
    #     return self._client.delete_group(identifyer)
    #
    # @synchronized(_shared_client_lock)
    # def remove_user_from_group(
    #     self, user_identifier: int | str, group_identifier: int | str
    # ) -> bool:
    #     return self._client.remove_user_from_group(user_identifier, group_identifier)
    #
    # @synchronized(_shared_client_lock)
    # def add_user_to_group(
    #     self, user_identifier: int | str, group_identifier: int | str
    # ) -> bool:
    #     return self._client.add_user_to_group(group_identifier, user_identifier)
    #
    # @synchronized(_shared_client_lock)
    # def get_groups_for_user(self, user_identifier: int | str) -> list[int]:
    #     return self._client.get_groups_for_user(user_identifier)
    #
    # @synchronized(_shared_client_lock)
    # def get_group_id_by_name(self, group_name: str) -> int | None:
    #     return self._client.get_group_id_by_name(group_name)
