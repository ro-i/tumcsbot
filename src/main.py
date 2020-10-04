#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import argparse
import typing

from tumcsbot.tumcsbot import TumCSBot


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description = TumCSBot.__doc__,
        formatter_class = argparse.RawTextHelpFormatter
    )
    argument_parser.add_argument(
        'zuliprc', metavar = 'ZULIPRC', nargs = 1,
        help = 'zuliprc file containing the bot\'s configuration'
    )
    argument_parser.add_argument(
        '-d', '--debug', action = 'store_true',
        help = 'print debug information on the console'
    )
    argument_parser.add_argument(
        '-l', '--logfile', help = 'use LOGFILE for logging output'
    )
    args: argparse.Namespace = argument_parser.parse_args()

    bot: TumCSBot = TumCSBot(
        zuliprc = args.zuliprc[0],
        debug = args.debug,
        logfile = args.logfile
    )
    bot.start()


if __name__ == '__main__':
    main()
