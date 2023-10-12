#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import tempfile
import unittest

from tumcsbot.lib import Conf, DB


class ConfTest(unittest.TestCase):
    def test_conf(self) -> None:
        with tempfile.NamedTemporaryFile() as file:
            db = DB(db_path=file.name)
            conf = Conf(db=db)

            self.assertIsNone(conf.get("name"))
            try:
                conf.remove("name")
            except Exception as exc:
                self.fail(f"received exception {exc}")
            self.assertEqual(conf.list(), [])

            conf.set("name", "foo")
            self.assertEqual(conf.get("name"), "foo")
            conf.set("name", "bar")
            self.assertEqual(conf.get("name"), "bar")
            self.assertEqual(conf.list(), [("name", "bar")])

            conf.remove("name")
            self.assertIsNone(conf.get("name"))
            try:
                conf.remove("name")
            except Exception as exc:
                self.fail(f"received exception {exc}")
