# Users App - Custom Authentication System

Complete custom authentication system for SasPulse, independent of Django's built-in auth.

## Overview

This app provides a fully-featured authentication and authorization system with:
- Custom user model with profile fields
- Session-based authentication with security features
- Role-based access control (RBAC)
- Brute force protection
- Password complexity enforcement
- Email verification and password reset flows

## Quick Start

### Installation

```bash
# 1. Install Argon2
pip install django[argon2]

# 2. Add to settings.py
# See: /Users/sas/Repos/saspulse/docs/CUSTOM_AUTH_INSTALLATION_CHECKLIST.md

# 3. Run migrations
python manage.py makemigrations users
python manage.py migrate users

# 4. Create superuser
python manage.py shell
>>> from users.models import CustomUser
>>> admin = CustomUser.objects.create(
...     username='admin',
...     email='admin@example.com',
...     is_active=True,
...     is_staff=True,
...     is_superuser=True,
...     email_verified=True
... )
>>> admin.set_password('YourSecurePassword123!')
```

### Basic Usage

```python
# Protect a view
from users.decorators import login_required, permission_required

@login_required()
def my_view(request):
    user = request.user
    return render(request, 'template.html', {'user': user})

# Check permissions
@login_required()
@permission_required('users.create')
def create_user(request):
    # Only users with 'users.create' permission can access
    pass

# Authenticate users
from users.auth_backend import auth_backend

user = auth_backend.authenticate(request, username='john', password='pass')
if user:
    auth_backend.login(request, user, remember_me=True)
```

## File Structure

```
users/
├── models.py              # CustomUser, UserSession, Role models
├── auth_backend.py        # Authentication backend
├── middleware.py          # Authentication middleware
├── decorators.py          # View protection decorators
├── utils.py               # Password utilities
├── validators.py          # Django form validators
├── __init__.py            # Convenience imports
├── forms.py               # User management forms (existing)
├── views.py               # User management views (existing)
├── admin.py               # Django admin configuration
└── README.md              # This file
```

## Models

### CustomUser
Complete user model with authentication, profile, and security fields.

**Fields:**
- Identity: `id`, `username`, `email`, `password_hash`
- Personal: `first_name`, `last_name`, `phone_number`, `department`, `job_title`, `bio`
- Roles: `roles` (ManyToMany)
- Status: `is_active`, `is_staff`, `is_superuser`, `email_verified`
- Security: `failed_login_attempts`, `locked_until`, `last_login`, `last_password_change`
- Tokens: `activation_token`, `reset_token`, `reset_token_expires`
- Timestamps: `created_at`, `updated_at`

**Methods:**
- `set_password(raw_password)` - Hash and store password
- `check_password(raw_password)` - Verify password
- `has_permission(permission_key)` - Check permission
- `has_role(role_name)` - Check role
- `get_full_name()` - Get full name
- `generate_activation_token()` - Create email verification token
- `generate_reset_token()` - Create password reset token
- `is_locked()` - Check if account is locked
- `lock_account()` - Lock account
- `unlock_account()` - Unlock account

### UserSession
Session tracking and management.

**Fields:**
- `session_key` (PK) - Unique 40-char identifier
- `user` - ForeignKey to CustomUser
- `ip_address` - Client IP
- `user_agent` - Browser info
- `created_at`, `last_activity`, `expires_at`
- `is_active`, `remember_me`

**Methods:**
- `is_expired()` - Check expiration
- `extend_expiry(hours)` - Extend session
- `deactivate()` - Logout

### Role
Role-based permission system (existing, kept).

**Fields:**
- `name` - Role name
- `description` - Role description
- `permissions` - JSON permissions dict
- `is_active` - Active status

## Security Features

### Password Security
- **Argon2 hashing** - Industry-standard secure hashing
- **Complexity requirements** - 8+ chars, mixed case, numbers, special chars
- **Common password blocking** - 30+ weak passwords rejected
- **User attribute checking** - Password can't contain username/email

### Brute Force Protection
- **Failed attempt tracking** - Counter per user
- **Account locking** - 5 failed attempts = 30 min lockout
- **Automatic unlock** - Expires after lockout duration

### Session Security
- **Secure keys** - 40-char cryptographically random
- **Expiration** - 2 hours (default) or 30 days (remember me)
- **Sliding expiration** - Auto-extend on activity
- **IP/User Agent tracking** - Optional verification
- **Hijacking detection** - Security middleware

## Decorators

### @login_required()
Require authentication. Redirects to login if not authenticated.

```python
@login_required()
def my_view(request):
    # request.user is authenticated CustomUser
    pass

@login_required(redirect_to='/custom-login/')
def my_view(request):
    pass

@login_required(raise_exception=True)
def api_view(request):
    # Returns 403 JSON instead of redirecting
    pass
```

### @permission_required(permission_key)
Require specific permission via roles.

```python
@permission_required('users.create')
def create_user(request):
    pass
```

### @role_required(role_name)
Require specific role.

```python
@role_required('Admin')
def admin_panel(request):
    pass
```

### @verified_email_required()
Require verified email address.

```python
@verified_email_required()
def sensitive_view(request):
    pass
```

### @staff_required() / @superuser_required()
Require staff or superuser status.

```python
@staff_required()
def admin_view(request):
    pass
```

### @any_permission_required(*perms)
Require ANY of multiple permissions.

```python
@any_permission_required('users.view', 'users.create')
def user_management(request):
    pass
```

### @all_permissions_required(*perms)
Require ALL specified permissions.

```python
@all_permissions_required('users.view', 'users.edit')
def edit_users(request):
    pass
```

## Utilities

```python
from users.utils import (
    hash_password,
    check_password,
    validate_password_strength,
    validate_username,
    validate_email,
    generate_password,
    generate_token,
    get_password_strength_score,
)

# Validate password
is_valid, errors = validate_password_strength('MyPass123!')
if not is_valid:
    print('\n'.join(errors))

# Generate secure password
password = generate_password(length=12)

# Hash password
hashed = hash_password('password')

# Validate username
is_valid, error = validate_username('john_doe')

# Generate token
token = generate_token(32)
```

## Validators

Django form/model validators for input validation.

```python
from users.validators import (
    PasswordComplexityValidator,
    CommonPasswordValidator,
    UsernameValidator,
    EmailValidator,
    validate_password,
)

# In forms
class RegistrationForm(forms.Form):
    username = forms.CharField(validators=[UsernameValidator()])
    email = forms.EmailField(validators=[EmailValidator()])
    password = forms.CharField(validators=[
        PasswordComplexityValidator(),
        CommonPasswordValidator()
    ])

# Or use convenience function
try:
    validate_password('weakpass', user=user)
except ValidationError as e:
    print(e.messages)
```

## Configuration

Add to `settings.py`:

```python
# Password Hashers
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# Custom Auth Settings
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION = 30
ACTIVATION_TOKEN_EXPIRY = 24
RESET_TOKEN_EXPIRY = 1

# Session Settings
SESSION_COOKIE_AGE = 7200
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True

# Middleware
MIDDLEWARE = [
    # ... other middleware
    'users.middleware.AuthenticationMiddleware',
    'users.middleware.SessionSecurityMiddleware',
    # ... other middleware
]
```

## Examples

### User Registration

```python
from users.models import CustomUser
from users.utils import validate_password_strength

def register(request):
    username = request.POST.get('username')
    email = request.POST.get('email')
    password = request.POST.get('password')

    # Validate
    is_valid, errors = validate_password_strength(password)
    if not is_valid:
        return render(request, 'register.html', {'errors': errors})

    # Create user
    user = CustomUser.objects.create(
        username=username,
        email=email,
        is_active=False
    )
    user.set_password(password)

    # Send activation email
    token = user.generate_activation_token()
    send_activation_email(user.email, token)

    return redirect('registration_complete')
```

### Login

```python
from users.auth_backend import auth_backend

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember_me') == 'on'

        user = auth_backend.authenticate(request, username, password)

        if user:
            auth_backend.login(request, user, remember_me=remember)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {
                'error': 'Invalid credentials or account locked'
            })

    return render(request, 'login.html')
```

### Password Reset

```python
def reset_password(request, token):
    try:
        user = CustomUser.objects.get(
            reset_token=token,
            reset_token_expires__gt=timezone.now()
        )

        if request.method == 'POST':
            new_password = request.POST.get('password')
            user.set_password(new_password)
            user.reset_token = ''
            user.reset_token_expires = None
            user.save()

            # Invalidate all sessions
            from users.models import UserSession
            UserSession.objects.filter(user=user).update(is_active=False)

            return redirect('login')

        return render(request, 'reset_password.html')
    except CustomUser.DoesNotExist:
        return render(request, 'reset_failed.html')
```

## Testing

```python
# Test authentication
from django.test import TestCase
from users.models import CustomUser
from users.auth_backend import auth_backend

class AuthTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
        self.user.set_password('TestPass123!')

    def test_authentication(self):
        user = auth_backend.authenticate(
            self.request,
            username='testuser',
            password='TestPass123!'
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'testuser')

    def test_wrong_password(self):
        user = auth_backend.authenticate(
            self.request,
            username='testuser',
            password='wrongpass'
        )
        self.assertIsNone(user)
```

## Documentation

- **Full Implementation**: `/docs/CUSTOM_AUTH_IMPLEMENTATION_SUMMARY.md`
- **Quick Reference**: `/docs/CUSTOM_AUTH_QUICK_REFERENCE.md`
- **Installation Guide**: `/docs/CUSTOM_AUTH_INSTALLATION_CHECKLIST.md`
- **Original Plan**: `/docs/CUSTOM_AUTH_PLAN.md`

## Support

### Common Issues

**"No module named 'argon2'"**
```bash
pip install django[argon2]
```

**"Session not persisting"**
- Check SessionMiddleware is before AuthenticationMiddleware

**"User always AnonymousUser"**
- Verify custom middleware is added to settings.py

**"Permissions not working"**
- Ensure user has roles assigned
- Verify roles have correct permissions

### Debug

```python
# Check authentication
print(f"User: {request.user}")
print(f"Type: {type(request.user)}")
print(f"Authenticated: {not isinstance(request.user, AnonymousUser)}")

# Check session
print(f"Session key: {request.session.get('custom_session_key')}")

# Check permissions
print(f"Permissions: {request.user.get_all_permissions()}")
print(f"Has permission: {request.user.has_permission('users.create')}")

# Check roles
print(f"Roles: {list(request.user.roles.values_list('name', flat=True))}")
```

## License

Copyright (c) 2024 SasPulse Team. All rights reserved.

## Version

1.0.0 - Initial implementation (February 2024)
