TUM CS Bot
==========

An interactive bot for zulip.in.tum.de, the [Zulip Chat](https://zulipchat.com/)
of the Department of Informatics of the Technichal University of Munich.

**Note: This bot is currently under development and not yet production-ready!**


setup
-----

Currently, no special setup required. The bot only needs its `zuliprc` file
which you receive when adding the bot to your Zulip instance. Currently, the
bot is intended to run as `Generic` bot, owned by an administrator.
- [add a bot](https://zulipchat.com/help/add-a-bot-or-integration)
- [about bots](https://zulipchat.com/help/bots-and-integrations)

Note: For some commands such as `subscribe` or `solved` the bot needs
administrator and `api_super_user` rights.
([documentation for Zulip 3.x](https://github.com/zulip/zulip/blob/3.x/docs/production/security-model.md)).
In order to grant those rights, run
- `manage.py knight --for-real --permission=administer <bot_email>` (Zulip <= 3.2)
- `manage.py change_user_role -r REALM_ID <bot_email> admin` and
  `manage.py change_user_role -r REALM_ID <bot_email> administrator`
in the appropriate directory of your zulip server installation.


usage
-----

- `make init` will create the database `tumcsbot.db` and install a virtual
  environment into `venv`.
- `make run` lets you run the bot.
- `make debug` runs the bot with debug logging enabled.

You can also run the bot manually:
```
usage: main.py [-h] [-d] [-l LOGFILE] ZULIPRC DB_PATH

TUM CS Bot - a generic Zulip bot.

This bot is currently especially intended for administrative tasks.
It supports several commands which can be written to the bot using
a private message or a message starting with @mentioning the bot.

positional arguments:
  ZULIPRC               zuliprc file containing the bot's configuration
  DB_PATH               path to the bot's database

optional arguments:
  -h, --help            show this help message and exit
  -d, --debug           print debug information on the console
  -l LOGFILE, --logfile LOGFILE
                        use LOGFILE for logging output
```


usage in chat
-------------
Write the word `help` to the bot - as private message or using
`@<tumcsbot-name> help`. It will tell you how you can use it. :-)


notes
-----

My work on the possibility of accessing a file that the sender has added to a
message using the "Attach files" function and my questions about this topic on
chat.zulip.org have led to the corresponding issue on github:
https://github.com/zulip/python-zulip-api/issues/628

The bot supports a dynamic plugin infrastructure and also generates the help
message dynamically by using appropriate attributes every plugin has to
provide.

[mypy](https://github.com/python/mypy) with `--strict` should not show any
significant warnings.


model
-----

![class diagram](./class_diagram.svg?)

