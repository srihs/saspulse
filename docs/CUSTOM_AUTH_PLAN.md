# Custom Authentication System - Architecture Plan

## 🎯 Overview

Replace Django's built-in authentication system with a custom implementation that provides:
- Custom user model (not extending Django's User)
- Custom authentication backend
- Session-based authentication
- Role-based access control (already implemented)
- Login/Logout/Registration flows
- Password hashing and security

---

## 📋 Requirements

### Functional Requirements
1. ✅ User registration with email verification
2. ✅ Login with username/email and password
3. ✅ Logout functionality
4. ✅ Session management
5. ✅ Password hashing (secure)
6. ✅ Remember me functionality
7. ✅ Password reset flow
8. ✅ Account activation
9. ✅ Multi-role support (already built)
10. ✅ Permission checking

### Non-Functional Requirements
1. ✅ Secure password storage (bcrypt/argon2)
2. ✅ Session security
3. ✅ CSRF protection
4. ✅ Brute force protection
5. ✅ Password complexity requirements

---

## 🏗️ Architecture Design

### 1. Custom User Model

**Location:** `users/models.py`

```python
class User(models.Model):
    """Custom User model - completely independent of Django's auth"""

    # Core Identity
    id = BigAutoField(primary_key=True)
    username = CharField(unique=True, max_length=150)
    email = EmailField(unique=True)

    # Authentication
    password_hash = CharField(max_length=255)  # Store hashed password

    # Personal Information
    first_name = CharField(max_length=150, blank=True)
    last_name = CharField(max_length=150, blank=True)

    # Profile Fields (moved from UserProfile)
    phone_number = CharField(max_length=20, blank=True)
    department = CharField(max_length=100, blank=True)
    job_title = CharField(max_length=100, blank=True)
    bio = TextField(blank=True)

    # Roles & Permissions
    roles = ManyToManyField('Role', related_name='users')

    # Status & Flags
    is_active = BooleanField(default=False)  # Require activation
    is_staff = BooleanField(default=False)   # Can access admin
    is_superuser = BooleanField(default=False)  # Super admin
    email_verified = BooleanField(default=False)

    # Security
    failed_login_attempts = IntegerField(default=0)
    locked_until = DateTimeField(null=True, blank=True)
    last_login = DateTimeField(null=True, blank=True)
    last_password_change = DateTimeField(null=True, blank=True)

    # Tokens
    activation_token = CharField(max_length=64, blank=True)
    reset_token = CharField(max_length=64, blank=True)
    reset_token_expires = DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        indexes = [
            Index(fields=['username']),
            Index(fields=['email']),
            Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.username

    # Methods
    def set_password(self, raw_password)
    def check_password(self, raw_password)
    def has_permission(self, permission_key)
    def has_role(self, role_name)
    def get_full_name(self)
    def generate_activation_token(self)
    def generate_reset_token(self)
    def is_locked(self)
    def lock_account(self, duration_minutes=30)
    def unlock_account(self)
```

### 2. Session Model

**Location:** `users/models.py`

```python
class UserSession(models.Model):
    """Custom session management"""

    session_key = CharField(max_length=40, primary_key=True)
    user = ForeignKey('User', on_delete=CASCADE, related_name='sessions')
    ip_address = GenericIPAddressField(null=True)
    user_agent = TextField(blank=True)

    created_at = DateTimeField(auto_now_add=True)
    last_activity = DateTimeField(auto_now=True)
    expires_at = DateTimeField()

    is_active = BooleanField(default=True)
    remember_me = BooleanField(default=False)

    class Meta:
        db_table = 'user_sessions'
        indexes = [
            Index(fields=['user', 'is_active']),
            Index(fields=['expires_at']),
        ]
```

### 3. Authentication Backend

**Location:** `users/auth_backend.py`

```python
class CustomAuthBackend:
    """Custom authentication backend"""

    def authenticate(self, request, username=None, password=None):
        """Authenticate user by username/email and password"""

    def login(self, request, user, remember_me=False):
        """Login user and create session"""

    def logout(self, request):
        """Logout user and destroy session"""

    def get_user_from_session(self, request):
        """Get user from session key"""

    def is_authenticated(self, request):
        """Check if request has valid session"""
```

### 4. Middleware

**Location:** `users/middleware.py`

```python
class AuthenticationMiddleware:
    """Attach user to request based on session"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get user from session
        # Attach to request.user
        # Update last_activity

class SessionSecurityMiddleware:
    """Handle session security"""

    # Check session expiration
    # Validate IP address (optional)
    # Check for session hijacking
```

### 5. Views Structure

**Location:** `users/auth_views.py`

```python
# Public Views (no login required)
- LoginView (GET/POST)
- RegisterView (GET/POST)
- ActivateAccountView (GET with token)
- ForgotPasswordView (GET/POST)
- ResetPasswordView (GET/POST with token)

# Authenticated Views (login required)
- LogoutView (POST)
- ChangePasswordView (GET/POST)
- ProfileView (GET/POST)
```

### 6. Forms

**Location:** `users/auth_forms.py`

```python
- LoginForm (username/email, password, remember_me)
- RegisterForm (username, email, password, password_confirm, first_name, last_name)
- ForgotPasswordForm (email)
- ResetPasswordForm (password, password_confirm)
- ChangePasswordForm (old_password, new_password, new_password_confirm)
```

### 7. Decorators

**Location:** `users/decorators.py`

```python
@login_required
@permission_required(permission_key)
@role_required(role_name)
@verified_email_required
```

---

## 🔐 Security Features

### Password Hashing
- Use **Argon2** (recommended) or **bcrypt**
- Salt automatically handled
- Password complexity requirements:
  - Minimum 8 characters
  - At least 1 uppercase
  - At least 1 lowercase
  - At least 1 number
  - At least 1 special character

### Session Security
- Session key: 40-character random string
- Session expiration:
  - Default: 2 hours of inactivity
  - Remember me: 30 days
- CSRF token required for all POST requests
- Session rotation on login

### Brute Force Protection
- Lock account after 5 failed attempts
- Lockout duration: 30 minutes
- Track failed attempts per IP
- CAPTCHA after 3 failed attempts (future)

### Email Verification
- Send activation email on registration
- Token expires after 24 hours
- Re-send activation email option

### Password Reset
- Send reset link to email
- Token expires after 1 hour
- One-time use token
- Invalidate all sessions on password reset

---

## 🎨 UI Pages Required

Using Phoenix Admin Template styling:

1. **Login Page** (`/auth/login/`)
   - Username/Email field
   - Password field
   - Remember me checkbox
   - Login button
   - Links: Forgot password, Register

2. **Registration Page** (`/auth/register/`)
   - Username, Email, Password fields
   - First name, Last name
   - Terms acceptance checkbox
   - Register button
   - Link: Back to login

3. **Activation Page** (`/auth/activate/<token>/`)
   - Success/Error message
   - Link to login

4. **Forgot Password Page** (`/auth/forgot-password/`)
   - Email field
   - Send reset link button
   - Link: Back to login

5. **Reset Password Page** (`/auth/reset-password/<token>/`)
   - New password fields
   - Reset button
   - Link: Back to login

6. **Change Password Page** (`/system/change-password/`)
   - Old password field
   - New password fields
   - Change button

7. **Profile Page** (`/system/profile/`)
   - Edit personal information
   - View roles
   - Change password link

---

## 🔄 Migration Strategy

### Phase 1: Create Custom User Model
1. Create new User model (without extending Django User)
2. Create UserSession model
3. Keep existing UserProfile/Role models temporarily
4. Run migrations

### Phase 2: Build Auth Backend
1. Implement CustomAuthBackend
2. Implement middleware
3. Create decorators
4. Test authentication flow

### Phase 3: Build UI
1. Create login/register templates
2. Create password reset flow
3. Create profile page
4. Style with Phoenix template

### Phase 4: Data Migration
1. Migrate existing Django users to custom User model
2. Preserve passwords (rehash if needed)
3. Migrate role assignments
4. Test all users can login

### Phase 5: Remove Django Auth
1. Remove django.contrib.auth from INSTALLED_APPS
2. Remove django.contrib.auth middleware
3. Update all @login_required to custom decorator
4. Delete old UserProfile model
5. Clean up migrations

### Phase 6: Testing
1. Test login/logout
2. Test registration
3. Test password reset
4. Test permissions
5. Test session expiration
6. Test brute force protection

---

## 📁 File Structure

```
users/
├── models.py               # User, UserSession, Role models
├── auth_backend.py         # CustomAuthBackend
├── auth_views.py           # Login, Register, etc.
├── auth_forms.py           # All authentication forms
├── decorators.py           # @login_required, @permission_required
├── middleware.py           # Authentication & session middleware
├── utils.py                # Password hashing, token generation
├── validators.py           # Password validators
├── templates/users/auth/
│   ├── login.html
│   ├── register.html
│   ├── activate.html
│   ├── forgot_password.html
│   ├── reset_password.html
│   ├── change_password.html
│   └── profile.html
└── migrations/
    └── 0002_custom_auth.py
```

---

## 🔗 URL Structure

```
/auth/login/                    → LoginView
/auth/logout/                   → LogoutView
/auth/register/                 → RegisterView
/auth/activate/<token>/         → ActivateAccountView
/auth/forgot-password/          → ForgotPasswordView
/auth/reset-password/<token>/   → ResetPasswordView

/system/profile/                → ProfileView (authenticated)
/system/change-password/        → ChangePasswordView (authenticated)
/system/users/                  → User management (existing)
/system/roles/                  → Role management (existing)
```

---

## ⚙️ Settings Configuration

```python
# settings.py

# Remove Django auth
INSTALLED_APPS = [
    # 'django.contrib.auth',  # REMOVE
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'users',
    'cin7',
]

# Custom middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'users.middleware.AuthenticationMiddleware',  # CUSTOM
    'users.middleware.SessionSecurityMiddleware',  # CUSTOM
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Custom auth backend
AUTHENTICATION_BACKENDS = [
    'users.auth_backend.CustomAuthBackend',
]

# Session settings
SESSION_COOKIE_AGE = 7200  # 2 hours
SESSION_COOKIE_SECURE = True  # HTTPS only in production
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Password hashing
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# Password validation
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_LOWERCASE = True
PASSWORD_REQUIRE_NUMBERS = True
PASSWORD_REQUIRE_SPECIAL = True

# Account security
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION = 30  # minutes
ACTIVATION_TOKEN_EXPIRY = 24  # hours
RESET_TOKEN_EXPIRY = 1  # hour

# Email settings (for activation/reset)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = 'noreply@saspulse.com'
```

---

## 🧪 Testing Checklist

### Authentication Tests
- [ ] User can register with valid data
- [ ] Registration fails with invalid data
- [ ] Activation email is sent
- [ ] User can activate account with valid token
- [ ] Activation fails with invalid token
- [ ] User can login with username/password
- [ ] User can login with email/password
- [ ] Login fails with wrong password
- [ ] Account locks after 5 failed attempts
- [ ] Remember me extends session duration
- [ ] User can logout
- [ ] Sessions are properly destroyed on logout

### Password Reset Tests
- [ ] User can request password reset
- [ ] Reset email is sent
- [ ] User can reset password with valid token
- [ ] Reset fails with invalid/expired token
- [ ] All sessions invalidated on password reset

### Permission Tests
- [ ] @login_required blocks unauthenticated users
- [ ] @permission_required checks permissions correctly
- [ ] @role_required checks roles correctly
- [ ] Superuser has all permissions

### Security Tests
- [ ] Passwords are properly hashed
- [ ] Sessions have CSRF protection
- [ ] Sessions expire after inactivity
- [ ] Brute force protection works
- [ ] Password complexity is enforced

---

## 📊 Comparison: Django Auth vs Custom Auth

| Feature | Django Auth | Custom Auth |
|---------|-------------|-------------|
| User Model | Fixed schema | Flexible schema |
| Extensions | Via UserProfile | Direct in User model |
| Dependencies | Many Django internals | Minimal dependencies |
| Control | Limited | Full control |
| Learning Curve | Low | Medium |
| Maintenance | Django handles | We handle |
| Customization | Limited | Unlimited |
| Performance | Good | Optimized for our needs |

---

## 🎯 Success Criteria

1. ✅ Users can register, login, and logout
2. ✅ Email verification works
3. ✅ Password reset works
4. ✅ Sessions are secure and expire properly
5. ✅ Brute force protection is active
6. ✅ All existing user management features still work
7. ✅ Role-based permissions work correctly
8. ✅ UI matches Phoenix Admin template
9. ✅ No dependency on django.contrib.auth
10. ✅ All tests pass

---

## 📝 Implementation Steps

1. **Backend Agent:** Create models, auth backend, middleware
2. **Backend Agent:** Create decorators and utilities
3. **Frontend Agent:** Create authentication UI templates
4. **Backend Agent:** Implement views and forms
5. **Testing Agent:** Create comprehensive test suite
6. **Backend Agent:** Data migration from Django auth
7. **Backend Agent:** Remove Django auth dependencies
8. **Testing:** Full system testing

---

## ⏱️ Estimated Timeline

- **Phase 1:** Custom models - 2 hours
- **Phase 2:** Auth backend - 3 hours
- **Phase 3:** UI templates - 2 hours
- **Phase 4:** Data migration - 1 hour
- **Phase 5:** Remove Django auth - 1 hour
- **Phase 6:** Testing - 2 hours

**Total:** ~11 hours of development time

---

**Status:** Planning Complete ✅
**Next Step:** Begin implementation with agents
