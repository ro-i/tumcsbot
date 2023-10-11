#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import unittest

from unittest.mock import patch
from typing import Any

from tumcsbot.client import Client


@patch.object(Client, "__init__", lambda _: None)
class UserPrivilegedTest(unittest.TestCase):
    def test_invalid_user_data(self) -> None:
        ret: dict[str, Any] = {"result": "error"}
        with patch.object(Client, "get_user_by_id", return_value=ret):
            assert Client().get_user_by_id(0) == ret
            self.assertFalse(Client().user_is_privileged(0))

    def test_no_privilege(self) -> None:
        data: list[dict[str, Any]] = [
            {"role": -200},
            {"role": 0},
            {"role": 300},
            {"role": 400},
            {"role": 600},
            {"is_admin": False},
            {"is_admin": True},
            {"is_admin": "False"},
            {"is_admin": "True"},
        ]
        for d in data:
            ret: dict[str, Any] = {"result": "success", "user": d}
            with patch.object(Client, "get_user_by_id", return_value=ret):
                assert Client().get_user_by_id(0) == ret
                self.assertFalse(Client().user_is_privileged(0))

    def test_privilege(self) -> None:
        data: list[dict[str, Any]] = [{"role": 100}, {"role": 200}]
        for d in data:
            ret: dict[str, Any] = {"result": "success", "user": d}
            with patch.object(Client, "get_user_by_id", return_value=ret):
                assert Client().get_user_by_id(0) == ret
                self.assertTrue(Client().user_is_privileged(0))

    def test_privilege_mod(self) -> None:
        data: list[dict[str, Any]] = [{"role": 100}, {"role": 200}, {"role": 300}]
        for d in data:
            ret: dict[str, Any] = {"result": "success", "user": d}
            with patch.object(Client, "get_user_by_id", return_value=ret):
                assert Client().get_user_by_id(0) == ret
                self.assertTrue(Client().user_is_privileged(0, allow_moderator=True))

