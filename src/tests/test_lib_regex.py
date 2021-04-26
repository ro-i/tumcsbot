#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import unittest

from typing import List, Optional, Tuple

from tumcsbot.lib import Regex


class RegexTest(unittest.TestCase):
    emoji_names: List[Tuple[str, Optional[str]]] = [
        ('test', 'test'), (':test:', 'test'), (':tes:t:', None), ('test:', None), (':test', None)
    ]
    stream_names: List[Tuple[str, Optional[str]]] = [
        ('test', 'test'), ('abc def', 'abc def'), ('!/"§$& - ("!~EÜ', '!/"§$& - ("!~EÜ'),
        ('#**test**', 'test'), ('#*test*', '#*test*'), ('#**test*', '#**test*'),
        ('#*test**', '#*test**')
    ]
    user_names: List[Tuple[str, Optional[str]]] = [
        ('John Doe', 'John Doe'), ('John', 'John'), ('John Multiple Doe', 'John Multiple Doe'),
        ('@**John**', 'John'), ('@_**John Doe**', 'John Doe'), ('@*John*', None),
        ('@_*John*', None), ('@John**', None), ('@_John**', None), ('@**John', None),
        ('@_**John', None), ('Jo\\hn', None), ('@**J\\n**', None), ('@_**John D"e**', None)
    ]
    user_names_ids: List[Tuple[str, Optional[Tuple[str, int]]]] = [
        ('@_**John Doe|123**', ('John Doe', 123)), ('@**John Doe|456**', ('John Doe', 456)),
        ('@John Doe|123**', None), ('@**John Doe|123', None)
    ]

    def test_emoji_names(self) -> None:
        for (string, emoji) in self.emoji_names:
            self.assertEqual(Regex.get_emoji_name(string), emoji)

    def test_stream_names(self) -> None:
        for (string, stream_name) in self.stream_names:
            self.assertEqual(Regex.get_stream_name(string), stream_name)

    def test_user_names(self) -> None:
        for (string, user_name) in self.user_names:
            self.assertEqual(Regex.get_user_name(string), user_name)

    def test_user_names_ids(self) -> None:
        for (string, user_name) in self.user_names_ids:
            self.assertEqual(Regex.get_user_name(string, get_user_id = True), user_name)
