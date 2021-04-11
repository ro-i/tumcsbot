# See LICENSE file for copyright and license details.
# time-sheet - https://github.com/ro-i/time-sheet

# location to install the virtual environment
dest_dir = .

# bot parameters
args = 

# run bot; default target
.PHONY: run
run:
	@bash -- manage.sh run '$(dest_dir)' $(args)

.PHONY: debug
debug: args = --debug
debug: run

# remove virtual environment
.PHONY: clean
clean:
	@bash -- manage.sh clean '$(dest_dir)'

.PHONY: init
init: database virtualenv

# prepare database
.PHONY: database
database:
	@bash -- manage.sh database '$(dest_dir)'

# apply database migrations
migrations:
	@bash -- manage.sh migrations '$(dest_dir)'

# run only mypy, not all static_analysis
.PHONY: mypy
mypy:
	@bash -- manage.sh mypy '$(dest_dir)'

# run static analysis checker
.PHONY: static_analysis
static_analysis:
	@bash -- manage.sh static_analysis '$(dest_dir)'

# run tests
.PHONY: tests
tests:
	@bash -- manage.sh tests '$(dest_dir)'

.PHONY: upgrade_requirements
upgrade_requirements:
	@bash -- manage.sh upgrade_requirements '$(dest_dir)'

# install virtual environment
.PHONY: virtualenv
virtualenv:
	@bash -- manage.sh virtualenv '$(dest_dir)'

