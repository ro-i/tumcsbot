#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import unittest

from typing import Any, ClassVar

from tumcsbot.client import Client as TUMCSBotClient


class ClientGetUserIdsFromAttributeTest(unittest.TestCase):
    class Client(TUMCSBotClient):
        def __init__(self) -> None:
            pass

        def get_users(self, request: dict[str, Any] | None = None) -> dict[str, Any]:
            return get_users()

    _client: ClassVar[Client]

    @classmethod
    def setUpClass(cls) -> None:
        cls._client = cls.Client()

    def test_get_user_ids_from_attribute(self) -> None:
        self.assertEqual(
            self._client.get_user_ids_from_attribute(
                "not_existing_attribute", [1, 2, 3]
            ),
            [],
        )
        self.assertEqual(
            self._client.get_user_ids_from_attribute(
                "delivery_email", ["abc@zulip.org"]
            ),
            [1],
        )
        self.assertEqual(
            self._client.get_user_ids_from_attribute(
                "delivery_email", ["abc@zulip.org", "ghi@zulip.org"]
            ),
            [1, 3],
        )
        self.assertEqual(
            self._client.get_user_ids_from_attribute(
                "delivery_email", ["abc@zulip.org", "gHi@zulip.org"]
            ),
            [1],
        )
        self.assertEqual(
            self._client.get_user_ids_from_attribute(
                "delivery_email",
                ["abc@zulip.org", "gHi@zulip.org"],
                case_sensitive=False,
            ),
            [1, 3],
        )
        self.assertEqual(
            self._client.get_user_ids_from_attribute("user_id", [1, 3]), [1, 3]
        )
        self.assertEqual(
            self._client.get_user_ids_from_attribute(
                "user_id", [2, 3, 4], case_sensitive=False
            ),
            [2, 3],
        )
        self.assertEqual(
            self._client.get_user_ids_from_attribute("full_name", ["abc"]), [1, 2]
        )

    def test_get_user_ids_from_display_names(self) -> None:
        self.assertEqual(
            self._client.get_user_ids_from_attribute("full_name", ["abc"]),
            self._client.get_user_ids_from_display_names(["abc"]),
        )
        self.assertEqual(
            self._client.get_user_ids_from_attribute("full_name", ["aBc"]),
            self._client.get_user_ids_from_display_names(["aBc"]),
        )

    def test_get_user_ids_from_emails(self) -> None:
        self.assertEqual(
            self._client.get_user_ids_from_attribute(
                "delivery_email",
                ["abc@zulip.org", "gHi@zulip.org"],
                case_sensitive=False,
            ),
            self._client.get_user_ids_from_emails(["abc@zulip.org", "gHi@zulip.org"]),
        )


def get_users() -> dict[str, Any]:
    return {
        "result": "success",
        "members": [
            {
                "delivery_email": "abc@zulip.org",
                "full_name": "abc",
                "user_id": 1,
            },
            {
                "delivery_email": "def@zulip.org",
                "full_name": "abc",
                "user_id": 2,
            },
            {
                "delivery_email": "ghi@zulip.org",
                "full_name": "ghi",
                "user_id": 3,
            },
        ],
    }
