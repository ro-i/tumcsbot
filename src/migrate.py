#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Apply database migrations from file."""

import argparse
import sqlite3 as sqlite


def migrate(db_path: str, sql_script_path: str) -> None:
    """Apply the given sql_script to the given database."""
    connection: sqlite.Connection = sqlite.connect(db_path)
    cursor: sqlite.Cursor = connection.cursor()
    with open(sql_script_path, 'r') as sql_script:
        cursor.executescript(sql_script.read())
    connection.commit()
    connection.close()


def main() -> None:
    argument_parser = argparse.ArgumentParser(description = __doc__)
    argument_parser.add_argument(
        'db_path', metavar = 'DB_PATH', help = 'path to the bot\'s database'
    )
    argument_parser.add_argument(
        'script', metavar = 'SQL_SCRIPT', help = 'the migration script to execute'
    )

    args: argparse.Namespace = argument_parser.parse_args()

    migrate(args.db_path, args.script)

    print('Successfully applied migrations.')


if __name__ == '__main__':
    main()
