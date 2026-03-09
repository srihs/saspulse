# SasPulse Deployment Guide

## Quick Start

### 1. Prerequisites
- Docker
- Docker Compose

### 2. Setup Environment
Copy the example environment file and configure it:
```bash
cp .env.example .env
```

Edit `.env` and set:
- `SECRET_KEY` (generate a new one)
- `DB_PASSWORD` (secure password)
- `ALLOWED_HOSTS` (your domain)

### 3. Deploy with Docker Compose

**Development:**
```bash
docker-compose up -d
```

**Production (with Nginx):**
```bash
docker-compose --profile production up -d
```

### 4. Access the Application
- Application: http://localhost:8000
- With Nginx: http://localhost

### 5. Run Migrations
```bash
docker-compose exec web python manage.py migrate
```

### 6. Create Superuser
```bash
docker-compose exec web python manage.py createsuperuser
```

## Docker Commands

**Build:**
```bash
docker-compose build
```

**Start:**
```bash
docker-compose up -d
```

**Stop:**
```bash
docker-compose down
```

**View Logs:**
```bash
docker-compose logs -f web
```

**Database Backup:**
```bash
docker-compose exec db mysqldump -u root -p saspulse > backup.sql
```

## Troubleshooting

**Reset Database:**
```bash
docker-compose down -v
docker-compose up -d
```

**Check Container Status:**
```bash
docker-compose ps
```

**Exec into Container:**
```bash
docker-compose exec web bash
```
