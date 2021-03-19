#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import unittest

from typing import Any, Dict, Optional, Tuple

from tumcsbot.lib import CommandParser


class CommandParserTest(unittest.TestCase):
    def _do_parse(self, command: Optional[str]) -> Optional[Dict[str, Any]]:
        """Discard the subcommand_name, only return the arguments dict."""
        result: Optional[Tuple[str, CommandParser.Args]] = self.parser.parse(command)
        if result is None:
            return result
        _, args = result
        return args.__dict__

    def setUp(self) -> None:
        self.parser: CommandParser = CommandParser()

    def test_no_subcommands(self) -> None:
        self.assertIsNone(self._do_parse('some string'))

    def test_empty(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str})
        self.assertIsNone(self._do_parse(''))

    def test_none(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str})
        self.assertIsNone(self._do_parse(None))

    def test_valid_no_args(self) -> None:
        self.parser.add_subcommand('test1')
        self.assertEqual(self._do_parse('test1'), {})
        self.parser.add_subcommand('test2', {})
        self.assertEqual(self._do_parse('test2'), {})

    def test_valid_simple(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str, 'arg2': str})
        self.assertEqual(self._do_parse('test abc def'), {'arg1': 'abc', 'arg2': 'def'})

    def test_valid_simple_int(self) -> None:
        self.parser.add_subcommand('test', {'arg1': int})
        self.assertEqual(self._do_parse('test 42'), {'arg1': 42})

    def test_invalid_simple_int(self) -> None:
        self.parser.add_subcommand('test', {'arg1': int})
        self.assertIsNone(self._do_parse('test abc'))

    def test_too_short(self) -> None:
        self.parser.add_subcommand('test', {'arg1': int})
        self.assertIsNone(self._do_parse('test'))

    def test_too_long(self) -> None:
        self.parser.add_subcommand('test', {'arg1': int})
        self.assertIsNone(self._do_parse('test 1 2'))

    def test_valid_subcommands(self) -> None:
        self.parser.add_subcommand('test1', {'arg1': int})
        self.parser.add_subcommand('test2', {'arg1': str, 'arg2': str})
        self.assertEqual(
            self.parser.parse('test1 1'),
            ('test1', CommandParser.Args(**{'arg1': 1}))
        )
        self.assertEqual(
            self.parser.parse('test2 a b'),
            ('test2', CommandParser.Args(**{'arg1': 'a', 'arg2': 'b'}))
        )

    def test_invalid_subcommands(self) -> None:
        self.parser.add_subcommand('test1', {'arg1': int})
        self.assertIsNone(self.parser.parse('testN 1'))

    def test_valid_greedy(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str}, greedy = True)
        self.assertEqual(self._do_parse('test a b c'), {'arg1': ['a', 'b', 'c']})
        self.parser.add_subcommand('test1', greedy = True)
        self.assertEqual(self._do_parse('test1'), {})

    def test_invalid_greedy(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str}, greedy = True)
        self.assertIsNone(self._do_parse('test'))

    def test_valid_greedy_int(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str, 'arg2': int}, greedy = True)
        self.assertEqual(self._do_parse('test abc 1'), {'arg1': 'abc', 'arg2': [1]})
        self.assertEqual(self._do_parse('test abc 1 2 3'), {'arg1': 'abc', 'arg2': [1,2,3]})

    def test_invalid_greedy_int(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str, 'arg2': int}, greedy = True)
        self.assertIsNone(self._do_parse('test abc 1 a 3'))

    def test_valid_optional(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str}, optional = True)
        self.assertEqual(self._do_parse('test a'), {'arg1': 'a'})
        self.assertEqual(self._do_parse('test'), {})
        self.parser.add_subcommand('test', {'arg1': str, 'arg2': int}, optional = True)
        self.assertEqual(self._do_parse('test a'), {'arg1': 'a'})
        self.assertEqual(self._do_parse('test a 1'), {'arg1': 'a', 'arg2': 1})

    def test_invalid_optional(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str, 'arg2': int}, optional = True)
        self.assertIsNone(self._do_parse('test a b'))

    def test_valid_optional_greedy(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str}, greedy = True, optional = True)
        self.assertEqual(self._do_parse('test'), {})
        self.assertEqual(self._do_parse('test a'), {'arg1': ['a']})
        self.assertEqual(self._do_parse('test a b c'), {'arg1': ['a', 'b', 'c']})
        self.parser.add_subcommand(
            'test', {'arg1': str, 'arg2': int}, greedy = True, optional = True
        )
        self.assertEqual(self._do_parse('test a 1 2 3'), {'arg1': 'a', 'arg2': [1,2,3]})
        self.assertEqual(self._do_parse('test a 1'), {'arg1': 'a', 'arg2': [1]})
        self.assertEqual(self._do_parse('test a'), {'arg1': 'a'})

    def test_invalid_optional_greedy(self) -> None:
        self.parser.add_subcommand(
            'test', {'arg1': str, 'arg2': int}, greedy = True, optional = True
        )
        self.assertIsNone(self._do_parse('test a 1 2 a'))

    def test_valid_quotation(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str, 'arg2': str})
        self.assertEqual(self._do_parse('test "a b" c'), {'arg1': 'a b', 'arg2': 'c'})
        self.assertEqual(self._do_parse('test "a \\" b" c'), {'arg1': 'a " b', 'arg2': 'c'})
        self.assertEqual(self._do_parse('test "a \\\' b" c'), {'arg1': 'a \\\' b', 'arg2': 'c'})
        self.assertEqual(self._do_parse('test \'a b\' c'), {'arg1': 'a b', 'arg2': 'c'})
        self.assertEqual(self._do_parse('test \'a \\" b\' c'), {'arg1': 'a \\" b', 'arg2': 'c'})
        self.assertEqual(self._do_parse('test \'a " b\' c'), {'arg1': 'a " b', 'arg2': 'c'})

    def test_invalid_quotation(self) -> None:
        self.parser.add_subcommand('test', {'arg1': str, 'arg2': str})
        self.assertIsNone(self._do_parse('test "a b c'))
        self.assertIsNone(self._do_parse('test "a "b" c'))
        self.assertIsNone(self._do_parse('test a \'b c'))
        self.assertIsNone(self._do_parse('test \'a \'b\' c'))
        self.assertIsNone(self._do_parse('test \'a \\\' b\' c'))
