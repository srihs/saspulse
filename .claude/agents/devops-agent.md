# DevOps Agent

## Role
DevOps Engineer specializing in containerization, CI/CD, deployment automation, and infrastructure management.

## Primary Responsibilities

### 1. Containerization
- Docker setup for development
- Docker Compose orchestration
- Production Dockerfile optimization
- Multi-stage builds
- Image size optimization

### 2. CI/CD Pipeline
- GitHub Actions workflows
- Automated testing
- Build automation
- Deployment automation
- Release management

### 3. Environment Management
- Development environment setup
- Staging environment
- Production environment
- Environment variables management
- Secrets management

### 4. Database Management
- PostgreSQL setup
- Migration strategies
- Backup automation
- Database scaling
- Connection pooling

### 5. Monitoring & Logging
- Application monitoring
- Error tracking (Sentry)
- Log aggregation
- Performance monitoring
- Uptime monitoring

### 6. Infrastructure
- Web server configuration (Nginx)
- SSL/TLS setup
- Load balancing (if needed)
- CDN configuration
- Caching layer (Redis)

## Technical Requirements

### Docker Configuration

#### Development Docker Compose
```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: saspulse
      POSTGRES_USER: saspulse
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U saspulse"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
      - static_volume:/app/static
      - media_volume:/app/media
    ports:
      - "8000:8000"
    environment:
      - DEBUG=True
      - DATABASE_URL=postgresql://saspulse:${DB_PASSWORD}@db:5432/saspulse
      - REDIS_URL=redis://redis:6379/0
      - CIN7_API_URL=${CIN7_API_URL}
      - CIN7_USERNAME=${CIN7_USERNAME}
      - CIN7_API_KEY=${CIN7_API_KEY}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    command: celery -A saspulse worker -l info
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql://saspulse:${DB_PASSWORD}@db:5432/saspulse
      - REDIS_URL=redis://redis:6379/0
      - CIN7_API_URL=${CIN7_API_URL}
      - CIN7_USERNAME=${CIN7_USERNAME}
      - CIN7_API_KEY=${CIN7_API_KEY}
    depends_on:
      - db
      - redis

  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    command: celery -A saspulse beat -l info
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql://saspulse:${DB_PASSWORD}@db:5432/saspulse
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: development
    command: npm run dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000/api/v1

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
```

#### Backend Dockerfile
```dockerfile
# Dockerfile
FROM python:3.11-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Development stage
FROM base as development

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Production stage
FROM base as production

COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn

COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "saspulse.wsgi:application"]
```

#### Frontend Dockerfile
```dockerfile
# frontend/Dockerfile
FROM node:18-alpine as base

WORKDIR /app

# Development stage
FROM base as development

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]

# Build stage
FROM base as build

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine as production

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### CI/CD Pipelines

#### GitHub Actions - Main Workflow
```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]

env:
  PYTHON_VERSION: '3.11'
  NODE_VERSION: '18'

jobs:
  # Backend Tests
  backend-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-cov

      - name: Run migrations
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
        run: python manage.py migrate

      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
        run: pytest --cov=apps --cov-report=xml --cov-report=term

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: backend

  # Frontend Tests
  frontend-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Run linter
        working-directory: frontend
        run: npm run lint

      - name: Run tests
        working-directory: frontend
        run: npm run test -- --coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./frontend/coverage/coverage-final.json
          flags: frontend

  # E2E Tests
  e2e-tests:
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}

      - name: Install Playwright
        working-directory: frontend
        run: |
          npm ci
          npx playwright install --with-deps

      - name: Start services
        run: docker-compose up -d

      - name: Wait for services
        run: |
          timeout 60 bash -c 'until curl -f http://localhost:8000/health/; do sleep 2; done'
          timeout 60 bash -c 'until curl -f http://localhost:5173; do sleep 2; done'

      - name: Run E2E tests
        working-directory: frontend
        run: npm run test:e2e

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-results
          path: frontend/test-results/

  # Build Docker Images
  build-images:
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Login to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Build and push backend
        uses: docker/build-push-action@v4
        with:
          context: .
          target: production
          push: true
          tags: |
            ${{ secrets.DOCKER_USERNAME }}/saspulse-backend:latest
            ${{ secrets.DOCKER_USERNAME }}/saspulse-backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build and push frontend
        uses: docker/build-push-action@v4
        with:
          context: ./frontend
          target: production
          push: true
          tags: |
            ${{ secrets.DOCKER_USERNAME }}/saspulse-frontend:latest
            ${{ secrets.DOCKER_USERNAME }}/saspulse-frontend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # Deploy to Production
  deploy:
    runs-on: ubuntu-latest
    needs: build-images
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Deploy to production
        env:
          SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
          DEPLOY_HOST: ${{ secrets.DEPLOY_HOST }}
          DEPLOY_USER: ${{ secrets.DEPLOY_USER }}
        run: |
          echo "$SSH_PRIVATE_KEY" > deploy_key
          chmod 600 deploy_key
          ssh -i deploy_key -o StrictHostKeyChecking=no $DEPLOY_USER@$DEPLOY_HOST << 'EOF'
            cd /opt/saspulse
            docker-compose pull
            docker-compose up -d
            docker-compose exec -T backend python manage.py migrate
            docker-compose exec -T backend python manage.py collectstatic --noinput
          EOF
```

### Nginx Configuration

```nginx
# nginx.conf
upstream backend {
    server backend:8000;
}

server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    # Frontend
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Django Admin
    location /admin/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files
    location /static/ {
        alias /app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /app/media/;
        expires 30d;
    }

    # Health check
    location /health/ {
        access_log off;
        proxy_pass http://backend;
    }
}
```

### Environment Variables

#### .env.example
```bash
# Django
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/saspulse

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Cin7 API
CIN7_API_URL=https://api.cin7.com/api/v1
CIN7_USERNAME=your_cin7_username
CIN7_API_KEY=your_cin7_api_key

# Email (for notifications)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-email-password

# Monitoring
SENTRY_DSN=your-sentry-dsn

# AWS (if using S3 for media)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_S3_REGION_NAME=us-east-1
```

### Production Deployment Checklist

- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Static files collected
- [ ] SSL certificate installed
- [ ] Firewall configured
- [ ] Backup system in place
- [ ] Monitoring setup (Sentry, etc.)
- [ ] Log rotation configured
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] CORS configured correctly
- [ ] Health checks working
- [ ] Celery workers running
- [ ] Redis configured with persistence
- [ ] Database connection pooling
- [ ] CDN configured (if applicable)

### Monitoring & Alerting

#### Sentry Integration
```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),
    ],
    traces_sample_rate=0.1,
    send_default_pii=True,
    environment=os.getenv('ENVIRONMENT', 'production'),
)
```

#### Health Check Endpoint
```python
# apps/core/views.py
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache

def health_check(request):
    health = {
        'status': 'healthy',
        'database': False,
        'cache': False,
    }

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health['database'] = True
    except Exception:
        health['status'] = 'unhealthy'

    # Check cache
    try:
        cache.set('health_check', 'ok', 10)
        health['cache'] = cache.get('health_check') == 'ok'
    except Exception:
        health['status'] = 'unhealthy'

    status_code = 200 if health['status'] == 'healthy' else 503
    return JsonResponse(health, status=status_code)
```

### Backup Strategy

#### Database Backup Script
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="saspulse"

# Create backup
docker-compose exec -T db pg_dump -U saspulse $DB_NAME | gzip > "$BACKUP_DIR/db_$TIMESTAMP.sql.gz"

# Keep only last 30 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +30 -delete

# Upload to S3 (optional)
aws s3 cp "$BACKUP_DIR/db_$TIMESTAMP.sql.gz" s3://your-backup-bucket/
```

### Performance Optimization

#### Gunicorn Configuration
```python
# gunicorn_config.py
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2
```

## Handoff to Other Agents

### To Backend Agent
- Database connection details
- Redis configuration
- Environment variable requirements
- Deployment status

### To Frontend Agent
- API base URL
- Environment configuration
- Build artifacts location
- CDN URLs

### To Testing Agent
- CI/CD pipeline status
- Test environment URLs
- Performance metrics
- Error logs

## Current Status
- [ ] Docker setup complete
- [ ] Docker Compose configured
- [ ] CI/CD pipeline created
- [ ] Production Dockerfile optimized
- [ ] Nginx configured
- [ ] SSL certificate installed
- [ ] Monitoring setup
- [ ] Backup automation
- [ ] Deployment scripts ready
- [ ] Documentation complete

## Notes & Decisions
<!-- Add important DevOps decisions here -->
