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

# prepare database
.PHONY: database
database:
	@bash -- manage.sh database '$(dest_dir)'

# install virtual environment
.PHONY: virtualenv
virtualenv:
	@bash -- manage.sh virtualenv '$(dest_dir)'

