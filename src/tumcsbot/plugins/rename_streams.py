#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

from inspect import cleandoc
from typing import Any, Iterable

from tumcsbot.lib import split, Response
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class RenameStreams(PluginCommandMixin, PluginThread):
    syntax = "rename_streams <stream_name_old>,<stream_name_new>..."
    description = cleandoc(
        """
        Rename stream for every (`stream_name_old`,`stream_name_new`)-tuple \
        passed to this command. The stream names have to be plain names, \
        without `#` or `**`.
        [administrator/moderator rights needed]
        """
    )

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        if not self.client.user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        failed: list[str] = []

        stream_tuples: list[Any] | None = split(
            message["command"], converter=[lambda t: split(t, sep=",", exact_split=2)]
        )
        if stream_tuples is None or None in stream_tuples:
            return Response.error(message)

        for old, new in stream_tuples:
            # Used for error messages.
            line: str = f"{old} -> {new}"

            try:
                old_id: int = self.client.get_stream_id(old)["stream_id"]
            except Exception as e:
                self.logger.exception(e)
                failed.append(line)
                continue

            result: dict[str, Any] = self.client.update_stream(
                {"stream_id": old_id, "new_name": f"'{new}'"}
            )
            if result["result"] != "success":
                failed.append(line)

        if not failed:
            return Response.ok(message)

        response: str = "Failed to perform the following renamings:\n" + "\n".join(
            failed
        )

        return Response.build_message(message, response, msg_type="private")
