#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import unittest

from typing import cast, Any, Dict, Optional, Tuple

from tumcsbot.lib import CommandParser


class CommandParserTest(unittest.TestCase):
    def _do_parse(
        self,
        command: Optional[str]
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Discard the subcommand_name, only return the arguments dict."""
        result: Optional[Tuple[str, CommandParser.Opts, CommandParser.Args]]

        result = self.parser.parse(command)
        if result is None:
            return result
        _, opts, args = result

        return (opts.__dict__, args.__dict__)

    def _do_parse_args(
        self,
        command: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        result: Optional[Tuple[Dict[str, Any], Dict[str, Any]]]
        result = self._do_parse(command)
        if result is not None:
            self.assertEqual(result[0], CommandParser.Opts().__dict__)
        return None if result is None else result[1]

    def _do_parse_opts(
        self,
        command: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        result: Optional[Tuple[Dict[str, Any], Dict[str, Any]]]
        result = self._do_parse(command)
        if result is not None:
            self.assertEqual(result[1], CommandParser.Args().__dict__)
        return None if result is None else result[0]

    def setUp(self) -> None:
        self.parser: CommandParser = CommandParser()


class CommandParserTestArgs(CommandParserTest):
    def test_no_subcommands(self) -> None:
        self.assertIsNone(self._do_parse_args('some string'))

    def test_empty(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str})
        self.assertIsNone(self._do_parse_args(''))

    def test_none(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str})
        self.assertIsNone(self._do_parse_args(None))

    def test_valid_no_args(self) -> None:
        self.parser.add_subcommand('test1')
        self.assertEqual(self._do_parse_args('test1'), {})
        self.parser.add_subcommand('test2', args={})
        self.assertEqual(self._do_parse_args('test2'), {})

    def test_valid_simple(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str, 'arg2': str})
        self.assertEqual(self._do_parse_args('test abc def'), {'arg1': 'abc', 'arg2': 'def'})

    def test_valid_simple_int(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': int})
        self.assertEqual(self._do_parse_args('test 42'), {'arg1': 42})

    def test_invalid_simple_int(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': int})
        self.assertIsNone(self._do_parse_args('test abc'))

    def test_too_short(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': int})
        self.assertIsNone(self._do_parse_args('test'))

    def test_too_long(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': int})
        self.assertIsNone(self._do_parse_args('test 1 2'))

    def test_valid_subcommands(self) -> None:
        result: Tuple[str, CommandParser.Opts, CommandParser.Args]
        self.parser.add_subcommand('test1', args={'arg1': int})
        self.parser.add_subcommand('test2', args={'arg1': str, 'arg2': str})
        result = cast(
            Tuple[str, CommandParser.Opts, CommandParser.Args], self.parser.parse('test1 1')
        )
        self.assertEqual(result[0], 'test1')
        result = cast(
            Tuple[str, CommandParser.Opts, CommandParser.Args], self.parser.parse('test2 a b')
        )
        self.assertEqual(result[0], 'test2')

    def test_invalid_subcommands(self) -> None:
        self.parser.add_subcommand('test1', args={'arg1': int})
        self.assertIsNone(self.parser.parse('testN 1'))

    def test_valid_greedy(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str}, greedy = True)
        self.assertEqual(self._do_parse_args('test a b c'), {'arg1': ['a', 'b', 'c']})
        self.parser.add_subcommand('test1', greedy = True)
        self.assertEqual(self._do_parse_args('test1'), {})

    def test_invalid_greedy(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str}, greedy = True)
        self.assertIsNone(self._do_parse_args('test'))

    def test_valid_greedy_int(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str, 'arg2': int}, greedy = True)
        self.assertEqual(self._do_parse_args('test abc 1'), {'arg1': 'abc', 'arg2': [1]})
        self.assertEqual(self._do_parse_args('test abc 1 2 3'), {'arg1': 'abc', 'arg2': [1,2,3]})

    def test_invalid_greedy_int(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str, 'arg2': int}, greedy = True)
        self.assertIsNone(self._do_parse_args('test abc 1 a 3'))

    def test_valid_optional(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str}, optional = True)
        self.assertEqual(self._do_parse_args('test a'), {'arg1': 'a'})
        self.assertEqual(self._do_parse_args('test'), {'arg1': None})
        self.parser.add_subcommand('test', args={'arg1': str, 'arg2': int}, optional = True)
        self.assertEqual(self._do_parse_args('test a'), {'arg1': 'a', 'arg2': None})
        self.assertEqual(self._do_parse_args('test a 1'), {'arg1': 'a', 'arg2': 1})

    def test_invalid_optional(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str, 'arg2': int}, optional = True)
        self.assertIsNone(self._do_parse_args('test a b'))

    def test_valid_optional_greedy(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str}, greedy = True, optional = True)
        self.assertEqual(self._do_parse_args('test'), {'arg1': None})
        self.assertEqual(self._do_parse_args('test a'), {'arg1': ['a']})
        self.assertEqual(self._do_parse_args('test a b c'), {'arg1': ['a', 'b', 'c']})
        self.parser.add_subcommand(
            'test', args={'arg1': str, 'arg2': int}, greedy = True, optional = True
        )
        self.assertEqual(self._do_parse_args('test a 1 2 3'), {'arg1': 'a', 'arg2': [1,2,3]})
        self.assertEqual(self._do_parse_args('test a 1'), {'arg1': 'a', 'arg2': [1]})
        self.assertEqual(self._do_parse_args('test a'), {'arg1': 'a', 'arg2': None})

    def test_invalid_optional_greedy(self) -> None:
        self.parser.add_subcommand(
            'test', args={'arg1': str, 'arg2': int}, greedy = True, optional = True
        )
        self.assertIsNone(self._do_parse_args('test a 1 2 a'))


class CommandParserTestQuotes(CommandParserTest):
    def test_valid_quotation(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str, 'arg2': str})
        self.assertEqual(
            self._do_parse_args('test "a b" c'), {'arg1': 'a b', 'arg2': 'c'}
        )
        self.assertEqual(
            self._do_parse_args('test "a \\" b" c'), {'arg1': 'a " b', 'arg2': 'c'}
        )
        self.assertEqual(
            self._do_parse_args('test "a \\\' b" c'), {'arg1': 'a \\\' b', 'arg2': 'c'}
        )
        self.assertEqual(
            self._do_parse_args('test \'a b\' c'), {'arg1': 'a b', 'arg2': 'c'}
        )
        self.assertEqual(
            self._do_parse_args('test \'a \\" b\' c'), {'arg1': 'a \\" b', 'arg2': 'c'}
        )
        self.assertEqual(
            self._do_parse_args('test \'a " b\' c'), {'arg1': 'a " b', 'arg2': 'c'}
        )

    def test_invalid_quotation(self) -> None:
        self.parser.add_subcommand('test', args={'arg1': str, 'arg2': str})
        self.assertIsNone(self._do_parse_args('test "a b c'))
        self.assertIsNone(self._do_parse_args('test "a "b" c'))
        self.assertIsNone(self._do_parse_args('test a \'b c'))
        self.assertIsNone(self._do_parse_args('test \'a \'b\' c'))
        self.assertIsNone(self._do_parse_args('test \'a \\\' b\' c'))


class CommandParserTestOpts(CommandParserTest):
    def test_valid_single_opt(self) -> None:
        self.parser.add_subcommand('test', opts={'a': int})
        self.assertEqual(self._do_parse_opts('test -a1'), {'a': 1})
        self.assertEqual(self._do_parse_opts('test'), {'a': None})

    def test_valid_multiple_opts(self) -> None:
        self.parser.add_subcommand('test', opts={'c': float, 'a': int, 'b': str})
        self.assertEqual(
            self._do_parse_opts('test -babc -c1.0 -a1'), {'a': 1, 'b': 'abc', 'c': 1.0}
        )
        self.assertEqual(
            self._do_parse_opts('test -babc -a1'), {'a': 1, 'b': 'abc', 'c': None}
        )

    def test_valid_flags(self) -> None:
        self.parser.add_subcommand('test', opts={'a': None})
        self.assertEqual(self._do_parse_opts('test'), {'a': False})
        self.assertEqual(self._do_parse_opts('test -a'), {'a': True})

    def test_valid_flags_opts_combined(self) -> None:
        self.parser.add_subcommand('test', opts={'a': None, 'b': str, 'c': None})
        self.assertEqual(self._do_parse_opts('test'), {'a': False, 'b': None, 'c': False})
        self.assertEqual(self._do_parse_opts('test -bu'), {'a': False, 'b': 'u', 'c': False})
        self.assertEqual(self._do_parse_opts('test -bu -a'), {'a': True, 'b': 'u', 'c': False})
        self.assertEqual(self._do_parse_opts('test -c -bu -a'), {'a': True, 'b': 'u', 'c': True})

    def test_valid_optional_param(self) -> None:
        self.parser.add_subcommand('test', opts={'a': lambda s: 0 if not s else int(s)})
        self.assertEqual(self._do_parse_opts('test -a'), {'a': 0})
        self.assertEqual(self._do_parse_opts('test -a0'), {'a': 0})
        self.assertEqual(self._do_parse_opts('test -a42'), {'a': 42})
        self.assertEqual(self._do_parse_opts('test'), {'a': None})

    def test_invalid_param(self) -> None:
        self.parser.add_subcommand('test', opts={'a': int})
        self.assertIsNone(self._do_parse_opts('test -ab'))

    def test_invalid_optional_param(self) -> None:
        self.parser.add_subcommand('test', opts={'a': int})
        self.assertIsNone(self._do_parse_opts('test -a'))


class CommandParserTestOptsArgsCombined(CommandParserTest):
    def test_valid(self) -> None:
        self.parser.add_subcommand(
            'test', opts={'a': None}, args={'arg1': int, 'arg2': str}, greedy=True, optional=True
        )
        self.assertEqual(self._do_parse('test -a 1'), ({'a': True}, {'arg1': 1, 'arg2': None}))
        self.assertEqual(self._do_parse('test 1'), ({'a': False}, {'arg1': 1, 'arg2': None}))
        self.assertEqual(
            self._do_parse('test -a 1 abc'), ({'a': True}, {'arg1': 1, 'arg2': ['abc']})
        )
        self.assertEqual(
            self._do_parse('test -a 1 a b c'), ({'a': True}, {'arg1': 1, 'arg2': ['a', 'b', 'c']})
        )
        self.parser.add_subcommand(
            'test2', opts={'i': int, 'a': None}, args={'arg1': int, 'arg2': str},
            greedy=True, optional=True
        )

    def test_invalid(self) -> None:
        self.parser.add_subcommand('test', opts={'a': int}, args={'arg1': int})
        self.assertIsNone(self._do_parse('test -aa 1'))
        self.assertIsNone(self._do_parse('test -a1 a'))

    def test_valid_end_of_options(self) -> None:
        self.parser.add_subcommand(
            'test', opts={'a': None, 'b': str}, args={'arg1': str, 'arg2': str}, optional=True
        )
        self.assertEqual(
            self._do_parse('test -a -bc d'), ({'a': True, 'b': 'c'}, {'arg1': 'd', 'arg2': None})
        )
        self.assertEqual(
            self._do_parse('test -a -b c d'), ({'a': True, 'b': ''}, {'arg1': 'c', 'arg2': 'd'})
        )
        self.assertEqual(
            self._do_parse(r'test -a \\-b'), ({'a': True, 'b': None}, {'arg1': '-b', 'arg2': None})
        )
        self.assertEqual(
            self._do_parse(r'test -a \\-b c'), ({'a': True, 'b': None}, {'arg1': '-b', 'arg2': 'c'})
        )
