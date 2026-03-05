# SASPulse Deployment Guide

## Production Server Setup

This guide explains how to run SASPulse with a production-ready server instead of Django's development server.

### Why Use Gunicorn?

The Django development server (`manage.py runserver`) is:
- **NOT suitable for production** - It's single-threaded and not optimized for performance
- **Vulnerable to security issues** - It doesn't handle HTTPS properly
- **Shows annoying errors** - HTTPS requests to HTTP-only dev server cause error spam

Gunicorn is a production WSGI server that:
- ✅ Handles multiple concurrent requests efficiently
- ✅ Works properly with both HTTP and HTTPS
- ✅ Is battle-tested and recommended by Django
- ✅ Filters out invalid requests (like HTTPS to HTTP) silently

### Quick Start

#### 1. Start the Production Server

```bash
./start_server.sh
```

This will:
- Stop any existing servers
- Collect static files
- Run database migrations
- Start Gunicorn with optimized settings

#### 2. Stop the Production Server

```bash
./stop_server.sh
```

This will kill all Django/Gunicorn processes cleanly.

### Manual Commands

If you prefer to run commands manually:

**Start Gunicorn:**
```bash
gunicorn saspulse.wsgi:application \
    --config gunicorn_config.py \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 300
```

**Run in background:**
```bash
nohup gunicorn saspulse.wsgi:application --config gunicorn_config.py > gunicorn.log 2>&1 &
```

**Stop all servers:**
```bash
pkill -f "gunicorn saspulse.wsgi"
lsof -ti:8000 | xargs kill -9
```

### Configuration Files

- **gunicorn_config.py** - Gunicorn server configuration
- **start_server.sh** - Production startup script
- **stop_server.sh** - Server shutdown script

### Gunicorn Settings

The server is configured with:
- **Workers:** Auto-calculated based on CPU cores (formula: `2 * cores + 1`)
- **Timeout:** 300 seconds for long-running requests
- **Binding:** 0.0.0.0:8000 (accessible from any IP)
- **Logging:** Outputs to console with INFO level

### HTTPS Support

To enable HTTPS with SSL certificates, edit `gunicorn_config.py`:

```python
# Uncomment and update these lines:
keyfile = "/path/to/your/keyfile.key"
certfile = "/path/to/your/certfile.crt"
```

Or use Nginx as a reverse proxy (recommended for production).

### Log Filtering

The application is configured to suppress:
- HTTPS error messages when clients attempt HTTPS on HTTP-only server
- "Bad request version" errors from malformed requests

These are filtered in `saspulse/settings.py` via the logging configuration.

### Development Mode

If you still want to use the development server for debugging:

```bash
python3 manage.py runserver
```

**Note:** This will show the HTTPS errors again. Use Gunicorn to avoid them.

### Troubleshooting

**Port 8000 already in use:**
```bash
./stop_server.sh
# or
lsof -ti:8000 | xargs kill -9
```

**Server not accessible:**
- Check firewall settings
- Verify ALLOWED_HOSTS in settings.py includes your domain/IP
- Ensure port 8000 is not blocked

**Static files not loading:**
```bash
python3 manage.py collectstatic --noinput
```

### Production Checklist

Before deploying to a real production environment:

- [ ] Set `DEBUG = False` in settings or environment
- [ ] Update `SECRET_KEY` to a secure random value
- [ ] Configure `ALLOWED_HOSTS` with your domain
- [ ] Set up SSL/TLS certificates
- [ ] Use a reverse proxy (Nginx) for serving static files
- [ ] Set up a process manager (systemd, supervisor) to auto-restart
- [ ] Configure database backups
- [ ] Set up monitoring and error tracking

### Environment Variables

Create a `.env` file in the project root:

```env
DEBUG=False
SECRET_KEY=your-super-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,localhost
DB_NAME=dataSync
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=3306
```

### Monitoring

View server logs in real-time:
```bash
tail -f gunicorn.log
```

Check running processes:
```bash
ps aux | grep gunicorn
```

### Performance Tuning

Edit `gunicorn_config.py` to adjust:
- Worker count (more workers = more concurrent requests)
- Timeout (increase for long-running operations)
- Worker class (try 'gevent' or 'eventlet' for async)

---

## Need Help?

For more information:
- Gunicorn docs: https://docs.gunicorn.org/
- Django deployment: https://docs.djangoproject.com/en/6.0/howto/deployment/
