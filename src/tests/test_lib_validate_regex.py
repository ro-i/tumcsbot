#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import unittest

from tumcsbot.lib import validate_and_return_regex


class RegexTest(unittest.TestCase):
    def test_invalid_regexes(self) -> None:
        invalid_regexes: list[str] = [r"[", r")", r"[^]"]
        for regex in invalid_regexes:
            self.assertIsNone(validate_and_return_regex(regex))

    def test_None(self) -> None:
        self.assertIsNone(validate_and_return_regex(None))

    def test_valid_regexes(self) -> None:
        valid_regexes: list[str] = [r"", r"\d.*", r"(\\).*[^\S]"]
        for regex in valid_regexes:
            self.assertEqual(validate_and_return_regex(regex), regex)
