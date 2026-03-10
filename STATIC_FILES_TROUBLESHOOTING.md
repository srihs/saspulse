# Static Files Troubleshooting Guide

## Problem Overview

Your Django application deployed at `https://dev-saspulse.it.sas.co.nz` is returning **404 errors** and **incorrect MIME types** for static files (CSS, JavaScript, images). Users are seeing:

- 404 errors for files like `/static/js/config.js`, `/static/css/theme.min.css`, etc.
- MIME type errors where files return `text/html` instead of their proper content types
- Broken styling and non-functional JavaScript

## Root Cause Analysis

Based on your codebase analysis, here are the key issues:

### 1. DEBUG Mode is Hardcoded to True
**Location:** `/app/saspulse/settings.py:19`
```python
DEBUG = True  # Hardcoded for development
```

**Problem:** Django's `runserver` serves static files automatically when `DEBUG=True`, but production WSGI servers (Gunicorn) **never** serve static files, regardless of DEBUG setting. This creates a false sense of security during development.

### 2. Missing WhiteNoise Middleware
**Current State:** No static file serving middleware is configured in `MIDDLEWARE` settings.

**Impact:** When Gunicorn serves your application, it cannot serve static files. All static file requests fall through to Django's URL routing, which returns the 404 error page (HTML content), explaining the `text/html` MIME type errors.

### 3. Nginx Configuration is Missing
**Current State:** The `nginx/` directory exists but has no configuration files.

**Docker Setup:** Your `docker-compose.yml` references nginx configuration files that don't exist:
```yaml
volumes:
  - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
  - ./nginx/conf.d:/etc/nginx/conf.d:ro
```

### 4. Environment Variable Not Respected
**Issue:** Even though `docker-compose.yml` sets `DEBUG=${DEBUG:-False}`, the settings.py file overrides this with:
```python
DEBUG = True  # Hardcoded for development
```

## Why This Happens

**Django's Static File Philosophy:**
- **Development:** `runserver` includes a static file server (convenience)
- **Production:** WSGI servers (Gunicorn, uWSGI) do NOT serve static files (by design)
- **Reason:** Serving static files with Python is inefficient; dedicated web servers or CDNs should handle this

**The Workflow Gap:**
1. Developers test with `runserver` - static files work fine
2. Deploy with Gunicorn - static files break
3. Confusion ensues because "it worked locally"

## Solutions (Multiple Approaches)

### Solution 1: WhiteNoise Middleware (RECOMMENDED)

WhiteNoise allows Django to serve static files efficiently in production without requiring Nginx/Apache. This is the **simplest and most robust** solution for Django applications.

#### Step 1: Install WhiteNoise
```bash
# On your deployment server or in Docker container
docker-compose exec web pip install whitenoise
```

Or add to `requirements.txt`:
```txt
whitenoise==6.6.0
```

#### Step 2: Update Django Settings

**File:** `/app/saspulse/settings.py`

**Update MIDDLEWARE** (add WhiteNoise right after SecurityMiddleware):
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ADD THIS LINE
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... rest of middleware
]
```

**Update Static Files Configuration:**
```python
# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

# WhiteNoise Configuration
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

**Fix DEBUG Setting:**
```python
# Replace line 19 with:
DEBUG = os.getenv('DEBUG', 'False') == 'True'
```

#### Step 3: Rebuild and Collect Static Files
```bash
# Rebuild Docker image
docker-compose build web

# Restart containers
docker-compose down
docker-compose up -d

# Verify collectstatic ran (it's in your docker-compose.yml command)
docker-compose logs web | grep collectstatic
```

#### Step 4: Verify
```bash
# Check static files were collected
docker-compose exec web ls -la /app/staticfiles/

# Test a static file URL
curl -I https://dev-saspulse.it.sas.co.nz/static/css/theme.min.css
```

**Expected:** You should see `HTTP/1.1 200 OK` with correct `Content-Type` header.

---

### Solution 2: Nginx Reverse Proxy (Production-Grade)

This approach uses Nginx to serve static files directly, which is more efficient for high-traffic sites.

#### Step 1: Create Nginx Configuration

**File:** `/app/nginx/nginx.conf`
```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 20M;

    gzip on;
    gzip_disable "msie6";
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml+rss
               application/rss+xml font/truetype font/opentype
               application/vnd.ms-fontobject image/svg+xml;

    include /etc/nginx/conf.d/*.conf;
}
```

**File:** `/app/nginx/conf.d/saspulse.conf`
```nginx
upstream django {
    server web:8000;
}

server {
    listen 80;
    server_name dev-saspulse.it.sas.co.nz;
    charset utf-8;

    # Max upload size
    client_max_body_size 20M;

    # Static files - served directly by Nginx
    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;

        # Ensure correct MIME types
        types {
            text/css css;
            text/javascript js;
            application/javascript js;
            image/png png;
            image/jpeg jpg jpeg;
            image/gif gif;
            image/svg+xml svg;
            font/woff woff;
            font/woff2 woff2;
        }
    }

    # Media files - served directly by Nginx
    location /media/ {
        alias /app/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # All other requests proxy to Django
    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint
    location /health/ {
        access_log off;
        proxy_pass http://django;
    }
}
```

#### Step 2: Update docker-compose.yml

Ensure nginx service is configured (it already is in your file):
```yaml
nginx:
  image: nginx:alpine
  container_name: saspulse_nginx
  restart: unless-stopped
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - ./nginx/conf.d:/etc/nginx/conf.d:ro
    - static_volume:/app/staticfiles:ro
    - media_volume:/app/media:ro
  depends_on:
    - web
  networks:
    - saspulse_network
  profiles:
    - production
```

#### Step 3: Deploy with Nginx
```bash
# Build and start with production profile
docker-compose --profile production down
docker-compose --profile production build
docker-compose --profile production up -d

# Verify nginx is running
docker-compose ps

# Check nginx configuration is valid
docker-compose exec nginx nginx -t

# View nginx logs
docker-compose logs nginx
```

#### Step 4: Update DNS/Reverse Proxy

If you're using an external reverse proxy (like Traefik, Caddy, or cloud load balancer) that points to your server:

**Option A:** Point it to Nginx on port 80
**Option B:** Keep pointing to port 8000 but use Solution 1 (WhiteNoise)

---

### Solution 3: Quick Fix for Testing (NOT FOR PRODUCTION)

If you need to quickly verify the application works while implementing a proper solution:

#### Temporary: Enable Django Static File Serving

**File:** `/app/saspulse/urls.py`

Add at the bottom:
```python
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ... your existing patterns
]

# TEMPORARY: Only for testing - REMOVE IN PRODUCTION
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

**Set DEBUG=True in .env:**
```bash
DEBUG=True
```

**Restart:**
```bash
docker-compose restart web
```

**WARNING:** This is inefficient and insecure for production. Use only for testing!

---

## Verification Checklist

After implementing any solution, verify with these checks:

### 1. Check Static Files are Collected
```bash
docker-compose exec web ls -la /app/staticfiles/
docker-compose exec web ls -la /app/staticfiles/css/
docker-compose exec web ls -la /app/staticfiles/js/
docker-compose exec web ls -la /app/staticfiles/img/
```

**Expected:** You should see all your static files copied here.

### 2. Test Static File URLs
```bash
# Test CSS file
curl -I https://dev-saspulse.it.sas.co.nz/static/css/theme.min.css

# Test JavaScript file
curl -I https://dev-saspulse.it.sas.co.nz/static/js/phoenix.js

# Test image file
curl -I https://dev-saspulse.it.sas.co.nz/static/img/icons/logo.png
```

**Expected Output:**
```
HTTP/1.1 200 OK
Content-Type: text/css    # or application/javascript or image/png
Content-Length: [size]
```

**BAD Output (current state):**
```
HTTP/1.1 404 Not Found
Content-Type: text/html   # This means it's serving Django's 404 page
```

### 3. Check Browser Developer Tools

Open https://dev-saspulse.it.sas.co.nz in browser:

1. Open Developer Tools (F12)
2. Go to Network tab
3. Refresh page
4. Look for static files (filter by CSS, JS, Img)
5. Verify Status: 200 (not 404)
6. Verify Type: correct MIME types
7. Check Console for errors

### 4. Verify Application Works

- Login page displays correctly with styling
- JavaScript functionality works
- Images load properly
- No console errors related to static files

---

## Common Pitfalls to Avoid

### 1. Not Running collectstatic
**Symptom:** 404 errors even with WhiteNoise/Nginx configured

**Fix:**
```bash
docker-compose exec web python manage.py collectstatic --noinput
docker-compose restart web
```

Your docker-compose.yml already runs this on startup, but verify it succeeds:
```bash
docker-compose logs web | grep collectstatic
```

### 2. Wrong STATIC_ROOT Path
**Symptom:** Files collected but not served

**Check:** Ensure paths match between Django settings and nginx/docker volumes:
- Django `STATIC_ROOT = /app/staticfiles` (in container)
- Nginx volume: `static_volume:/app/staticfiles:ro`
- Docker-compose web volume: `static_volume:/app/staticfiles`

### 3. File Permissions Issues
**Symptom:** 403 Forbidden errors

**Fix:**
```bash
# Set correct permissions
docker-compose exec web chmod -R 755 /app/staticfiles/
docker-compose exec web chown -R www-data:www-data /app/staticfiles/
```

### 4. Nginx Not Using Volume
**Symptom:** Nginx returns 404 even though files exist in web container

**Check:**
```bash
# Check from nginx container
docker-compose exec nginx ls -la /app/staticfiles/

# Check volume is mounted
docker-compose exec nginx mount | grep staticfiles
```

**Fix:** Ensure both services use the same volume in docker-compose.yml (they already do in your config).

### 5. Cache Issues
**Symptom:** Old/missing files after updates

**Fix:**
```bash
# Clear browser cache or use hard refresh (Ctrl+Shift+R)
# Clear Django cache
docker-compose exec web python manage.py clear_cache  # if you have this command
# Restart nginx
docker-compose restart nginx
```

### 6. ALLOWED_HOSTS Not Set
**Symptom:** 400 Bad Request errors

**Fix:** Ensure `.env` file has:
```
ALLOWED_HOSTS=dev-saspulse.it.sas.co.nz,localhost,127.0.0.1
```

### 7. SSL/HTTPS Issues
**Symptom:** Mixed content warnings (HTTPS page loading HTTP static files)

**Fix:** Ensure STATIC_URL uses relative paths (it already does: `/static/`), or configure X-Forwarded-Proto headers properly.

---

## Recommended Implementation Order

Based on your current setup, here's the recommended approach:

### Immediate Fix (30 minutes):
1. **Use WhiteNoise** (Solution 1)
   - Add to requirements.txt
   - Update settings.py (middleware + STORAGES)
   - Fix DEBUG setting to read from environment
   - Rebuild and redeploy

### Medium Term (2 hours):
2. **Add Nginx** (Solution 2)
   - Create nginx configuration files
   - Deploy with `--profile production`
   - Update external reverse proxy to point to nginx

### Long Term:
3. **Consider CDN** for truly static assets (uploaded images, etc.)
4. **Add SSL/TLS** certificates to nginx
5. **Implement asset versioning** for cache busting

---

## Current Configuration Summary

**Your Current Setup:**
- **Django:** 6.0.1
- **WSGI Server:** Gunicorn (4 workers)
- **Static URL:** `/static/`
- **Static Root:** `/app/staticfiles`
- **Static Dirs:** `/app/static`
- **DEBUG:** Hardcoded to `True` (line 19 of settings.py)
- **Middleware:** No static file serving middleware
- **Nginx:** Referenced but not configured

**What Needs to Change:**
- Add WhiteNoise middleware OR configure Nginx
- Fix DEBUG to read from environment variable
- Ensure collectstatic runs successfully
- Verify static files are in correct location

---

## Testing Your Fix

After implementing your chosen solution:

```bash
# 1. Check container logs
docker-compose logs web --tail=100

# 2. Verify static files exist
docker-compose exec web find /app/staticfiles -name "theme.min.css"

# 3. Test from inside container
docker-compose exec web curl -I http://localhost:8000/static/css/theme.min.css

# 4. Test from outside
curl -I https://dev-saspulse.it.sas.co.nz/static/css/theme.min.css

# 5. Check nginx (if using)
docker-compose exec nginx curl -I http://localhost/static/css/theme.min.css
```

---

## Additional Resources

- **Django Static Files Docs:** https://docs.djangoproject.com/en/6.0/howto/static-files/deployment/
- **WhiteNoise Docs:** http://whitenoise.evans.io/
- **Nginx Django Guide:** https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/nginx/
- **Gunicorn Config:** https://docs.gunicorn.org/en/stable/configure.html

---

## Quick Reference Commands

```bash
# Collect static files manually
docker-compose exec web python manage.py collectstatic --noinput

# List static files
docker-compose exec web ls -R /app/staticfiles/

# Check Django settings
docker-compose exec web python manage.py diffsettings | grep STATIC

# Test from container
docker-compose exec web python manage.py shell
>>> from django.conf import settings
>>> print(settings.STATIC_ROOT)
>>> print(settings.STATIC_URL)
>>> print(settings.DEBUG)

# Rebuild everything
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d

# View all logs
docker-compose logs -f
```

---

## Need Help?

If you're still experiencing issues after trying these solutions:

1. Check container logs: `docker-compose logs web`
2. Verify environment variables: `docker-compose exec web env | grep DEBUG`
3. Test static file access from inside container
4. Check nginx error logs: `docker-compose logs nginx`
5. Verify DNS/reverse proxy configuration points to correct port

**Most likely solution for your case:** Implement WhiteNoise (Solution 1) - it's the quickest, requires no infrastructure changes, and is the Django-recommended approach for containerized deployments.
