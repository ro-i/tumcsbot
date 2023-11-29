#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from shlex import quote
from typing import Any, Iterable

from tumcsbot.lib import (
    split,
    validate_and_return_regex,
    CommandParser,
    Regex,
    Response,
)
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class ArchiveStreams(PluginCommandMixin, PluginThread):
    syntax = cleandoc(
        """
        archive_streams <stream>...
          or archive_streams -r <stream_regex>..."
        """
    )
    description = cleandoc(
        """
        Archive the given streams.
        The list of streams is interpreted in a way that autocompleted
        stream names (à la `#**stream name**`) are auto-detected.
        If the `-r` option is present, select the streams according to the
        given regular expressions, which have to match the full stream name.
        Note that only empty streams will be archived.
        [administrator/moderator rights needed]

        Examples (note the quoting!):
        ```text
        archive_streams "test" "#**abc**"
        archive_streams -r "test.*" "abc \\d* class"
        ```
        """
    )

    def _init_plugin(self) -> None:
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand(
            self.plugin_name(),
            opts={"r": None},
            greedy={"streams": str},
        )

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        result_args: tuple[str, CommandParser.Opts, CommandParser.Args] | None
        streams: list[str]

        if not self.client.user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        result_args = self.command_parser.parse(
            self.plugin_name() + " " + message["command"]
        )
        if result_args is None:
            return Response.command_not_found(message)
        _, opts, args = result_args

        if args.streams is None or None in args.streams:
            return Response.build_message(message, "error parsing given arguments")

        if opts.r:
            # Get the list of streams we would delete, build a new command
            # without regexes that would accomplish this, and ask the user
            # whether they would like to execute it like that.
            streams = self._get_streams_from_regexes(args.streams)
            return Response.build_request_msg(
                message, f"{self.plugin_name()} {' '.join(map(quote, streams))}"
            )
        else:
            streams = []
            for stream in args.streams:
                stream_s: str | None = Regex.get_stream_name(stream)
                if stream_s is None:
                    return Response.build_message(
                        message, f"error: {stream} cannot be parsed"
                    )
                streams.append(stream_s)
            return self._archive_streams(message, streams)

    def _archive_streams(
        self, message: dict[str, Any], streams: list[str]
    ) -> Response | Iterable[Response]:
        failed: list[str] = []

        for stream in streams:
            result: dict[str, Any] = self.client.get_stream_id(stream)
            if result["result"] != "success":
                failed.append(stream)
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
                failed.append(stream)
                continue

            # Archive the stream: https://zulip.com/help/archive-a-stream
            result = self.client.delete_stream(stream_id)
            if result["result"] != "success":
                failed.append(stream)

        if not failed:
            return Response.ok(message)

        return Response.build_message(
            message, f"failed to remove the following stream(s): {failed}"
        )

    def _get_streams_from_regexes(self, stream_regs: list[str]) -> list[str]:
        return [
            stream
            for stream_reg in stream_regs
            for stream in self.client.get_streams_from_regex(stream_reg)
        ]
