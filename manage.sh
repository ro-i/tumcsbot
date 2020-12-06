#!/bin/sh

set -e


clean_func () {
	# remove virtual environment
	rm -rf "${dest_dir}/venv"
}


database_func () {
	db="${dest_dir}/tumcsbot.db"

	if [ -e "$db" ]; then
		echo "Database ${db} already exists."
		return
	fi

	touch "$db"
	chmod 0600 "$db"
}

run_func () {
	# enter virtual environment
	. "${dest_dir}/venv/bin/activate"

	# execute bot
	exec "${dest_dir}/src/main.py" "$@" "${dest_dir}/zuliprc" "${dest_dir}/tumcsbot.db"
}

virtualenv_func () {
	# create virtual environment
	python3 -m venv "${dest_dir}/venv"

	# enter virtual environment
	. "${dest_dir}/venv/bin/activate"

	# install dependecies
	pip3 install -r requirements.txt

	# exit virtual environment
	deactivate

	printf '\n\n%s\n\n' '########################################'
	printf '%s' 'TODO for you: Please install the zuliprc for this bot.'
	printf '\n\n%s\n\n\n' '########################################'
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
	'clean')
		clean_func "$@"
		;;
	'database')
		database_func "$@"
		;;
	'run')
		run_func "$@"
		;;
	'virtualenv')
		virtualenv_func "$@"
		;;
esac
