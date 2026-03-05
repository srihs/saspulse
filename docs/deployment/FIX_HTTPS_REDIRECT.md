# Fix Browser Auto-Redirecting HTTP to HTTPS

Your browser is remembering a previous HTTPS redirect and automatically converting `http://localhost:8000` to `https://localhost:8000`. Here's how to fix it:

## Chrome / Edge / Brave

1. **Clear HSTS Settings:**
   - Visit: `chrome://net-internals/#hsts` (or `edge://net-internals/#hsts`)
   - Scroll down to "Delete domain security policies"
   - Enter: `localhost`
   - Click **Delete**
   - Also delete: `127.0.0.1`

2. **Clear Site Data:**
   - Visit: `chrome://settings/content/all`
   - Search for: `localhost`
   - Click the trash icon to remove all data

3. **Try again:**
   - Visit: `http://localhost:8000` (type it manually, don't click a bookmark)

## Firefox

1. **Clear Site Settings:**
   - Go to `about:preferences#privacy`
   - Scroll to "Cookies and Site Data"
   - Click "Manage Data..."
   - Search for `localhost`
   - Remove all localhost entries
   - Click "Save Changes"

2. **Clear History:**
   - Press `Cmd+Shift+Delete` (Mac) or `Ctrl+Shift+Delete` (Windows)
   - Select "Everything" for time range
   - Check "Browsing & Download History" and "Cookies"
   - Click "Clear Now"

3. **Try again:**
   - Visit: `http://localhost:8000`

## Safari

1. **Clear Website Data:**
   - Safari → Settings → Privacy
   - Click "Manage Website Data..."
   - Search for: `localhost`
   - Remove all entries
   - Click "Done"

2. **Clear History:**
   - Safari → Clear History...
   - Select "all history"
   - Click "Clear History"

3. **Try again:**
   - Visit: `http://localhost:8000`

## Alternative: Use a Different Port

If clearing doesn't work, just use a different port that doesn't have HSTS cached:

```bash
# Kill all servers
./stop_server.sh

# Start on port 8080 instead
python3 manage.py runserver 8080
```

Then visit: `http://localhost:8080`

## Alternative: Use Private/Incognito Mode

The quickest temporary fix:

1. Open a **Private/Incognito window** (Cmd+Shift+N in Chrome, Cmd+Shift+P in Firefox)
2. Visit: `http://localhost:8000`
3. Private mode ignores HSTS cache

## Alternative: Edit /etc/hosts

If you want to use a different hostname:

```bash
# Edit hosts file
sudo nano /etc/hosts

# Add this line:
127.0.0.1    saspulse.local

# Save and exit (Ctrl+X, Y, Enter)
```

Then visit: `http://saspulse.local:8000`

## Why This Happens

Django's development server sent an HSTS header that told your browser to ALWAYS use HTTPS for localhost. The browser cached this instruction and now automatically redirects all HTTP requests to HTTPS.

## Permanent Fix: Disable HSTS in Development

To prevent this from happening again, I can update your Django settings to disable HSTS in development mode.
