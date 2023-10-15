#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Iterable

from tumcsbot.lib import split, validate_and_return_regex, Response
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class ArchiveStreams(PluginCommandMixin, PluginThread):
    syntax = "archive_streams <stream_regex>..."
    description = cleandoc(
        """
        Archive streams according to the given regular expressions, which have
        to match the full stream name.
        Note that only empty streams will be archived.
        [administrator/moderator rights needed]

        Example (note the quoting!):
        ```text
        archive_streams "Test.*" "ABC \\d* class"
        ```
        """
    )

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        if not self.client.user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        stream_regexes: list[Any] | None = split(
            message["command"], converter=[validate_and_return_regex]
        )
        if stream_regexes is None or None in stream_regexes:
            return Response.build_message(message, "Found invalid regular expressions.")

        response: list[str] = []

        for stream_regex in stream_regexes:
            streams: list[str] = self.client.get_streams_from_regex(stream_regex)
            removed: int = 0

            for stream in streams:
                result: dict[str, Any] = self.client.get_stream_id(stream)
                if result["result"] != "success":
                    continue
                stream_id: int = result["stream_id"]

                # Check if stream is empty.
                result = self.client.get_messages(
                    {
                        "anchor": "oldest",
                        "num_before": 0,
                        "num_after": 1,
                        "narrow": [{"operator": "stream", "operand": stream_id}],
                    }
                )
                if result["result"] != "success" or result["messages"]:
                    continue

                # Archive the stream: https://zulip.com/help/archive-a-stream
                result = self.client.delete_stream(stream_id)
                if result["result"] == "success":
                    removed += 1

            response.append(
                f"'{stream_regex}' - found {len(streams)} matching streams, removed {removed}"
            )

        return Response.build_message(message, "\n".join(response))
