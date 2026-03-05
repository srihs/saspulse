# SASPulse Quick Start Guide

## Development Environment Access

### ✅ Correct URLs

Access the application using **HTTP** (not HTTPS):

```
http://localhost:8000
http://127.0.0.1:8000
```

### ❌ Common Errors

**ERR_SSL_PROTOCOL_ERROR** - You're using HTTPS when the server only supports HTTP:

```
https://localhost:8000      ❌ WRONG - Will cause SSL error
https://127.0.0.1:8000      ❌ WRONG - Will cause SSL error
```

**Solution:** Remove the `s` from `https` and use `http` instead.

## Starting the Server

### Option 1: Production Server (Recommended)

```bash
./start_server.sh
```

Then visit: **http://localhost:8000**

### Option 2: Development Server

```bash
python3 manage.py runserver
```

Then visit: **http://localhost:8000**

## Stopping the Server

```bash
./stop_server.sh
```

## Why No HTTPS in Development?

- HTTPS requires SSL certificates
- Development servers don't need encryption on localhost
- Browser will show errors when trying HTTPS on HTTP-only servers
- For production with HTTPS, see [DEPLOYMENT.md](DEPLOYMENT.md)

## Browser Auto-Redirecting to HTTPS?

Some browsers remember HTTPS redirects. To fix:

### Chrome:
1. Visit: `chrome://net-internals/#hsts`
2. Scroll to "Delete domain security policies"
3. Enter: `localhost` and click Delete
4. Try `http://localhost:8000` again

### Firefox:
1. Clear browsing history
2. Or use private/incognito window
3. Make sure to type `http://` explicitly

### Safari:
1. Clear website data for localhost
2. Or use private browsing window

## Quick Checklist

- [ ] Server is running (use `./start_server.sh` or `python3 manage.py runserver`)
- [ ] Using HTTP not HTTPS in browser
- [ ] URL is `http://localhost:8000` or `http://127.0.0.1:8000`
- [ ] No other process is using port 8000

## Still Having Issues?

Check if server is running:
```bash
lsof -i:8000
```

Check server logs for errors:
```bash
tail -f gunicorn.log  # if using production server
# or watch terminal output if using development server
```

View recent errors:
```bash
python3 manage.py check
```

---

**Remember:** Use **http://** not **https://** for local development!
