#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import urllib.parse

from typing import Any, Dict, List, Pattern, Tuple, Union

import tumcsbot.command as command
import tumcsbot.lib as lib

from tumcsbot.client import Client


class Command(command.CommandInteractive):
    name: str = 'search'
    syntax: str = 'search <string>'
    description: str = 'Get a url to a search for "string" in all public streams.'
    msg_template: str = 'Hi, I hope that these search results may help you: {}'
    path: str = '#narrow/streams/public/search/'

    def __init__(self, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile(r'\s*search\s+(\S+.*)', re.I)

    def handle_message(
        self,
        client: Client,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[lib.Response, List[lib.Response]]:
        # get search string and quote it
        search: str = urllib.parse.quote(
            self._pattern.match(message['command']).group(1), safe = ''
        )
        # fix strange behavior of Zulip which does not accept literal periods
        search = search.replace('.', '%2E')
        # get host url (removing trailing 'api/')
        base_url: str = client.base_url[:-4]
        # build the full url
        url: str = base_url + Command.path + search
        # remove requesting message
        client.delete_message(message['id'])
        return lib.Response.build_message(
            message, Command.msg_template.format(url)
        )
