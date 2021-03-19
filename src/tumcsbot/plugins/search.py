#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

import urllib.parse

from typing import Any, Dict, Iterable, Union

from tumcsbot.lib import Response
from tumcsbot.plugin import CommandPlugin


class Search(CommandPlugin):
    plugin_name = 'search'
    syntax = 'search <string>'
    description = 'Get a url to a search for "string" in all public streams.'
    msg_template: str = 'Hi, I hope that these search results may help you: {}'
    path: str = '#narrow/streams/public/search/'

    def handle_message(
        self,
        message: Dict[str, Any],
        **kwargs: Any
    ) -> Union[Response, Iterable[Response]]:
        # Get search string and quote it.
        search: str = urllib.parse.quote(message['command'], safe = '')
        # Fix strange behavior of Zulip which does not accept literal periods.
        search = search.replace('.', '%2E')
        # Get host url (removing trailing 'api/').
        base_url: str = self.client.base_url[:-4]
        # Build the full url.
        url: str = base_url + self.path + search
        # Remove requesting message.
        self.client.delete_message(message['id'])
        return Response.build_message(
            message, self.msg_template.format(url)
        )
