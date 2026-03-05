# Custom Authentication - Quick Reference Card

## Quick Start

### 1. Basic Login/Logout

```python
from users.auth_backend import auth_backend

# Login
def login_view(request):
    user = auth_backend.authenticate(request, username='john', password='Pass123!')
    if user:
        auth_backend.login(request, user, remember_me=True)
        return redirect('dashboard')

# Logout
def logout_view(request):
    auth_backend.logout(request)
    return redirect('login')
```

### 2. Protect Views

```python
from users.decorators import login_required, permission_required, role_required

@login_required()
def my_view(request):
    # Only authenticated users
    pass

@login_required()
@permission_required('users.create')
def create_user(request):
    # Only users with permission
    pass

@login_required()
@role_required('Admin')
def admin_panel(request):
    # Only users with Admin role
    pass
```

### 3. Create Users

```python
from users.models import CustomUser

# Create user
user = CustomUser.objects.create(
    username='john_doe',
    email='john@example.com',
    first_name='John',
    last_name='Doe'
)
user.set_password('SecurePass123!')

# Activate account
user.is_active = True
user.email_verified = True
user.save()

# Assign role
from users.models import Role
admin_role = Role.objects.get(name='Admin')
user.roles.add(admin_role)
```

### 4. Check Permissions

```python
# In views
if request.user.has_permission('users.create'):
    # User can create users
    pass

if request.user.has_role('Admin'):
    # User is admin
    pass

if request.user.is_superuser:
    # User has all permissions
    pass

# Get all permissions
permissions = request.user.get_all_permissions()
```

### 5. Password Operations

```python
from users.utils import (
    validate_password_strength,
    generate_password,
    hash_password
)

# Validate password
is_valid, errors = validate_password_strength('MyPass123!')
if not is_valid:
    print('\n'.join(errors))

# Generate random password
temp_password = generate_password(length=12)

# Change password
user.set_password('NewPassword123!')

# Verify password
if user.check_password('test'):
    print('Password correct')
```

### 6. Token Operations

```python
# Email verification
activation_token = user.generate_activation_token()
# Send token via email

# Password reset
reset_token = user.generate_reset_token(expiry_hours=1)
# Send token via email

# Verify token
if user.reset_token == token and user.reset_token_expires > timezone.now():
    # Token valid
    user.set_password(new_password)
    user.reset_token = ''
    user.reset_token_expires = None
    user.save()
```

### 7. Session Management

```python
from users.models import UserSession

# Get active sessions for user
sessions = UserSession.objects.filter(user=user, is_active=True)

# Terminate specific session
session = UserSession.objects.get(session_key=key)
session.deactivate()

# Get current session
session_key = request.session.get('custom_session_key')
session = UserSession.objects.get(session_key=session_key)
```

---

## Common Patterns

### Registration Flow

```python
from users.models import CustomUser
from users.utils import validate_password_strength, validate_username, validate_email

def register(request):
    username = request.POST.get('username')
    email = request.POST.get('email')
    password = request.POST.get('password')

    # Validate
    valid_username, username_error = validate_username(username)
    valid_email, email_error = validate_email(email)
    valid_password, password_errors = validate_password_strength(password)

    if valid_username and valid_email and valid_password:
        # Create user
        user = CustomUser.objects.create(
            username=username,
            email=email,
            is_active=False  # Require activation
        )
        user.set_password(password)

        # Generate activation token
        token = user.generate_activation_token()

        # Send activation email
        send_activation_email(user.email, token)

        return redirect('registration_complete')
```

### Account Activation

```python
def activate_account(request, token):
    try:
        user = CustomUser.objects.get(activation_token=token)
        user.is_active = True
        user.email_verified = True
        user.activation_token = ''
        user.save()
        return redirect('login')
    except CustomUser.DoesNotExist:
        return render(request, 'activation_failed.html')
```

### Password Reset Flow

```python
# Request reset
def forgot_password(request):
    email = request.POST.get('email')
    try:
        user = CustomUser.objects.get(email=email)
        token = user.generate_reset_token(expiry_hours=1)
        send_reset_email(user.email, token)
        return redirect('reset_email_sent')
    except CustomUser.DoesNotExist:
        # Don't reveal if email exists
        return redirect('reset_email_sent')

# Reset password
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
            UserSession.objects.filter(user=user).update(is_active=False)

            return redirect('login')

        return render(request, 'reset_password.html')
    except CustomUser.DoesNotExist:
        return render(request, 'reset_failed.html')
```

### Change Password (Authenticated)

```python
from users.decorators import login_required

@login_required()
def change_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')

        # Verify old password
        if not request.user.check_password(old_password):
            return render(request, 'change_password.html', {
                'error': 'Current password is incorrect'
            })

        # Validate new password
        is_valid, errors = validate_password_strength(new_password)
        if not is_valid:
            return render(request, 'change_password.html', {
                'errors': errors
            })

        # Change password
        request.user.set_password(new_password)
        return redirect('profile')

    return render(request, 'change_password.html')
```

---

## Decorator Reference

```python
# Basic authentication
@login_required()
@login_required(redirect_to='/custom-login/')
@login_required(raise_exception=True)

# Permission checking
@permission_required('users.create')
@permission_required('users.create', raise_exception=False)

# Role checking
@role_required('Admin')
@role_required('Manager', raise_exception=False)

# Email verification
@verified_email_required()
@verified_email_required(redirect_to='/verify-prompt/')

# Staff/Superuser
@staff_required()
@superuser_required()

# Multiple permissions
@any_permission_required('users.view', 'users.create')  # ANY
@all_permissions_required('users.view', 'users.create')  # ALL

# Combining decorators
@login_required()
@verified_email_required()
@permission_required('reports.view')
def sensitive_view(request):
    pass
```

---

## Template Usage

```django
<!-- Check authentication -->
{% if request.user.is_authenticated %}
    <p>Welcome, {{ request.user.get_full_name }}!</p>
{% endif %}

<!-- Check permission -->
{% if request.user.has_permission.users.create %}
    <a href="{% url 'create_user' %}">Create User</a>
{% endif %}

<!-- Check role -->
{% if request.user.has_role.Admin %}
    <a href="{% url 'admin_panel' %}">Admin</a>
{% endif %}

<!-- Check staff -->
{% if request.user.is_staff %}
    <a href="/admin/">Django Admin</a>
{% endif %}

<!-- User info -->
<p>Email: {{ request.user.email }}</p>
<p>Username: {{ request.user.username }}</p>
<p>Joined: {{ request.user.created_at|date:"Y-m-d" }}</p>
```

---

## Model Fields Reference

### CustomUser Fields

```python
# Identity
user.id
user.username
user.email

# Personal
user.first_name
user.last_name
user.phone_number
user.department
user.job_title
user.bio

# Status
user.is_active
user.is_staff
user.is_superuser
user.email_verified

# Security
user.failed_login_attempts
user.locked_until
user.last_login
user.last_password_change

# Tokens
user.activation_token
user.reset_token
user.reset_token_expires

# Relations
user.roles.all()

# Timestamps
user.created_at
user.updated_at
```

### UserSession Fields

```python
session.session_key
session.user
session.ip_address
session.user_agent
session.created_at
session.last_activity
session.expires_at
session.is_active
session.remember_me
```

---

## Utility Functions

```python
from users.utils import *

# Password
hash_password(raw_password)
check_password(raw_password, hash)
validate_password_strength(password)  # Returns (bool, [errors])
get_password_strength_score(password)  # Returns 0-5
generate_password(length=12, use_special=True)
is_password_compromised(password)

# Username/Email
validate_username(username)  # Returns (bool, error)
validate_email(email)  # Returns (bool, error)
sanitize_username(username)
mask_email(email)  # Returns 'u***@example.com'

# Tokens
generate_token(length=32)
generate_session_key()

# Request helpers
get_client_ip(request)
get_user_agent(request)
```

---

## Error Handling

```python
from django.core.exceptions import ValidationError
from users.validators import validate_password

try:
    validate_password('weakpass')
except ValidationError as e:
    print(e.messages)  # List of errors
```

---

## Settings Configuration

```python
# saspulse/settings.py

# Password hashers
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# Custom auth settings
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION = 30  # minutes
ACTIVATION_TOKEN_EXPIRY = 24  # hours
RESET_TOKEN_EXPIRY = 1  # hour

# Session settings
SESSION_COOKIE_AGE = 7200  # 2 hours
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# URLs
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'users.middleware.AuthenticationMiddleware',
    'users.middleware.SessionSecurityMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

---

## Migration Commands

```bash
# Create migrations
python manage.py makemigrations users

# Run migrations
python manage.py migrate users

# Create superuser (via shell)
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
>>> admin.set_password('YourPassword123!')
>>> exit()
```

---

## Debugging

```python
# Check authentication
print(f"User: {request.user}")
print(f"Authenticated: {request.user.is_authenticated}")
print(f"Type: {type(request.user)}")

# Check session
print(f"Session key: {request.session.get('custom_session_key')}")
print(f"Session data: {dict(request.session)}")

# Check permissions
print(f"All permissions: {request.user.get_all_permissions()}")
print(f"Has permission: {request.user.has_permission('users.create')}")

# Check roles
print(f"Roles: {list(request.user.roles.values_list('name', flat=True))}")
print(f"Has role: {request.user.has_role('Admin')}")

# Check account status
print(f"Is active: {request.user.is_active}")
print(f"Is locked: {request.user.is_locked()}")
print(f"Failed attempts: {request.user.failed_login_attempts}")
```

---

## Common Issues

**Issue:** "No module named 'argon2'"
**Solution:** `pip install django[argon2]` or `pip install argon2-cffi`

**Issue:** User always AnonymousUser
**Solution:** Check middleware order, ensure SessionMiddleware before AuthenticationMiddleware

**Issue:** Permissions not working
**Solution:** Verify user has roles assigned and roles have permissions

**Issue:** Account locked forever
**Solution:** `user.unlock_account()` or wait 30 minutes

**Issue:** Session not persisting
**Solution:** Check SESSION_COOKIE_SECURE setting (False for HTTP, True for HTTPS)

---

## API Endpoints (To Implement)

```python
# urls.py
from users import views

urlpatterns = [
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/activate/<str:token>/', views.ActivateView.as_view(), name='activate'),
    path('auth/forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('auth/reset-password/<str:token>/', views.ResetPasswordView.as_view(), name='reset_password'),
    path('system/profile/', views.ProfileView.as_view(), name='profile'),
    path('system/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
]
```

---

## Quick Import Cheatsheet

```python
# Models
from users.models import CustomUser, UserSession, Role

# Auth backend
from users.auth_backend import auth_backend, AnonymousUser

# Decorators (most common)
from users.decorators import (
    login_required,
    permission_required,
    role_required
)

# Utils (most common)
from users.utils import (
    hash_password,
    validate_password_strength,
    generate_password
)

# Validators
from users.validators import validate_password

# OR use convenience imports
from users import (
    CustomUser,
    auth_backend,
    login_required,
    hash_password
)
```

---

**Documentation:** See `/Users/sas/Repos/saspulse/docs/CUSTOM_AUTH_IMPLEMENTATION_SUMMARY.md` for full details.
