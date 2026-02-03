.PHONY: help build up down restart logs shell migrate createsuperuser test clean

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

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Services are starting..."
	@echo "Backend: http://localhost:8000"
	@echo "Admin: http://localhost:8000/admin"
	@echo "API: http://localhost:8000/api/v1/"

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-celery:
	docker-compose logs -f celery

logs-db:
	docker-compose logs -f db

shell:
	docker-compose exec backend python manage.py shell

bash:
	docker-compose exec backend bash

migrate:
	docker-compose exec backend python manage.py migrate

makemigrations:
	docker-compose exec backend python manage.py makemigrations

createsuperuser:
	docker-compose exec backend python manage.py createsuperuser

test:
	docker-compose exec backend pytest

test-coverage:
	docker-compose exec backend pytest --cov=apps --cov-report=html

clean:
	docker-compose down -v
	rm -rf static media

ps:
	docker-compose ps

dbshell:
	docker-compose exec db psql -U saspulse -d saspulse

redis-cli:
	docker-compose exec redis redis-cli

check:
	docker-compose exec backend python manage.py check

collectstatic:
	docker-compose exec backend python manage.py collectstatic --noinput
