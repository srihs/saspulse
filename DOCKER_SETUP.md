# SasPulse Docker Setup Guide

## Prerequisites

- Docker Desktop installed (includes Docker Compose)
- Git
- 4GB+ RAM available for Docker
- Cin7 API credentials (optional for initial setup)

## Quick Start

### 1. Clone and Configure

```bash
# Clone repository
git clone https://github.com/srihs/saspulse.git
cd saspulse

# Copy environment file
cp .env.example .env

# Edit .env with your Cin7 credentials (optional initially)
nano .env
```

### 2. Build and Start

```bash
# Build Docker images
make build

# Start all services
make up

# Check if services are running
make ps
```

### 3. Access the Application

- **Backend API:** http://localhost:8000/api/v1/
- **Django Admin:** http://localhost:8000/admin
  - Username: `admin`
  - Password: `admin123` (auto-created)
- **PostgreSQL:** localhost:5432
- **Redis:** localhost:6379

## Available Services

The Docker setup includes:

1. **PostgreSQL Database** (port 5432)
   - Database: `saspulse`
   - User: `saspulse`
   - Password: Set in `.env` (default: `saspulse123`)

2. **Redis Cache** (port 6379)
   - Used for caching and Celery task queue

3. **Django Backend** (port 8000)
   - REST API
   - Admin interface

4. **Celery Worker**
   - Background task processing
   - Cin7 data synchronization

5. **Celery Beat**
   - Task scheduler
   - Periodic sync jobs

## Common Commands

### Service Management

```bash
# Start services
make up

# Stop services
make down

# Restart services
make restart

# View all logs
make logs

# View backend logs only
make logs-backend

# View service status
make ps
```

### Django Management

```bash
# Run database migrations
make migrate

# Create new migrations
make makemigrations

# Django shell
make shell

# Container bash shell
make bash

# Create superuser
make createsuperuser

# Collect static files
make collectstatic

# Run Django checks
make check
```

### Database Operations

```bash
# PostgreSQL shell
make dbshell

# Redis CLI
make redis-cli

# View database logs
make logs-db
```

### Testing

```bash
# Run tests
make test

# Run tests with coverage
make test-coverage
```

### Cleanup

```bash
# Stop and remove containers, networks
make down

# Stop and remove containers, networks, AND volumes (DESTRUCTIVE)
make clean
```

## Environment Variables

Edit `.env` file to configure:

### Required for Development
```bash
SECRET_KEY=your-secret-key
DEBUG=True
DB_PASSWORD=saspulse123
```

### Required for Cin7 Integration
```bash
CIN7_API_URL=https://api.cin7.com/api/v1
CIN7_USERNAME=your_cin7_username
CIN7_API_KEY=your_cin7_api_key
```

### Optional
```bash
# Email notifications
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-password

# Monitoring
SENTRY_DSN=your-sentry-dsn
```

## Manual Docker Commands

If you prefer not to use Make:

```bash
# Build
docker-compose build

# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f

# Execute command in backend
docker-compose exec backend python manage.py migrate

# Shell access
docker-compose exec backend bash
```

## Troubleshooting

### Services Won't Start

```bash
# Check if ports are already in use
lsof -i :8000  # Backend
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis

# View detailed logs
make logs

# Rebuild from scratch
make clean
make build
make up
```

### Database Connection Issues

```bash
# Check database health
docker-compose exec db pg_isready -U saspulse

# Check database logs
make logs-db

# Reset database (DESTRUCTIVE)
make clean
make up
```

### Permission Issues

```bash
# Fix permissions on Linux/macOS
sudo chown -R $USER:$USER .

# Make scripts executable
chmod +x docker-entrypoint.sh
```

### Migrations Not Running

```bash
# Manually run migrations
make migrate

# Check migration status
docker-compose exec backend python manage.py showmigrations

# Create missing migrations
make makemigrations
```

### Celery Not Working

```bash
# Check Celery worker logs
make logs-celery

# Check Redis connection
make redis-cli
> ping
PONG

# Restart Celery
docker-compose restart celery celery-beat
```

## Development Workflow

### Making Code Changes

1. Edit code in your local directory
2. Changes are automatically synced to container (volume mount)
3. Django auto-reloads on code changes
4. For model changes:
   ```bash
   make makemigrations
   make migrate
   ```

### Adding Python Dependencies

1. Edit `requirements.txt`
2. Rebuild backend:
   ```bash
   docker-compose build backend celery celery-beat
   docker-compose up -d
   ```

### Database Backups

```bash
# Create backup
docker-compose exec db pg_dump -U saspulse saspulse > backup.sql

# Restore backup
cat backup.sql | docker-compose exec -T db psql -U saspulse saspulse
```

## Production Considerations

For production deployment:

1. **Change secrets in `.env`**
2. **Set `DEBUG=False`**
3. **Configure proper `ALLOWED_HOSTS`**
4. **Use production-grade database**
5. **Set up SSL/TLS**
6. **Configure monitoring (Sentry)**
7. **Set up automated backups**
8. **Use production Dockerfile target**

```bash
# Build for production
docker-compose -f docker-compose.prod.yml build

# Start production services
docker-compose -f docker-compose.prod.yml up -d
```

## Health Checks

Services include health checks:

- **PostgreSQL:** `pg_isready`
- **Redis:** `redis-cli ping`
- Backend depends on healthy DB and Redis

Check health:
```bash
docker-compose ps
```

Healthy services show `(healthy)` status.

## Getting Help

- Check logs: `make logs`
- View specific service: `make logs-backend`
- Django errors: Check backend container logs
- Database issues: Check database connection settings
- Celery issues: Check Redis connection

## Next Steps

After Docker setup is working:

1. Configure Cin7 credentials in `.env`
2. Run initial data sync
3. Explore the admin interface
4. Start frontend development

---

**Need more help?** Check the main documentation or agent guides in `docs/agents/`
