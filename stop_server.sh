#!/bin/bash

# SASPulse Server Stop Script

echo "Stopping SASPulse servers..."

# Kill Gunicorn processes
pkill -f "gunicorn saspulse.wsgi" 2>/dev/null

# Kill Django development servers
ps aux | grep "manage.py runserver" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null

# Kill anything on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null

echo "All servers stopped."
