# See LICENSE file for copyright and license details.
# tumcsbot - https://github.com/ro-i/tumcsbot

# location to install the virtual environment
dest_dir = .

# bot parameters
args = 

# run bot; default target
.PHONY: run
run:
	@bash -- manage.sh -v run '$(dest_dir)' $(args)

.PHONY: class_diagram
class_diagram:
	pyreverse --colorized -f ALL -S -my --ignore plugins src/tumcsbot -o svg

# run bot in debug mode
.PHONY: debug
debug: args = --debug
debug: run

# run in docker
.PHONY: docker-run
docker-run:
	docker compose up

# run in docker in debug mode
.PHONY: docker-debug
docker-debug:
	docker compose -f docker-compose.debug.yml up

# remove virtual environment
.PHONY: clean
clean:
	@bash -- manage.sh -v clean '$(dest_dir)'

# install requirements (in virtualenv)
.PHONY: env
env:
	@bash -- manage.sh -v env '$(dest_dir)'

.PHONY: init
init: database env

# prepare database
.PHONY: database
database:
	@bash -- manage.sh -v database '$(dest_dir)'

# apply database migrations
migrations:
	@bash -- manage.sh -v migrations '$(dest_dir)'

# run only mypy, not all static_analysis
.PHONY: mypy
mypy:
	@bash -- manage.sh -v mypy '$(dest_dir)'

# run static analysis checker
.PHONY: static_analysis
static_analysis:
	@bash -- manage.sh -v static_analysis '$(dest_dir)'

# run tests
.PHONY: tests
tests:
	@bash -- manage.sh -v tests '$(dest_dir)'

.PHONY: upgrade_requirements
upgrade_requirements:
	@bash -- manage.sh -v upgrade_requirements '$(dest_dir)'

