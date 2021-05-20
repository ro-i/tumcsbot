#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import unittest

from typing import cast, Any, Dict

from tumcsbot.lib import user_is_privileged


class UserPrivilegedTest(unittest.TestCase):
    def test_invalid_argument(self) -> None:
        # Tell mypy to ignore the None value.
        self.assertFalse(user_is_privileged(cast(Dict[str, Any], None)))
        self.assertFalse(user_is_privileged({}))
        self.assertFalse(user_is_privileged({'foo': 'bar'}))

    def test_no_privilege(self) -> None:
        self.assertFalse(user_is_privileged({'role': -200}))
        self.assertFalse(user_is_privileged({'role': 0}))
        self.assertFalse(user_is_privileged({'role': 400}))
        self.assertFalse(user_is_privileged({'role': 600}))
        self.assertFalse(user_is_privileged({'is_admin': False}))
        self.assertFalse(user_is_privileged({'is_admin': "False"}))
        self.assertFalse(user_is_privileged({'is_admin': "True"}))

    def test_privilege(self) -> None:
        self.assertTrue(user_is_privileged({'role': 100}))
        self.assertTrue(user_is_privileged({'role': 200}))
        self.assertTrue(user_is_privileged({'role': 300}))
        self.assertTrue(user_is_privileged({'is_admin': True}))
