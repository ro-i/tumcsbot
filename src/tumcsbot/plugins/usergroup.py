#!/usr/bin/env python3

# See LICENSE file for copyright and license details.
# TUM CS Bot - https://github.com/ro-i/tumcsbot

"""Manage reactions on certain words or phrases with emojis.

Use the Zulip facility, see https://zulip.com/help/add-an-alert-word.
Provide also an interactive command so administrators are able to
change the alert words and specify the emojis to use for the reactions.
"""

from typing import Any, Iterable, Callable
from inspect import cleandoc

from tumcsbot.lib import CommandParser, DB, Response, Regex
from tumcsbot.plugin import PluginCommandMixin, PluginThread


class Usergroup(PluginCommandMixin, PluginThread):
    _remove_group_sql: str = "delete from UserGroups where UGroup = ?"
    _remove_user_from_group_sql: str = (
        "delete from UserGroups where UGroup = ? and UserId = ?"
    )
    _list_sql: str = "select * from UserGroups"
    _list_user_sql: str = "select UGroup from UserGroups where UserId = ?"
    _insert_sql: str = "insert or ignore into UserGroups (UGroup, UserId) values (?, ?)"
    _delete_sql: str = "delete from UserGroups where "

    _create_group_sql: str = "insert or ignore into UserGroups (UGroup) values (?)"
    _get_group_id_sql: str = "select GroupId from UserGroups where UGroup = ?"
    # _get_groups_for_

    def _init_plugin(self) -> None:
        # Get own database connection.
        self._db: DB = DB()
        # Check for database table.
        self._db.checkout_table(
            "UserGroups",
            "(GroupId integer primary key autoincrement, UGroup text unique)",
        )
        self._db.checkout_table(
            "UserGroupMembers",
            "(GroupId integer not null, UserId integer not null, primary key (GroupId, UserId))",
        )

        self.command_parser: CommandParser = CommandParser()
        self.command_parser.add_subcommand(
            "list",
            optionals={"user": Regex.match_user_argument},
            opts={"a": None, "all": None},
            description=cleandoc(
                """
                list user groups
                - `user` : the user for which the groups should be listed
                - `-a, --all` : option to display all user groups with all users
                """
            ),
        )
        self.command_parser.add_subcommand(
            "creat",
            args={"name": str, "description": str},
            description=cleandoc(
                """
                create an empty user group
                - `name` : the name of the user group
                - `description` : the description for the user group (required for portability with builtin zulip usergroups)
                """
            ),
        )
        self.command_parser.add_subcommand(
            "remove",
            optionals={"user": Regex.match_user_argument, "group": Regex.match_group_argument},
            description=cleandoc(
                """
                remove user from groups
                - `user` : the user that should get removed. If no group is not specified, the user gets removed from all groups
                - `group` : the group the user should get removed from. If no user is not specified, all users gets removed from this groups
                """
            ),
        )
        self.command_parser.add_subcommand(
            "add",
            greedy={"groups": Regex.match_group_argument, "users": Regex.match_user_argument},
            description=cleandoc(
                """
                remove users to groups
                - `user` : the user that should get added to groups
                - `group` : the groups the users should get added to
                """
            ),
        )

        self.syntax = self.command_parser.generate_syntax()
        self.description = self.command_parser.generate_description()
        self.update_plugin_usage()

    def handle_message(self, message: dict[str, Any]) -> Response | Iterable[Response]:
        result: tuple[str, CommandParser.Opts, CommandParser.Args] | None

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
            self.logger.debug(f"executing subcommand: {command}")
            self.logger.debug(f"args: {args}")
            self.logger.debug(f"opts: {opts}")
            return func(message, args, opts)
        else:
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
            if user_result is None or user_result["result"] != "success":
                return Response.build_message(
                    message, f"User with id {uid} not found.", msg_type="private"
                )

            args.user = f"@_**{user_result['user']['full_name']}|{user_result['user']['user_id']}**"

        if opts.a or opts.all:
            if not self.client.user_is_privileged(message["sender_id"]):
                return Response.privilege_err(message)

            groups = self.get_groups()
            result_dict: dict[str, list[str]] = {}
            for group in groups:
                group_name = group["name"]
                result_dict[group_name] = list()
                for uid in group["members"]:
                    user_result = self.client.get_user_by_id(uid)
                    if user_result["result"] != "success":
                        return Response.build_message(
                            message,
                            f"An error occurred while querying user with ID {uid}",
                            msg_type="private",
                        )
                    result_dict[group_name].append(
                        f"@_**{user_result['user']['full_name']}|{uid}**"
                    )

            result_list = [
                f"## {group}:\n[" + ", ".join(users) + "]"
                for group, users in result_dict.items()
            ]
            return Response.build_message(
                message,
                "# Usergroups:\n" + "\n".join(result_list),
                msg_type="private",
            )
        else:
            if message["sender_id"] != uid and not self.client.user_is_privileged(
                message["sender_id"]
            ):
                return Response.privilege_err(message)

            group_list = [g for g in self.get_groups() if uid in g["members"]]

            if len(group_list) == 0:
                return Response.build_message(
                    message, f"{args.user} is not in any user group", msg_type="private"
                )

            msg = ", ".join(f"`{g['name']}`" for g in group_list)
            return Response.build_message(
                message,
                f"{args.user} is in the following user groups: {msg}",
                msg_type="private",
            )

    def _add(
        self, message: dict[str, Any], args: CommandParser.Args, _: CommandParser.Opts
    ) -> Response | Iterable[Response]:
        if not self.client.user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        failures: dict[str, list[str]] = {}
        success: dict[str, list[str]] = {}

        if len(args.users) == 0 or len(args.groups) == 0:
            return Response.build_message(
                message,
                "Error: At least one user and one group must be specified.",
                msg_type="private",
            )

        for user in args.users:
            success[user] = list()
            failures[user] = list()
            for group in args.groups:
                if not self.add_user_to_group(user, group):
                    failures[user].append(group)
                else:
                    success[user].append(group)

        responses = []

        for user, groups in failures.items():
            if len(groups) > 0:
                groups_str = ", ".join(groups)
                responses.append(
                    Response.build_message(
                        message,
                        f"Error: Could not add user '{user}' to groups '{groups_str}'",
                        msg_type="private",
                    )
                )

        for user, groups in success.items():
            if len(groups) > 0:
                uid = self.client.get_user_id_by_name(user)
                if uid:
                    groups_str = ", ".join([f"`{g}`" for g in groups])
                    responses.append(
                        Response.build_message(
                            message=None,
                            msg_type="private",
                            content=f"Hey,\nYou have been added to the following user groups by @_**{message['sender_full_name']}|{message['sender_id']}**:\n{groups_str}",
                            to=[uid],
                        )
                    )
                else:
                    groups_str = ", ".join(groups)
                    responses.append(
                        Response.build_message(
                            message,
                            f"Error: Could not find id for user {user}.",
                            msg_type="private",
                        )
                    )
        responses.append(Response.ok(message))
        return responses

    def _creat(
        self, message: dict[str, Any], args: CommandParser.Args, _: CommandParser.Opts
    ) -> Response | Iterable[Response]:
        if not self.client.user_is_privileged(message["sender_id"]):
            return Response.privilege_err(message)

        success = self.create_group(args.name, args.description)

        if not success:
            return Response.build_message(
                message,
                f"Error: Could not create group '{args.name}' with description '{args.description}'.",
                msg_type="private",
            )

        return Response.ok(message)

    def _remove(
        self, message: dict[str, Any], args: CommandParser.Args, _: CommandParser.Opts
    ) -> Response | Iterable[Response]:
        user_id = None

        if args.user is not None:
            user_id = self.client.get_user_id_by_name(args.user)
            if user_id is None:
                return Response.build_message(
                    message, f"Error: User not found: {args.user}", msg_type="private"
                )

        if (
            user_id
            and message["sender_id"] != user_id
            and not self.client.user_is_privileged(message["sender_id"])
        ):
            return Response.privilege_err(message)

        responses = []
        if args.user is not None and args.group is not None:
            self.remove_user_from_group(args.user, args.group)
            uid = self.client.get_user_id_by_name(args.user)
            if uid:
                responses.append(
                    Response.build_message(
                        message=None,
                        msg_type="private",
                        content=f"Hey,\nYou have been removed to the following user group by @_**{message['sender_full_name']}|{message['sender_id']}**:\n`{args.group}`",
                        to=[uid],
                    )
                )
            else:
                responses.append(
                    Response.build_message(
                        message,
                        f"Error: Could not find id for user {args.user}.",
                        msg_type="private",
                    )
                )
        elif args.user is not None:
            uid = self.client.get_user_id_by_name(args.user)
            if not uid:
                responses.append(
                    Response.build_message(
                        message,
                        f"Error: Could not find id for user {args.user}.",
                        msg_type="private",
                    )
                )
            else:
                groups = self.get_groups_for_user(args.user)
                for gid in groups:
                    self.remove_user_from_group(args.user, gid)
                print(groups)
                names = [
                    g_dict["name"]
                    for g_dict in [self.get_group_by_identifier(g) for g in groups]
                    if g_dict
                ]
                print([self.get_group_by_identifier(g) for g in groups])
                print("§" * 100)
                names_str = ", ".join([f"`{n}`" for n in names])
                responses.append(
                    Response.build_message(
                        message=None,
                        msg_type="private",
                        content=f"Hey,\nYou have been removed from the following user groups by @_**{message['sender_full_name']}|{message['sender_id']}**:\n[{names_str}]",
                        to=[uid],
                    )
                )
        elif args.group is not None:
            for member in self.get_group_members(args.group):
                responses.append(
                    Response.build_message(
                        message=None,
                        msg_type="private",
                        content=f"Hey,\nYou have been removed from the following user group by @_**{message['sender_full_name']}|{message['sender_id']}**:\n`{args.group}`",
                        to=[member],
                    )
                )
            self.delete_group(args.group)
        else:
            return Response.build_message(
                message,
                f"Error: At least a user or a group must be specified.",
                msg_type="private",
            )

        responses.append(Response.ok(message))
        return responses

    # TODO: replacement for zulip usergroups. Rreplace as soon as api allows bot requests for usergroups
    def get_groups(self) -> list[dict[str, Any]]:
        res_groups = self._db.execute("select * from UserGroups")
        if res_groups is None:
            return []

        groups: list[dict[str, Any]] = []
        for group_id, group_name in res_groups:
            memers_res = self._db.execute(
                "select UserId from UserGroupMembers where GroupId = ?",
                group_id,
            )
            members: list[int] = []
            if memers_res is not None:
                members = [t[0] for t in memers_res]
            groups.append({"id": group_id, "name": group_name, "members": members})

        return groups

    def create_group(self, name: str, _: str) -> bool:
        self._db.execute(
            "insert or ignore into UserGroups (UGroup) values (?)",
            name,
            commit=True,
        )
        return True

    def delete_group(self, identifier: int | str) -> bool:
        gid = self.group_id_by_identifier(identifier)
        if gid is None:
            return False
        self._db.execute(
            "delete from UserGroups where GroupId = ?",
            gid,
            commit=True,
        )
        self._db.execute(
            "delete from UserGroupMembers where GroupId = ?",
            gid,
            commit=True,
        )
        return True

    def remove_user_from_group(
        self, user_identifier: int | str, group_identifier: int | str
    ) -> bool:
        uid = self.user_id_by_identifier(user_identifier)
        gid = self.group_id_by_identifier(group_identifier)
        if uid is None or gid is None:
            return False
        self._db.execute(
            "delete from UserGroupMembers where GroupId = ? and UserId = ?",
            gid,
            uid,
            commit=True,
        )
        return True

    def add_user_to_group(
        self, user_identifier: int | str, group_identifier: int | str
    ) -> bool:
        uid = self.user_id_by_identifier(user_identifier)
        gid = self.group_id_by_identifier(group_identifier)
        if uid is None or gid is None:
            return False
        self._db.execute(
            "insert or ignore into UserGroupMembers values (?, ?)",
            gid,
            uid,
            commit=True,
        )
        return True

    def get_groups_for_user(self, user_identifier: int | str) -> list[int]:
        uid = self.user_id_by_identifier(user_identifier)
        res = self._db.execute(
            "select g.GroupId from UserGroups g, UserGroupMembers m where m.GroupId = g.GroupId and m.UserId = ?",
            uid,
        )
        if not res or len(res) == 0:
            return []
        return [i[0] for i in res]

    def get_group_id_by_name(self, group_name: str) -> int | None:
        res = self._db.execute(
            "select GroupId from UserGroups where UGroup = ? LIMIT 1", group_name
        )
        if not res or len(res) == 0:
            return None
        i: int = res[0][0]
        return i

    def group_id_by_identifier(self, identifier: int | str) -> int | None:
        print(type(identifier))
        print(isinstance(identifier, int))
        if isinstance(identifier, int):
            print(int(identifier))
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

    def user_id_by_identifier(self, identifier: int | str) -> int | None:
        if isinstance(identifier, int):
            return int(identifier)
        return self.client.get_user_id_by_name(str(identifier))
