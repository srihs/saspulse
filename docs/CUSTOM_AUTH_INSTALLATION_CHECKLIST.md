# Custom Authentication - Installation Checklist

## Pre-Installation Verification

- [x] Custom models created in `users/models.py`
- [x] Authentication backend created in `users/auth_backend.py`
- [x] Middleware created in `users/middleware.py`
- [x] Decorators created in `users/decorators.py`
- [x] Utilities created in `users/utils.py`
- [x] Validators created in `users/validators.py`

---

## Phase 1: Install Dependencies

### Required Package

```bash
cd /Users/sas/Repos/saspulse

# Install Argon2 for password hashing
pip install django[argon2]

# OR
pip install argon2-cffi
```

**Verify Installation:**
```bash
python -c "import argon2; print('Argon2 installed successfully')"
```

- [ ] Argon2 installed and verified

---

## Phase 2: Update Settings

### File: `/Users/sas/Repos/saspulse/saspulse/settings.py`

### 1. Add Password Hashers (Add at end of file)

```python
# ============================================================================
# CUSTOM AUTHENTICATION SETTINGS
# ============================================================================

# Password Hashing - Use Argon2 (most secure)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# Custom Authentication Settings
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION = 30  # minutes
ACTIVATION_TOKEN_EXPIRY = 24  # hours
RESET_TOKEN_EXPIRY = 1  # hour

# Session Settings
SESSION_COOKIE_AGE = 7200  # 2 hours in seconds
SESSION_COOKIE_SECURE = not DEBUG  # HTTPS only in production
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = False  # Save only on modification

# Login/Logout URLs
LOGIN_URL = '/auth/login/'
LOGOUT_REDIRECT_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
```

- [ ] Password hashers configured
- [ ] Authentication settings added
- [ ] Session settings configured
- [ ] URL settings defined

### 2. Update Middleware (Find existing MIDDLEWARE list)

**IMPORTANT:** Keep Django's AuthenticationMiddleware for now. Add custom middleware AFTER it.

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # KEEP existing
    'users.middleware.AuthenticationMiddleware',  # ADD custom
    'users.middleware.SessionSecurityMiddleware',  # ADD custom
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

- [ ] Custom middleware added to settings
- [ ] Middleware order verified (custom AFTER Django auth)

---

## Phase 3: Create Migrations

```bash
cd /Users/sas/Repos/saspulse

# Create migration files
python manage.py makemigrations users

# Expected output:
# Migrations for 'users':
#   users/migrations/000X_custom_auth.py
#     - Create model CustomUser
#     - Create model UserSession
#     - Add field roles to customuser
```

**Check Migration File:**
```bash
ls -la users/migrations/
```

- [ ] Migration files created successfully
- [ ] Migration file reviewed

---

## Phase 4: Run Migrations

```bash
# Backup database first (if production)
cp db.sqlite3 db.sqlite3.backup

# Run migrations
python manage.py migrate users

# Expected output:
# Running migrations:
#   Applying users.000X_custom_auth... OK
```

**Verify Tables Created:**
```bash
python manage.py dbshell
# SQLite commands:
.tables
# Should see: custom_users, user_sessions, custom_users_roles
.schema custom_users
.exit
```

- [ ] Database backed up
- [ ] Migrations run successfully
- [ ] Tables created and verified

---

## Phase 5: Create Superuser

### Option A: Django Shell

```bash
python manage.py shell
```

```python
from users.models import CustomUser
from django.utils import timezone

# Create superuser
admin = CustomUser.objects.create(
    username='admin',
    email='admin@saspulse.com',
    first_name='Admin',
    last_name='User',
    is_active=True,
    is_staff=True,
    is_superuser=True,
    email_verified=True,
    last_password_change=timezone.now()
)

# Set password (will be hashed with Argon2)
admin.set_password('Admin@SasPulse2024!')

print(f"Superuser created: {admin.username}")
print(f"Password hash: {admin.password_hash[:50]}...")
exit()
```

### Option B: Create Management Command (Better for future)

Create file: `users/management/commands/create_superuser.py`

```python
from django.core.management.base import BaseCommand
from django.utils import timezone
from users.models import CustomUser

class Command(BaseCommand):
    help = 'Create a superuser for custom auth system'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin')
        parser.add_argument('--email', type=str, default='admin@saspulse.com')
        parser.add_argument('--password', type=str, required=True)

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        if CustomUser.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'User {username} already exists'))
            return

        admin = CustomUser.objects.create(
            username=username,
            email=email,
            is_active=True,
            is_staff=True,
            is_superuser=True,
            email_verified=True,
            last_password_change=timezone.now()
        )
        admin.set_password(password)

        self.stdout.write(self.style.SUCCESS(f'Superuser {username} created successfully'))
```

Then run:
```bash
python manage.py create_superuser --password 'Admin@SasPulse2024!'
```

- [ ] Superuser created successfully
- [ ] Password verified (can login later)
- [ ] Credentials documented securely

---

## Phase 6: Create Test User (Optional)

```bash
python manage.py shell
```

```python
from users.models import CustomUser, Role

# Create test user
user = CustomUser.objects.create(
    username='testuser',
    email='test@saspulse.com',
    first_name='Test',
    last_name='User',
    is_active=True,
    email_verified=True
)
user.set_password('Test@Pass123!')

# Create a test role
role = Role.objects.create(
    name='Viewer',
    description='Read-only access',
    permissions={'users': {'view': True}}
)

# Assign role
user.roles.add(role)

print(f"Test user created: {user.username}")
print(f"Roles: {list(user.roles.values_list('name', flat=True))}")
exit()
```

- [ ] Test user created
- [ ] Test role created and assigned

---

## Phase 7: Testing

### Test Authentication Backend

Create file: `test_auth.py` in project root

```python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saspulse.settings')
django.setup()

from django.test import RequestFactory
from users.auth_backend import auth_backend
from users.models import CustomUser

# Create mock request
factory = RequestFactory()
request = factory.post('/auth/login/')
request.session = {}

print("Testing authentication backend...")

# Test 1: Authenticate with correct credentials
print("\n1. Testing authentication with correct credentials...")
user = auth_backend.authenticate(request, username='admin', password='Admin@SasPulse2024!')
if user:
    print(f"✓ Authentication successful: {user.username}")
else:
    print("✗ Authentication failed")

# Test 2: Authenticate with wrong password
print("\n2. Testing authentication with wrong password...")
user = auth_backend.authenticate(request, username='admin', password='wrongpassword')
if user is None:
    print("✓ Correctly rejected wrong password")
else:
    print("✗ Should have rejected wrong password")

# Test 3: Check user methods
print("\n3. Testing user methods...")
admin = CustomUser.objects.get(username='admin')
print(f"   Full name: {admin.get_full_name()}")
print(f"   Is superuser: {admin.is_superuser}")
print(f"   Has permission 'any': {admin.has_permission('any')}")
print(f"   All permissions: {admin.get_all_permissions()}")

# Test 4: Password verification
print("\n4. Testing password verification...")
if admin.check_password('Admin@SasPulse2024!'):
    print("✓ Password verification works")
else:
    print("✗ Password verification failed")

print("\n✓ All tests completed!")
```

Run:
```bash
python test_auth.py
```

- [ ] Authentication backend tested
- [ ] User methods work correctly
- [ ] Password hashing/verification works

### Test Utilities

```bash
python manage.py shell
```

```python
from users.utils import (
    validate_password_strength,
    validate_username,
    validate_email,
    generate_password,
    hash_password,
    check_password
)

# Test password validation
print("1. Testing password validation...")
is_valid, errors = validate_password_strength('weakpass')
print(f"   Weak password valid: {is_valid}")
print(f"   Errors: {errors}")

is_valid, errors = validate_password_strength('StrongPass123!')
print(f"   Strong password valid: {is_valid}")

# Test username validation
print("\n2. Testing username validation...")
valid, error = validate_username('john_doe')
print(f"   Valid username: {valid}")

valid, error = validate_username('ab')  # Too short
print(f"   Short username valid: {valid} - {error}")

# Test email validation
print("\n3. Testing email validation...")
valid, error = validate_email('user@example.com')
print(f"   Valid email: {valid}")

# Test password generation
print("\n4. Testing password generation...")
password = generate_password(12)
print(f"   Generated password: {password}")
is_valid, errors = validate_password_strength(password)
print(f"   Generated password valid: {is_valid}")

# Test hashing
print("\n5. Testing password hashing...")
hashed = hash_password('TestPassword123!')
print(f"   Hash starts with: {hashed[:30]}...")
print(f"   Is Argon2: {hashed.startswith('argon2')}")
print(f"   Verification: {check_password('TestPassword123!', hashed)}")

exit()
```

- [ ] Password validation tested
- [ ] Username validation tested
- [ ] Email validation tested
- [ ] Password generation tested
- [ ] Hashing/verification tested

---

## Phase 8: Integration Testing

### Create Simple Test View

Create file: `users/test_views.py`

```python
from django.http import HttpResponse
from users.decorators import login_required, permission_required

@login_required()
def test_protected_view(request):
    return HttpResponse(f"Hello, {request.user.username}!")

@login_required()
@permission_required('users.create')
def test_permission_view(request):
    return HttpResponse("You have permission!")
```

Add to `saspulse/urls.py`:

```python
from users.test_views import test_protected_view, test_permission_view

urlpatterns = [
    # ... existing patterns
    path('test/protected/', test_protected_view, name='test_protected'),
    path('test/permission/', test_permission_view, name='test_permission'),
]
```

### Manual Browser Test

```bash
# Start development server
python manage.py runserver
```

1. Visit: http://127.0.0.1:8000/test/protected/
   - Should redirect to `/auth/login/?next=/test/protected/`
   - [ ] Redirects correctly

2. Visit: http://127.0.0.1:8000/test/permission/
   - Should redirect to login
   - [ ] Redirects correctly

(Note: You'll need to create login views for full testing)

---

## Phase 9: Performance Check

### Test Session Cleanup

```bash
python manage.py shell
```

```python
from users.models import UserSession
from django.utils import timezone
from datetime import timedelta

# Create test expired session
from users.models import CustomUser
admin = CustomUser.objects.get(username='admin')

expired_session = UserSession.objects.create(
    session_key='test_expired_session',
    user=admin,
    expires_at=timezone.now() - timedelta(hours=1),
    is_active=True
)

print(f"Expired session created: {expired_session.session_key}")
print(f"Is expired: {expired_session.is_expired()}")

# Test cleanup query
expired_count = UserSession.objects.filter(
    expires_at__lt=timezone.now()
).count()
print(f"Total expired sessions: {expired_count}")

# Cleanup
UserSession.objects.filter(
    expires_at__lt=timezone.now()
).delete()

print("Expired sessions deleted")
exit()
```

- [ ] Session expiration works
- [ ] Cleanup query efficient

### Check Database Indexes

```bash
python manage.py dbshell
```

```sql
-- SQLite: Check indexes
.indexes custom_users
.indexes user_sessions

-- Should see indexes on:
-- custom_users: username, email, is_active, email_verified
-- user_sessions: (user_id, is_active), expires_at, last_activity
```

- [ ] All indexes created correctly

---

## Phase 10: Security Verification

### Check Password Hashing

```bash
python manage.py shell
```

```python
from users.models import CustomUser

admin = CustomUser.objects.get(username='admin')
print(f"Password hash: {admin.password_hash}")

# Should start with 'argon2$argon2id$'
assert admin.password_hash.startswith('argon2'), "Password should use Argon2!"
print("✓ Using Argon2 hashing")

# Check hash length
assert len(admin.password_hash) > 100, "Hash too short"
print(f"✓ Hash length: {len(admin.password_hash)} characters")

exit()
```

- [ ] Passwords hashed with Argon2
- [ ] Hash format correct

### Test Brute Force Protection

```bash
python manage.py shell
```

```python
from django.test import RequestFactory
from users.auth_backend import auth_backend
from users.models import CustomUser

factory = RequestFactory()
request = factory.post('/auth/login/')
request.session = {}

# Get test user
user = CustomUser.objects.get(username='testuser')
user.unlock_account()  # Reset if locked

print(f"Initial failed attempts: {user.failed_login_attempts}")

# Attempt 5 failed logins
for i in range(5):
    result = auth_backend.authenticate(
        request,
        username='testuser',
        password='wrongpassword'
    )
    user.refresh_from_db()
    print(f"Attempt {i+1}: Failed attempts = {user.failed_login_attempts}")

# Check if locked
user.refresh_from_db()
print(f"\nAccount locked: {user.is_locked()}")
print(f"Locked until: {user.locked_until}")

# Should be locked now
assert user.is_locked(), "Account should be locked after 5 failed attempts!"
print("✓ Brute force protection working")

# Cleanup
user.unlock_account()
exit()
```

- [ ] Failed attempts tracked
- [ ] Account locks after 5 attempts
- [ ] Unlock works correctly

---

## Phase 11: Documentation Check

Verify all documentation files exist:

```bash
ls -lh /Users/sas/Repos/saspulse/docs/CUSTOM_AUTH*.md
```

Should see:
- `CUSTOM_AUTH_PLAN.md` - Original plan
- `CUSTOM_AUTH_IMPLEMENTATION_SUMMARY.md` - Detailed implementation
- `CUSTOM_AUTH_QUICK_REFERENCE.md` - Developer quick reference
- `CUSTOM_AUTH_INSTALLATION_CHECKLIST.md` - This file

- [ ] All documentation files present
- [ ] Documentation reviewed

---

## Phase 12: Final Verification

### Checklist Summary

- [ ] Argon2 installed
- [ ] Settings configured
- [ ] Middleware added
- [ ] Migrations created and run
- [ ] Superuser created
- [ ] Authentication backend tested
- [ ] Utilities tested
- [ ] Security features verified
- [ ] Documentation complete

### System Status Check

```bash
python manage.py shell
```

```python
# Quick system check
from users.models import CustomUser, UserSession, Role

print("=== Custom Auth System Status ===\n")

print(f"Total users: {CustomUser.objects.count()}")
print(f"Active users: {CustomUser.objects.filter(is_active=True).count()}")
print(f"Superusers: {CustomUser.objects.filter(is_superuser=True).count()}")
print(f"Total roles: {Role.objects.count()}")
print(f"Active sessions: {UserSession.objects.filter(is_active=True).count()}")

print("\n✓ Custom auth system operational!")
exit()
```

---

## Next Steps

1. **Create Authentication Views** - Login, logout, register, password reset
2. **Create Templates** - HTML forms for authentication
3. **Add URL Routing** - Wire up authentication endpoints
4. **Email Integration** - Setup email for activation/reset
5. **Data Migration** - Migrate existing Django users (if any)
6. **Remove Django Auth** - Final step after full migration

---

## Rollback Plan (If Needed)

If something goes wrong:

```bash
# Restore database backup
cp db.sqlite3.backup db.sqlite3

# Remove custom middleware from settings.py
# Comment out these lines:
# 'users.middleware.AuthenticationMiddleware',
# 'users.middleware.SessionSecurityMiddleware',

# Rollback migrations
python manage.py migrate users zero

# Restart server
python manage.py runserver
```

---

## Support & Troubleshooting

### Common Issues

**Import Error: No module named 'argon2'**
```bash
pip install django[argon2]
```

**Migration Error: Table already exists**
```bash
python manage.py migrate users --fake
```

**Middleware Error**
- Check middleware order in settings.py
- Ensure SessionMiddleware is before AuthenticationMiddleware

**Password Not Hashing**
- Verify PASSWORD_HASHERS in settings.py
- Ensure Argon2 is first in the list

---

## Installation Complete! 🎉

Your custom authentication system is now installed and ready to use.

**Credentials:**
- Username: `admin`
- Password: `Admin@SasPulse2024!` (change this!)

**Next:** Create authentication views and templates to complete the system.

**Documentation:**
- Full details: `/Users/sas/Repos/saspulse/docs/CUSTOM_AUTH_IMPLEMENTATION_SUMMARY.md`
- Quick reference: `/Users/sas/Repos/saspulse/docs/CUSTOM_AUTH_QUICK_REFERENCE.md`
