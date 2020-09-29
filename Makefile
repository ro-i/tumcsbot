# See LICENSE file for copyright and license details.
# time-sheet - https://github.com/ro-i/time-sheet

# location to install the virtual environment
dest_dir = bin

args = 

# default target
.PHONY: install
install:
	@bash -- util.sh install '$(dest_dir)'

.PHONY: debug
debug: args = --debug
debug: run

.PHONY: run
run:
	@bash -- util.sh run '$(dest_dir)' $(args)

.PHONY: uninstall
uninstall:
	@bash -- util.sh uninstall '$(dest_dir)'

