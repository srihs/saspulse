.PHONY: help build up down restart logs shell migrate createsuperuser test clean

# Detect Docker Compose command (v1 vs v2)
DOCKER_COMPOSE := $(shell command -v docker-compose 2> /dev/null)
ifndef DOCKER_COMPOSE
	DOCKER_COMPOSE := docker compose
endif

help:
	@echo "SasPulse Docker Management"
	@echo "=========================="
	@echo "make build          - Build Docker images"
	@echo "make up             - Start all services"
	@echo "make down           - Stop all services"
	@echo "make restart        - Restart all services"
	@echo "make logs           - View logs (all services)"
	@echo "make logs-backend   - View backend logs"
	@echo "make logs-celery    - View celery logs"
	@echo "make shell          - Django shell"
	@echo "make bash           - Backend container bash"
	@echo "make migrate        - Run database migrations"
	@echo "make makemigrations - Create new migrations"
	@echo "make createsuperuser- Create Django superuser"
	@echo "make test           - Run tests"
	@echo "make clean          - Remove containers and volumes"
	@echo "make ps             - Show running containers"
	@echo ""
	@echo "Using: $(DOCKER_COMPOSE)"

build:
	$(DOCKER_COMPOSE) build

up:
	$(DOCKER_COMPOSE) up -d
	@echo "Services are starting..."
	@echo "Backend: http://localhost:8000"
	@echo "Admin: http://localhost:8000/admin"
	@echo "API: http://localhost:8000/api/v1/"

down:
	$(DOCKER_COMPOSE) down

restart:
	$(DOCKER_COMPOSE) restart

logs:
	$(DOCKER_COMPOSE) logs -f

logs-backend:
	$(DOCKER_COMPOSE) logs -f backend

logs-celery:
	$(DOCKER_COMPOSE) logs -f celery

logs-db:
	$(DOCKER_COMPOSE) logs -f db

shell:
	$(DOCKER_COMPOSE) exec backend python manage.py shell

bash:
	$(DOCKER_COMPOSE) exec backend bash

migrate:
	$(DOCKER_COMPOSE) exec backend python manage.py migrate

makemigrations:
	$(DOCKER_COMPOSE) exec backend python manage.py makemigrations

createsuperuser:
	$(DOCKER_COMPOSE) exec backend python manage.py createsuperuser

test:
	$(DOCKER_COMPOSE) exec backend pytest

test-coverage:
	$(DOCKER_COMPOSE) exec backend pytest --cov=apps --cov-report=html

clean:
	$(DOCKER_COMPOSE) down -v
	rm -rf static media

ps:
	$(DOCKER_COMPOSE) ps

dbshell:
	$(DOCKER_COMPOSE) exec db psql -U saspulse -d saspulse

redis-cli:
	$(DOCKER_COMPOSE) exec redis redis-cli

check:
	$(DOCKER_COMPOSE) exec backend python manage.py check

collectstatic:
	$(DOCKER_COMPOSE) exec backend python manage.py collectstatic --noinput
