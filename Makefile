export COMPOSE_DOCKER_CLI_BUILD=1
export DOCKER_BUILDKIT=1

test:
	protean test

build:
	docker-compose build

up:
	docker-compose up -d redis elasticsearch postgres

down:
	docker-compose down --remove-orphans

html:
	@cd docs; $(MAKE) html

test-full: up
	pytest --slow --sqlite --postgresql --elasticsearch --redis tests

cov: up
    pytest --slow --sqlite --postgresql --elasticsearch --redis --cov=protean --cov-config .coveragerc tests
