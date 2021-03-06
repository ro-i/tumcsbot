#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""TUM CS Bot - a generic Zulip bot.

This bot is currently especially intended for administrative tasks.
It supports several commands which can be written to the bot using
a private message or a message starting with @mentioning the bot.
"""

import argparse
import os
import sys

from tumcsbot.tumcsbot import TumCSBot


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description = __doc__,
        formatter_class = argparse.RawTextHelpFormatter
    )
    argument_parser.add_argument(
        'zuliprc', metavar = 'ZULIPRC', nargs = 1,
        help = 'zuliprc file containing the bot\'s configuration'
    )
    argument_parser.add_argument(
        'db_path', metavar = 'DB_PATH', nargs = 1,
        help = 'path to the bot\'s database'
    )
    argument_parser.add_argument(
        '-t', '--threads', metavar = 'N', type = int, default = 8,
        help = 'maximum number of threads to use to run the plugins (default: 8)'
    )
    argument_parser.add_argument(
        '-d', '--debug', action = 'store_true',
        help = 'debugging mode switch'
    )
    argument_parser.add_argument(
        '-l', '--logfile', help = 'use LOGFILE for logging output'
    )
    args: argparse.Namespace = argument_parser.parse_args()

    bot: TumCSBot = TumCSBot(
        zuliprc = args.zuliprc[0],
        db_path = args.db_path[0],
        max_workers = args.threads,
        debug = args.debug,
        logfile = args.logfile
    )

    try:
        bot.run()
    except SystemExit:
        pass

    if bot.restart:
        print('Received termination request. Restarting: ' + str(sys.argv))
        bot.exit_handler()
        os.execv(sys.argv[0], sys.argv)
    else:
        print('Terminated.')


if __name__ == '__main__':
    main()
