#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import re
import typing
import urllib.parse

from typing import Any, Dict, Pattern, Tuple
from zulip import Client

import tumcsbot.lib as lib


class Command(lib.Command):
    syntax: str = 'search <string>'
    description: str = ('get a url to a search for "string" in all public streams')
    msg_template: str = 'Hi, I hope that these search results may help you: {}'
    path: str = '#narrow/streams/public/search/'

    def __init__(self, **kwargs: Any):
        self._pattern: Pattern[str] = re.compile('\s*search\s+\S+.*', re.I)
        self._capture_pattern: Pattern[str] = re.compile('\s*search\s+(.*)', re.I)

    def func(
            self,
            client: Client,
            message: Dict[str, Any],
            **kwargs: Any
            ) -> Tuple[str, Dict[str, Any]]:
        # get search string
        search: str = self._capture_pattern.match(message['content']).group(1)
        # get host url (removing trailing 'api/')
        base_url: str = client.base_url[:-4]
        # build the full url
        url: str = base_url + Command.path + urllib.parse.quote(search, safe = '')
        # remove requesting message
        client.delete_message(message['id'])
        return lib.build_message(message, Command.msg_template.format(url))
