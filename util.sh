#!/bin/bash

set -e


install_func () {
	# create virtual environment
	python -m venv "${dest_dir}/tumcsbot_venv"

	# enter virtual environment
	source "${dest_dir}/tumcsbot_venv/bin/activate"

	# install dependecies
	pip install -r requirements.txt

	# exit virtual environment
	deactivate

	# install bot
	install -m 0700 -T ./tumcsbot/tumcsbot.py "${dest_dir}/tumcsbot"

	printf '\n\n%s\n\n' '########################################'
	echo "TODO for you: Please install the zuliprc for this bot in ${dest_dir}"
	printf '\n%s\n\n\n' '########################################'
}

run_func () {
	# enter virtual environment
	source "${dest_dir}/tumcsbot_venv/bin/activate"

	# execute bot
	"${dest_dir}/tumcsbot" "$@" "${dest_dir}/zuliprc"

	# exit virtual environment
	deactivate
}

uninstall_func () {
	# remove virtual environment and bot
	rm -rf "${dest_dir}/tumcsbot_venv" "${dest_dir}/tumcsbot"
}


cmd="$1"
dest_dir="$2"
shift 2

if ! [ -d "$dest_dir" ]; then
	if [ -d "$dest_dir" ]; then
		echo "error: ${dest_dir} is not a directory"
	fi
	mkdir "$dest_dir"
fi

case "$cmd" in
	'install')
		install_func "$@"
		;;
	'run')
		run_func "$@"
		;;
	'uninstall')
		uninstall_func "$@"
		;;
esac
