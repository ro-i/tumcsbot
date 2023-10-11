#!/bin/sh

set -e


_command_exists_or_exit () {
    if ! type "$1" > /dev/null; then
        echo "$1 not found"
        exit 1
    fi
}

_enter_venv () {
    if ! $virtualenv; then
        return
    fi

    # enter virtual environment
    . "${dest_dir}/venv/bin/activate"
}

clean_func () {
    if ! $virtualenv; then
        return
    fi

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

env_func () {
    if $virtualenv; then
        # create virtual environment
        python3 -m venv "${dest_dir}/venv"
    fi

    _enter_venv

    # install dependecies
    pip3 install -r "${dest_dir}/requirements.txt"

    printf '\n\n%s\n\n' '########################################'
    printf '%s' 'TODO for you: Please install the zuliprc for this bot.'
    printf '\n\n%s\n\n\n' '########################################'
}

init_func () {
    database_func
    env_func
}

migrations_func () {
    "${dest_dir}/src/migrate.py" "${dest_dir}/tumcsbot.db" "${dest_dir}/migrations.sql"
}

mypy_func () {
    _enter_venv
    mypy --strict "${dest_dir}/src"
}

run_func () {
    _enter_venv
    upgrade_requirements_func
    # execute bot
    exec "${dest_dir}/src/main.py" "$@" "${dest_dir}/zuliprc" "${dest_dir}/tumcsbot.db"
}

static_analysis_func () {
    _enter_venv
    # Disable some checks.
    pylint --overgeneral-exceptions=BaseException \
        --min-similarity-lines=100 \
        --no-docstring-rgx='.*' \
        --good-names-rgxs='[a-z],[a-z][a-z]' \
        --disable=C0103,C0114,W0201,W0702 \
        --exit-zero \
        "${dest_dir}/src"
    mypy_func
}

test_func () {
    _enter_venv
    pytest
}

upgrade_requirements_func () {
    # upgrade all requirements
    pip3 install -U -r "${dest_dir}/requirements.txt"
}

usage () {
    echo -e "usage: manage.sh -m CMD DIR [ARGS]...\n\n\t-v\trun in virtualenv mode"
}


# whether the script runs in virtualenv mode or not
virtualenv=false

while getopts "v" opt; do
    case "$opt" in
        'v')
            virtualenv=true
            ;;
        *)
            usage
            exit 1
            ;;
    esac
done
shift $((OPTIND - 1))

cmd="$1"
# Always use absolute file names.
dest_dir=$(realpath "$2")
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
    'env')
        env_func "$@"
        ;;
    'init')
        init_func "$@"
        ;;
    'migrations')
        migrations_func "$@"
        ;;
    'mypy')
        mypy_func "$@"
        ;;
    'run')
        run_func "$@"
        ;;
    'static_analysis')
        static_analysis_func "$@"
        ;;
    'tests')
        test_func "$@"
        ;;
    'upgrade_requirements')
        upgrade_requirements_func "$@"
        ;;
    *)
        echo "command not found: $cmd"
        exit 1
        ;;
esac
