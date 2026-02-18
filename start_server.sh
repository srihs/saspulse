#!/bin/bash

# SASPulse Production Server Startup Script

# Navigate to project directory
cd /Users/sas/Repos/saspulse

# Kill any existing servers
echo "Stopping any existing servers..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
ps aux | grep "manage.py runserver" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null

# Wait a moment
sleep 2

# Activate virtual environment if it exists
if [ -d "env" ]; then
    source env/bin/activate
fi

# Collect static files (production)
echo "Collecting static files..."
python3 manage.py collectstatic --noinput

# Run migrations
echo "Running database migrations..."
python3 manage.py migrate --noinput

# Start Gunicorn server
echo "Starting Gunicorn production server..."
gunicorn saspulse.wsgi:application \
    --config gunicorn_config.py \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    --enable-stdio-inheritance

# If you want to run in background, use:
# nohup gunicorn saspulse.wsgi:application --config gunicorn_config.py > gunicorn.log 2>&1 &
