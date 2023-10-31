#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Manage reactions on certain words or phrases with emojis.

Use the Zulip facility, see https://zulip.com/help/add-an-alert-word.
Provide also an interactive command so administrators are able to
change the alert words and specify the emojis to use for the reactions.
"""

from inspect import cleandoc
from typing import Any, Iterable, Callable

from tumcsbot.lib import CommandParser, DB, Response, Regex
from tumcsbot.plugin import PluginCommandMixin, PluginThread
from tumcsbot.plugins.moderation_reaction_handler import ModerationReactionHandler


class Moderate(PluginCommandMixin, PluginThread):
    _actions = {
        "dm": "sends a message to the author",
        "delete": "deletes the message",
        "respond": "respons to the message",
    }
    # pylint: disable=line-too-long
    _default_config: list[tuple[str, str, str | None, str]] = [
        (
            ":recycle:",
            "dm",
            cleandoc(
                """            Deine Frage wurde bereits woanders gestellt und wurde deshalb gelöscht. Bitte verwende die Suchfunktion um die Antwort für deine Frage zu finden.
                                                        ---
                                                        Your question has already been asked elsewhere and therefore has been deleted. Please use the search function to find the answer to your question.
                                                        ```spoiler Deine ursprüngliche Nachricht in $topic | Your original message in $topic
                                                        $content
                                                        ```
                                                        ---
                                                        Diese Benachrichtigung wurde von $mod beauftragt.
                                                        This notification was issued by $mod.""",
            ),
            "sends a dm to the author that the question has already been asked on zulip",
        ),
        (":recycle:", "delete", None, "deletes the message"),
        (
            ":taking_a_picture:",
            "dm",
            cleandoc(
                """   In deiner Frage hast du ein Foto von deinem Bildschirm gepostet. Deine Nachricht wurde deshalb gelöscht. Bitte verwende formatierten Text für Textausgaben und Screenshots für nicht textuelle Inhalte und stelle deine Frage erneut.
                                                        ---
                                                        In your question, you posted a photo of your screen. Therefore, it was deleted. Please use formatted text for text outputs and screenshots for non-textual content and repost your question.
                                                        ```spoiler Deine ursprüngliche Nachricht in $topic | Your original message in $topic
                                                        $content
                                                        ```
                                                        ---
                                                        Diese Benachrichtigung wurde von $mod beauftragt.
                                                        This notification was issued by $mod.""",
            ),
            "sends a dm to the author that proper formatting should be used instead of pictures or screenshots",
        ),
        (":taking_a_picture:", "delete", None, "deletes the message"),
        (
            ":question:",
            "dm",
            cleandoc(
                """           Deine Frage ist nicht klar genug formuliert oder das Problem ist nicht klar erkennbar und wurde deshalb gelöscht. Bitte versuche genauer auf dein Problem einzugehen und eine klare Frage zu stellen.
                                                        ---
                                                        Your question is not formulated clearly enough, or the problem is not clearly identifiable. Therefore, the message was deleted. Please ask your question again and try to elaborate more on your problem, providing a clear question.
                                                        ```spoiler Deine ursprüngliche Nachricht in $topic | Your original message in $topic
                                                        $content
                                                        ```
                                                        ---
                                                        Diese Benachrichtigung wurde von $mod beauftragt.
                                                        This notification was issued by $mod.""",
            ),
            "sends a dm to the author that he should clarify the question",
        ),
        (
            ":scroll:",
            "dm",
            cleandoc(
                """             Deine Frage wird bereits in der Aufgabenstellung beantwortet und wurde deshalb gelöscht.
                                                        ---
                                                        Your question is already answered in the task description and therefore was deleted.
                                                        ```spoiler Deine ursprüngliche Nachricht in $topic | Your original message in $topic
                                                        $content
                                                        ```
                                                        ---
                                                        Diese Benachrichtigung wurde von $mod beauftragt.
                                                        This notification was issued by $mod.""",
            ),
            "sends a dm to the author that the question has already been answered in the problem statement",
        ),
        (":scroll:", "delete", None, "deletes the message"),
        (
            ":headlines:",
            "dm",
            cleandoc(
                """          Deine Frage hat keinen deskriptiven Topic-Titel oder deine Nachricht gehört nicht in das Topic $topic und wurde deshalb gelöscht. Bitte passe den Topic-Titel an, erstelle ein neues Topic oder poste deine Nachricht in ein passendes Topic.
                                                        ---
                                                        Your question has an ambiguous topic title or does not belong in the topic $topic and therefore was deleted. Please change the topic title, create a new topic, or post your message in an appropriate topic.
                                                        ```spoiler Deine ursprüngliche Nachricht in $topic | Your original message in $topic
                                                        $content
                                                        ```
                                                        ---
                                                        Diese Benachrichtigung wurde von $mod beauftragt.
                                                        This notification was issued by $mod.""",
            ),
            "sends a dm to the author that the question has a bad title or is in the wrong stream",
        ),
        (":headlines:", "delete", None, "deletes the message"),
        (
            ":www:",
            "dm",
            cleandoc(
                """                Deine Nachricht wurde gelöscht. Bitte verwende eine Suchmaschine deiner Wahl, um dein Problem zu lösen oder deine Frage zu beantworten.
                                                        ---
                                                        Your message was deleted. Please use a search engine of your choice to answer your question or solve your problem.
                                                        spoiler
                                                        :stackoverflow:[stackoverflow](https://stackoverflow.com/?q=$escaped_topic)
                                                        [DuckDuckGo](https://duckduckgo.com/?q=$escaped_topic)
                                                        [Google](https://google.com/search?q=$escaped_topic)
                                                        [Bing](https://bing.com/search?q=$escaped_topic)
                                                        [Ecosia](https://ecosia.com/search?q=$escaped_topic)
                                                        [Yahoo](https://yahoo.com/search?q=$escaped_topic)
                                                        [webcrawler](https://www.webcrawler.com/search?q=$escaped_topic)
                                                        ```spoiler Deine ursprüngliche Nachricht in $topic | Your original message in $topic 
                                                        $content
                                                        ```
                                                        ---
                                                        Diese Benachrichtigung wurde von $mod beauftragt.
                                                        This notification was issued by $mod.""",
            ),
            "sends a dm to the author that question should be aswered by searching online (e.g. googeling)",
        ),
        (":www:", "delete", None, "deletes the message"),
        (
            ":crown:",
            "dm",
            cleandoc(
                """              Ich wollte mich herzlich bei dir bedanken für deine herausragende Antwort in unserem Forum. Deine Erklärung war besonders klar und hilfreich. Es ist toll zu sehen, dass so engagierte Studierende wie du dazu beitragen, unser Wissen zu vertiefen. Weiter so:penguin: 
                                                        ---
                                                        I wanted to express my sincere gratitude for your outstanding response in our forum. Your explanation was exceptionally clear and helpful. It's great to see dedicated students like you contributing to deepening our knowledge. Keep up the excellent work:penguin:
                                                        ---
                                                        Diese Benachrichtigung wurde von $mod beauftragt.
                                                        This notification was issued by $mod.""",
            ),
            "sends a dm to the author that his answer is excellent",
        ),
        (
            ":wastebasket:",
            "dm",
            cleandoc(
                """        Deine Nachricht wurde gelöscht.
                                                        ---
                                                        Your question has been deleted.
                                                        ```spoiler Deine ursprüngliche Nachricht in $topic | Your original message in $topic
                                                        $content
                                                        ```
                                                        ---
                                                        Diese Benachrichtigung wurde von $mod beauftragt.
                                                        This notification was issued by $mod.""",
            ),
            "sends a dm to the author that the message was deleted",
        ),
        (":wastebasket:", "delete", None, "deletes the message"),
        (
            ":document:",
            "dm",
            cleandoc(
                """        Deine Nachricht wurde gelöscht. Bitte verwende die offizielle Dokumentation, um dein Problem zu lösen oder deine Frage zu beantworten.
                                                        ---
                                                        Your question has been deleted. Please use the official documentation to answer your question or solve your problem.
                                                        ```spoiler Deine ursprüngliche Nachricht in $topic | Your original message in $topic
                                                        $content
                                                        ```
                                                        ---
                                                        Diese Benachrichtigung wurde von $mod beauftragt.
                                                        This notification was issued by $mod.""",
            ),
            "sends a dm to the author that the question should be answered by looking at the official documentation",
        ),
        (":document:", "delete", None, "deletes the message"),
    ]
    # pylint: enable=line-too-long

    _list_reaction_sql: str = "select * from ReactionConfig"
    _insert_reaction_sql: str = (
        "insert or ignore into ReactionConfig values (?, ?, ?, ?, ?)"
    )
    _delete_reaction_sql: str = "delete from ReactionConfig where "

    _list_authorized_streams_sql: str = "select a.StreamId from GroupAuthorization a, UserGroupMembers m where a.GroupId = m.GroupId and m.UserId = ?"
    _list_authorization_sql: str = "select * from GroupAuthorization"
    _insert_authorization_sql: str = (
        "insert or ignore into GroupAuthorization values (?, ?)"
    )
    _delete_authorization_sql: str = "delete from GroupAuthorization where "

    @staticmethod
    def parse_action(s: str) -> str:
        if s in Moderate._actions:
            return s
        raise ValueError

    @staticmethod
    def parse_action_or_number(s: str) -> str:
        try:
            return Moderate.parse_action(s)
        except:
            return str(int(s))

    def _init_plugin(self) -> None:
        # Get own database connection.
        self._db: DB = DB()
        # Check for database table.
        self._db.checkout_table(
            "ReactionConfig",
            "(UserId integer not null, Emote text not null, Action text, Message text, Description text)",
        )

        self._db.checkout_table(
            "GroupAuthorization",
            "(GroupId integer not null, StreamId integer not null, primary key(GroupId, StreamId))",
        )
        self._db.checkout_table(
            "UserGroups",
            "(GroupId integer primary key, UGroup text unique)",
        )
        self._db.checkout_table(
            "UserGroupMembers",
            "(GroupId integer not null, UserId integer not null, primary key (GroupId, UserId))",
        )

        # pylint: disable=line-too-long
        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand(
            "list",
            optionals={"user": Regex.match_user_argument},
            opts={"a": None, "all": None, "v": None, "verbose": None},
            description=cleandoc(
                """
                list moderation configuration for a users.
                - `user` : the user for which the config should be displayed. Defaults to the sender of the command
                - `-a, --all` : option to display configuration for all users
                - `-v, --verbose` : additionaly show the actions taken for each reaction
                """
            ),
        )

        actions_str = "\n" + "\n".join([f"  - `{a}`" for a in self._actions]) + "\n"
        supported_variables = "\n".join(
            [
                f"  - `${name}`: {desc}"
                for name, (_, desc) in ModerationReactionHandler._replace_dict.items()
            ]
        )

        self.command_parser.add_subcommand(
            "add",
            args={"reaction": Regex.match_reaction_argument, "action": Moderate.parse_action},
            optionals={"user": Regex.match_user_argument, "message": str, "description": str},
            description=cleandoc(
                """
                Add an moderation configuration for a user.
                - `reaction` : the reaction that should trigger an action
                - `action` : the action that should be triggered. Supported actions are:
                """
            )
            + actions_str
            + cleandoc(
                """
                - `user` : the user this configuration should be addded. Defaults to the sender of the command
                - `message` : the message an action should use. The message may use special variables that are replaced depending on the context. Supported variables for message content:
                """
            )
            + supported_variables,
        )

        self.command_parser.add_subcommand(
            "remove",
            optionals={
                "user": Regex.match_user_argument,
                "reaction": Regex.match_reaction_argument,
                "action": Moderate.parse_action_or_number,
            },
            description=cleandoc(
                """
                
                Remove reactions from a configuration
                - `user` : the user the reaction should be removed from. Defaults to the sender of the command
                - `reaction` : the reaction that should be affected. Defaults to all reactions
                - `action` : the action that should be removed. May be the action keyword or the number of the action-element (starting with 1)
                """
            ),
        )

        self.command_parser.add_subcommand(
            "authorize",
            args={"group": str},
            greedy={"streams": str},
            description=cleandoc(
                """
                Authorize a group to allow moderation in streams
                - `group` : the group that should be granted moderation rights
                - `streams` : the streams that users in `<group>` should be able to moderate
                """
            ),
        )

        self.command_parser.add_subcommand(
            "revoke",
            optionals={"group": Regex.match_group_argument, "stream": Regex.match_stream_argument},
            description=cleandoc(
                """
                Remove authorization
                - `group` : the group that should be revoked. If `stream` is not specified, permissions for all streams are revoked for this group
                - `stream` : the stream that should be revoked. If `group` is not specified, permissions of all groups are revoked for this stream
                """
            ),
        )

        defaults_str = ", ".join(set([e for e, _, _, desc in self._default_config]))
        self.command_parser.add_subcommand(
            "defaults",
            greedy={"users": Regex.match_user_argument},
            description=cleandoc(
                """
                Set the actions for [
                """
            )
            + defaults_str
            + cleandoc(
                """] to their defaults
                - `users` : the users that should get their default reactions set
                """
            ),
        )
        # pylint: enable=line-too-long

        self.syntax = self.command_parser.generate_syntax()
        self.description = self.command_parser.generate_description()
        self.update_plugin_usage()

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        result: tuple[str, CommandParser.Opts, CommandParser.Args] | None
        _: list[tuple[Any, ...]]

        # Get command and parameters.
        result = self.command_parser.parse(message["command"])
        self.logger.debug(result)
        if result is None:
            return Response.command_not_found(message)
        command, opts, args = result

        if command in self.command_parser.commands:
            func: Callable[
                [dict[str, Any], CommandParser.Args, CommandParser.Opts],
                Response | Iterable[Response],
            ] = getattr(self, "_" + command)
            return func(message, args, opts)

        return Response.command_not_found(message)

    def _list(
        self,
        message: dict[str, Any],
        args: CommandParser.Args,
        opts: CommandParser.Opts,
    ) -> Response | Iterable[Response]:
        user_id: int | None
        uid: int

        if args.user is not None:
            user_id = self.client.get_user_id_by_name(args.user)
            if user_id is None:
                return Response.build_message(
                    message, f"User not found: {args.user}", msg_type="private"
                )
            uid = user_id
        else:
            uid = message["sender_id"]
            user_result = self.client.get_user_by_id(uid)
            if user_result["result"] != "success":
                return Response.build_message(
                    message, f"User with id {uid} not found.", msg_type="private"
                )
            args.user = f"@_**{user_result['user']['full_name']}|{user_result['user']['user_id']}**"

        if not self.client.user_is_privileged(message["sender_id"]) and (
            message["sender_id"] != uid or opts.all or opts.a
        ):
            return Response.privilege_err(message)

        if self.client.user_is_privileged(message["sender_id"]) and (
            opts.all or opts.a
        ):
            responses = [
                response
                for user_id, config in self.get_config_dict().items()
                for response in self.format_config(
                    message, user_id, config, opts.v or opts.verbose
                )
            ]
            if not opts.verbose and not opts.v:
                responses.append(
                    Response.build_message(
                        message, "*hint: use option -v to see detailed description*"
                    )
                )

            return responses

        cfg = self.get_config_dict()

        if uid not in cfg:
            return Response.build_message(
                message, f"{args.user} does not have any reaction configuration"
            )

        if cfg:
            responses_single = self.format_config(
                message, uid, cfg[uid], opts.v or opts.verbose
            )
            if not opts.verbose and not opts.v:
                responses_single.append(
                    Response.build_message(
                        message, "*hint: use option -v to see detailed description*"
                    )
                )
            return responses_single

        return Response.privilege_err(message)

    def _add(
        self,
        message: dict[str, Any],
        args: CommandParser.Args,
        _: CommandParser.Opts,
    ) -> Response | Iterable[Response]:
        user_id: int | None
        uid: int
        description: str

        if args.user is not None:
            user_id = self.client.get_user_id_by_name(args.user)
            if user_id is None:
                return Response.build_message(
                    message, f"User not found: {args.user}", msg_type="private"
                )
            uid = user_id
        else:
            uid = message["sender_id"]
            user_result = self.client.get_user_by_id(uid)
            if user_result["result"] != "success":
                return Response.build_message(
                    message,
                    f"Error: User with id {uid} not found.",
                    msg_type="private",
                )
            args.user = f"@_**{user_result['user']['full_name']}|{user_result['user']['user_id']}**"

        if (
            not self.client.user_is_privileged(message["sender_id"])
            and message["sender_id"] != uid
        ):
            return Response.privilege_err(message)

        if args.action not in self._actions:
            return Response.build_message(
                message,
                f"Error: '{args.action}' is not a valid action.",
                msg_type="private",
            )

        if args.description is None:
            description = self._actions[args.action]
        else:
            description = args.description

        self._db.execute(
            self._insert_reaction_sql,
            uid,
            args.reaction,
            args.action,
            args.message,
            description,
            commit=True,
        )
        return Response.ok(message)

    def _defaults(
        self,
        message: dict[str, Any],
        args: CommandParser.Args,
        _: CommandParser.Opts,
    ) -> Response | Iterable[Response]:
        responses = []
        uid = message["sender_id"]
        user_result = self.client.get_user_by_id(uid)
        if user_result["result"] != "success":
            return Response.build_message(
                message,
                f"Error: User with id {uid} not found.",
                msg_type="private",
            )
        sender_user_name = (
            f"@_**{user_result['user']['full_name']}|{user_result['user']['user_id']}**"
        )

        if len(args.users) == 0:
            args.users.append(sender_user_name)

        for user in args.users:
            user_id = self.client.get_user_id_by_name(user)

            if user_id is None:
                responses.append(
                    Response.build_message(
                        message, f"User not found: {user}", msg_type="private"
                    )
                )
                continue

            if user_id != message["sender_id"] and not self.client.user_is_privileged(
                message["sender_id"]
            ):
                responses.append(
                    Response.build_message(
                        message,
                        f"You are not privileged to edit the reaction config for {user}",
                        msg_type="private",
                    )
                )
                continue

            for emote_str, action_str, msg_str, desc in self._default_config:
                db_cmd = (
                    self._delete_reaction_sql
                    + f" Emote = '{emote_str}' and UserId = {user_id}"
                )
                self._db.execute(db_cmd, commit=True)

            reactions: set[str] = set()
            for emote_str, action_str, msg_str, desc in self._default_config:
                self._db.execute(
                    self._insert_reaction_sql,
                    user_id,
                    emote_str,
                    action_str,
                    msg_str,
                    desc,
                    commit=True,
                )
                reactions.add(emote_str)

            reaction_str = " \n".join(
                [
                    f" - {emote}: {self.reaction_description(user_id, emote)}"
                    for emote in reactions
                ]
            )
            responses.append(
                Response.build_message(
                    message=None,
                    content=f"Hey,\nthe following reactions have been updated for you by {sender_user_name}:\n{reaction_str}\nThese reactions have the above described effect in streams you are authorized.\n\n*hint: use the moderate command for more information*",
                    msg_type="private",
                    to=[user_id],
                )
            )

        responses.append(Response.ok(message))
        return responses

    def _authorize(
        self,
        message: dict[str, Any],
        args: CommandParser.Args,
        _: CommandParser.Opts,
    ) -> Response | Iterable[Response]:
        if not self.client.user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        res = []
        gid_opt = self.get_group_id_by_name(args.group)
        if gid_opt is None or gid_opt not in [g["id"] for g in self.get_groups()]:
            return Response.build_message(
                message, f"Error: No such group: {args.group}", msg_type="private"
            )
        gid: int = gid_opt
        successful_streams = []
        for stream in args.streams:
            stream_id = self.client.get_stream_id_by_name(stream)

            if stream_id is None:
                res.append(
                    Response.build_message(
                        message,
                        f"Error: Stream not found: {stream}",
                        msg_type="private",
                    )
                )
                continue
            self._db.execute(
                self._insert_authorization_sql, gid, stream_id, commit=True
            )
            successful_streams.append(stream)

        members = self.get_group_members(gid)
        if members is None:
            res.append(
                Response.build_message(
                    message,
                    f"Error: Could net get group members from group: {args.group}",
                    msg_type="private",
                )
            )
        else:
            streams_str = ", ".join(successful_streams)
            for member in members:
                res.append(
                    Response.build_message(
                        message=None,
                        content=f"Hey,\nthe group '{args.group}' you are a member of has been granted moderation rights for the following streams:\n[{streams_str}]\n\n*hint: use the moderate command for more information*",
                        msg_type="private",
                        to=[member],
                    )
                )

        if len(res) == 0:
            res.append(Response.ok(message))
        return res

    def _revoke(
        self,
        message: dict[str, Any],
        args: CommandParser.Args,
        _: CommandParser.Args,
    ) -> Response | Iterable[Response]:
        db_filters = []
        responses = []

        if not self.client.user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        if not args.stream and not args.group:
            return Response.build_message(
                message,
                "Error: At least a stream or a group must be specified.",
                msg_type="private",
            )

        if args.stream is not None:
            stream_id = self.client.get_stream_id_by_name(args.stream)
            if stream_id is None:
                return Response.build_message(
                    message,
                    f"Error: Stream not found: {args.stream}",
                    msg_type="private",
                )
            db_filters.append(f"StreamId = '{stream_id}'")

        if args.group is not None:
            group_id = self.get_group_id_by_name(args.group)
            if group_id is None:
                return Response.build_message(
                    message,
                    f"Error: Group not found: {args.group}",
                    msg_type="private",
                )
            db_filters.append(f"GroupId = '{group_id}'")

            members = self.get_group_members(group_id)
            if members is None:
                responses.append(
                    Response.build_message(
                        message,
                        f"Error: Could net get group members from group: {args.group}",
                        msg_type="private",
                    )
                )
            else:
                stream_str = (
                    " for the stream " + args.stream if args.stream is not None else ""
                )
                for member in members:
                    responses.append(
                        Response.build_message(
                            message=None,
                            content=f"Hey,\nmoderation rights of the group {args.group} you are a member of has been withdrawn{stream_str}\n\n*hint: use the moderate command for more information*",
                            msg_type="private",
                            to=[member],
                        )
                    )

        db_cmd = self._delete_authorization_sql + " and ".join(db_filters)
        self.logger.debug(db_cmd)
        self._db.execute(db_cmd, commit=True)
        responses.append(Response.ok(message))
        return responses

    def _remove(
        self,
        message: dict[str, Any],
        args: CommandParser.Args,
        _: CommandParser.Opts,
    ) -> Response | Iterable[Response]:
        user_id = message["sender_id"]
        db_filters = []
        end_str = ""

        if message["sender_id"] != user_id and not self.client.user_is_privileged(
            message["sender_id"]
        ):
            return Response.privilege_err(message)

        if args.action and not args.reaction:
            return Response.build_message(
                message, "Error: Missing argument: reaction", msg_type="private"
            )

        if args.user is not None:
            user_id = self.client.get_user_id_by_name(args.user)
            if user_id is None:
                return Response.build_message(
                    message, f"Error: User not found: {args.user}", msg_type="private"
                )
            db_filters.append(f"UserId = {user_id}")

        if args.reaction is not None:
            db_filters.append(f"Emote = '{args.reaction}'")

            end_str = ""
            if args.action is not None:
                end_str = f"and Action = '{args.action}'"
                try:
                    idx = int(args.action)
                    end_str = f"LIMIT {idx}-1,1"
                except:
                    pass

        db_cmd = self._delete_reaction_sql + " and ".join(db_filters) + end_str
        self.logger.debug(db_cmd)
        self._db.execute(db_cmd, commit=True)
        return Response.ok(message)

    def get_config_dict(self) -> dict[int, dict[str, list[dict[str, str]]]]:
        dict_result: dict[int, dict[str, list[dict[str, str]]]] = {}
        db_result = self._db.execute(self._list_reaction_sql)
        for user_id, _, _, _, _ in db_result:
            dict_result[user_id] = {}

        for user_id, emote, _, _, _ in db_result:
            dict_result[user_id][emote] = []

        for user_id, emote, action, msg, desc in db_result:
            if msg:
                dict_result[user_id][emote].append(
                    {"action": action, "msg": msg, "description": desc}
                )
            else:
                dict_result[user_id][emote].append(
                    {"action": action, "description": desc}
                )

        return dict_result

    def format_config(
        self,
        message: dict[str, Any],
        user_id: int,
        cfg: dict[str, list[dict[str, str]]],
        verbose: bool = False,
    ) -> list[Response]:
        responses = []
        user_result = self.client.get_user_by_id(user_id)
        if user_result["result"] != "success":
            return [
                Response.build_message(
                    message, f"User with id {user_id} not found.", msg_type="private"
                )
            ]
        user_name = (
            f"@_**{user_result['user']['full_name']}|{user_result['user']['user_id']}**"
        )
        msg = f"## Configuration for {user_name}\n"

        streams = []
        for stream_id in map(
            lambda x: x[0], self._db.execute(self._list_authorized_streams_sql, user_id)
        ):
            stream = self.client.get_stream_by_id(stream_id)
            if stream is None:
                responses.append(
                    Response.build_message(
                        message, f"Error: Stream with id {stream_id} not found."
                    )
                )
            else:
                streams.append(f"#**{stream['name']}**")

        msg += "**Authorized streams:**\n[" + ", ".join(streams) + "]"
        msg += "\n**Configured reactions**"
        if verbose:
            for emote, actions in cfg.items():
                msg += f"\n---\n**{emote}**\n"
                for a in actions:
                    if "msg" in a:
                        msg += f" - `{a['action']}`\n```text\n{a['msg'].replace('```', '````')}\n```\n"
                    else:
                        msg += f" - `{a['action']}`\n\n"
        else:
            msg += (
                " \n".join(
                    [
                        f" - {emote}: {self.reaction_description(user_id, emote)}"
                        for emote in cfg.keys()
                    ]
                )
                + "\n"
            )

        responses.append(Response.build_message(message, msg))
        return responses

    def reaction_description(self, user_id: int, reaction: str) -> str:
        return " and ".join(
            [e["description"] for e in self.get_config_dict()[user_id][reaction]]
        )

    # TODO: replacement for zulip usergroups. Rreplace as soon as api allows bot requests for usergroups
    def get_groups(self) -> list[dict[str, Any]]:
        res_groups = self._db.execute("select * from UserGroups")
        if res_groups is None:
            return []

        groups: list[dict[str, Any]] = []
        for group_id, group_name in res_groups:
            memers_res = self._db.execute(
                "select m.UserId from UserGroups g, UserGroupMembers m where m.GroupId = ?",
                group_id,
            )
            members: list[int] = []
            if memers_res is not None:
                members = [t[0] for t in memers_res]
            groups.append({"id": group_id, "name": group_name, "members": members})

        return groups

    def get_group_id_by_name(self, group_name: str) -> int | None:
        res = self._db.execute(
            "select GroupId from UserGroups where UGroup = ? LIMIT 1", group_name
        )
        if not res or len(res) == 0:
            return None
        i: int = res[0][0]
        return i

    def group_id_by_identifier(self, identifier: int | str) -> int | None:
        if isinstance(identifier, int):
            return int(identifier)
        res = self._db.execute(
            "select GroupId from UserGroups where UGroup = ? LIMIT 1", identifier
        )
        if not res or len(res) == 0:
            return None
        i: int = res[0][0]
        return i

    def get_group_by_identifier(self, identifier: int | str) -> dict[str, Any] | None:
        gid = self.group_id_by_identifier(identifier)
        if gid is None:
            return None
        res_name = self._db.execute(
            "select UGroup from UserGroups where GroupId = ? LIMIT 1", gid
        )
        res_members = self._db.execute(
            "select UserId from UserGroupMembers where GroupId = ?", gid
        )
        if res_members is None or res_name is None or len(res_name) == 0:
            return None
        g: dict[str, Any] = {
            "id": gid,
            "name": res_name[0][0],
            "members": [t[0] for t in res_members],
        }
        return g

    def get_group_members(self, identifier: int | str) -> list[int]:
        g = self.get_group_by_identifier(identifier)
        if g is None:
            return []
        members: list[int] = g["members"]
        return members
