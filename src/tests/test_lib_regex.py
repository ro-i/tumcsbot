#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import unittest

from tumcsbot.lib import Regex


class RegexTest(unittest.TestCase):
    stream_names = ['test', 'abc def', '!/"§$& - ("!~EÜ']

    def test_plain_stream_names(self) -> None:
        for s in self.stream_names:
            self.assertEqual(Regex.get_stream_name(s), s)

    def test_hash_stream_name(self) -> None:
        for s in self.stream_names:
            s_h: str = '#' + s
            self.assertEqual(Regex.get_stream_name(s_h), s)

    def test_link_stream_name(self) -> None:
        for s in self.stream_names:
            s_l: str = '#**%s**' % s
            self.assertEqual(Regex.get_stream_name(s_l), s)

    def test_invalid_stream_name_1(self) -> None:
        for s in self.stream_names:
            s_h: str = '#*%s*' % s
            self.assertIsNone(Regex.get_stream_name(s_h))

    def test_strange_format_stream_name_2(self) -> None:
        for s in self.stream_names:
            s_l: str = '**%s**' % s
            self.assertEqual(Regex.get_stream_name(s_l), s)
