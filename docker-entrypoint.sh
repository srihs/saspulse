#!/bin/bash
# Docker entrypoint script for SasPulse backend

set -e

echo "Waiting for PostgreSQL..."
while ! pg_isready -h db -U saspulse > /dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL is ready!"

echo "Waiting for Redis..."
while ! redis-cli -h redis ping > /dev/null 2>&1; do
  sleep 1
done
echo "Redis is ready!"

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || echo "Static files collection skipped"

echo "Creating superuser if doesn't exist..."
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@saspulse.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
" || echo "Superuser creation skipped"

echo "Starting application..."
exec "$@"
