#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import unittest

from unittest.mock import patch
from typing import Any, Dict, List

from tumcsbot.client import Client


@patch.object(Client, '__init__', lambda self: None)
class UserPrivilegedTest(unittest.TestCase):
    def test_invalid_user_data(self) -> None:
        ret: Dict[str, Any] = {'result': 'error'}
        with patch.object(Client, 'get_user_by_id', return_value = ret):
            assert Client().get_user_by_id(0) == ret
            self.assertFalse(Client().user_is_privileged(0))

    def test_no_privilege(self) -> None:
        data: List[Dict[str, Any]] = [
            {'role': -200}, {'role': 0}, {'role': 300}, {'role': 400}, {'role': 600},
            {'is_admin': False}, {'is_admin': "False"}, {'is_admin': "True"}
        ]
        for d in data:
            ret: Dict[str, Any] = {'result': 'success', 'user': d}
            with patch.object(Client, 'get_user_by_id', return_value = ret):
                assert Client().get_user_by_id(0) == ret
                self.assertFalse(Client().user_is_privileged(0))

    def test_privilege(self) -> None:
        data: List[Dict[str, Any]] = [
            {'role': 100}, {'role': 200}, {'is_admin': True}
        ]
        for d in data:
            ret: Dict[str, Any] = {'result': 'success', 'user': d}
            with patch.object(Client, 'get_user_by_id', return_value = ret):
                assert Client().get_user_by_id(0) == ret
                self.assertTrue(Client().user_is_privileged(0))
