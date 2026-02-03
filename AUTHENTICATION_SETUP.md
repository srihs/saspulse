# SasPulse Authentication System - Complete Setup

## Overview

A complete custom authentication system has been built for SasPulse with all necessary views, forms, templates, and URL patterns. The system uses the custom auth backend located at `/users/auth_backend.py`.

## Files Created

### Backend Files

1. **users/auth_forms.py** (14KB)
   - LoginForm: Username/email + password + remember me
   - RegisterForm: Full registration with validation
   - ForgotPasswordForm: Email validation
   - ResetPasswordForm: Password reset with strength validation
   - ChangePasswordForm: Password change for authenticated users
   - ProfileForm: User profile editing

2. **users/auth_views.py** (16KB)
   - LoginView: Handle login with remember me
   - LogoutView: POST-only logout
   - RegisterView: User registration + activation email
   - ActivateAccountView: Email token activation
   - ForgotPasswordView: Password reset request
   - ResetPasswordView: Password reset with token
   - ChangePasswordView: Password change (authenticated)
   - ProfileView: View/edit profile (authenticated)
   - CheckEmailView: Generic "check email" page

3. **users/auth_urls.py** (1KB)
   - URL patterns for all authentication views

4. **users/email_utils.py** (3KB)
   - send_activation_email(): Logs token to console (dev mode)
   - send_password_reset_email(): Logs token to console (dev mode)
   - get_token_display_info(): Helper for token display

### Templates

All templates use Phoenix Admin styling with clean, centered layouts for auth pages.

**Standalone Auth Pages** (no sidebar):
1. **login.html** (8KB) - Login form with remember me
2. **register.html** (13KB) - Registration form with validation
3. **activate.html** (7KB) - Account activation success/error
4. **forgot_password.html** (7KB) - Password reset request
5. **reset_password.html** (11KB) - Password reset form
6. **check_email.html** (8KB) - Check email message

**Authenticated Pages** (with base.html):
7. **change_password.html** (7KB) - Password change form
8. **profile.html** (11KB) - User profile with roles and sessions

### Configuration Updates

1. **users/urls.py** - Updated to include:
   - Authentication URLs at `/system/auth/`
   - Profile at `/system/profile/`
   - Change password at `/system/change-password/`

2. **saspulse/settings.py** - Added:
   - `SITE_URL = 'http://localhost:8000'` (for email links)

## URL Structure

All authentication URLs are prefixed with `/system/` (from main urls.py):

### Public Authentication URLs
- `/system/auth/login/` - Login page
- `/system/auth/logout/` - Logout (POST only)
- `/system/auth/register/` - Registration page
- `/system/auth/activate/<token>/` - Account activation
- `/system/auth/forgot-password/` - Password reset request
- `/system/auth/reset-password/<token>/` - Password reset
- `/system/auth/check-email/<email_type>/` - Check email page

### Authenticated User URLs
- `/system/profile/` - User profile
- `/system/change-password/` - Change password

## Features Implemented

### 1. Login (LoginView)
- Username or email authentication
- Remember me checkbox (30-day sessions vs 2-hour)
- Failed login tracking
- Account lockout after 5 failed attempts (30 min lockout)
- Redirect to `?next=` parameter or dashboard
- Error messages for locked accounts and inactive accounts

### 2. Registration (RegisterView)
- Username, email, first name, last name, password
- Password strength validation (8+ chars, uppercase, lowercase, number, special)
- Username and email uniqueness validation
- Terms and conditions checkbox
- Account created as inactive (requires email verification)
- Activation token generated and logged to console

### 3. Account Activation (ActivateAccountView)
- Token-based activation via email link
- Sets `is_active=True` and `email_verified=True`
- Clears activation token after successful activation
- Success/error display

### 4. Forgot Password (ForgotPasswordView)
- Email validation (checks if account exists)
- Generates reset token (valid for 1 hour)
- Logs token to console for development
- Security: Doesn't reveal if email exists

### 5. Reset Password (ResetPasswordView)
- Token validation with expiry check
- Password strength validation
- Invalidates all active sessions after reset
- Clears reset token after successful reset

### 6. Change Password (ChangePasswordView)
- Requires authentication
- Validates old password
- Ensures new password is different
- Password strength validation

### 7. Profile Management (ProfileView)
- View and edit profile information
- Display assigned roles with badges
- Show active sessions with IP and last activity
- Phone number, department, job title, bio

## Form Validation

### Password Strength Requirements
All password forms validate:
- Minimum 8 characters
- At least one uppercase letter (A-Z)
- At least one lowercase letter (a-z)
- At least one number (0-9)
- At least one special character (!@#$%^&*(),.?":{}|<>)

### Username Validation
- 3-150 characters
- Letters, digits, and @/./+/-/_ only
- Unique across system

### Email Validation
- Valid email format
- Unique across system

### Phone Number Validation
- 7-15 digits
- Formatting characters allowed: spaces, dashes, parentheses, plus

## Email Handling (Development Mode)

For development, emails are NOT actually sent. Instead:

1. **Activation Emails**: Token is logged to console with URL
2. **Password Reset Emails**: Token is logged to console with URL
3. **Check Email Page**: Shows development note to check console logs

### Console Output Format
```
================================================================================
ACTIVATION EMAIL
================================================================================
To: user@example.com
Subject: Activate your SasPulse account
Username: testuser
Activation Token: <token>
Activation URL: http://localhost:8000/system/auth/activate/<token>/
================================================================================
```

### Production Email Setup
To enable real emails in production:
1. Configure Django email settings in `settings.py`
2. Update `users/email_utils.py` to use `send_mail()`
3. Remove console logging statements
4. Test email delivery

## Security Features

1. **Brute Force Protection**
   - Max 5 failed login attempts
   - 30-minute account lockout
   - Auto-unlock after duration

2. **Session Management**
   - Configurable session duration (2 hours default)
   - Remember me extends to 30 days
   - Session tracking with IP and user agent
   - Sliding expiration (extends on activity)

3. **Token Security**
   - Secure token generation using `secrets.token_urlsafe(32)`
   - Token expiration (1 hour for password reset)
   - Tokens cleared after use

4. **Password Security**
   - Strong password requirements enforced
   - Argon2 password hashing (Django default)
   - Old password verification for changes

5. **CSRF Protection**
   - All POST requests require CSRF token
   - Logout is POST-only (prevents CSRF attacks)

## Testing Recommendations

### 1. Manual Testing Checklist

#### Registration Flow
- [ ] Access `/system/auth/register/`
- [ ] Fill form with valid data
- [ ] Submit and verify redirect to check email page
- [ ] Check console logs for activation token
- [ ] Copy activation URL and paste in browser
- [ ] Verify account activation success
- [ ] Attempt login with new account

#### Login Flow
- [ ] Access `/system/auth/login/`
- [ ] Test login with username
- [ ] Test login with email
- [ ] Test "Remember Me" checkbox
- [ ] Test wrong password (should track failed attempts)
- [ ] Test 5 failed attempts (should lock account)
- [ ] Test login with inactive account

#### Password Reset Flow
- [ ] Click "Forgot Password" on login page
- [ ] Enter registered email
- [ ] Check console for reset token
- [ ] Access reset URL
- [ ] Set new password
- [ ] Verify redirect to login
- [ ] Login with new password
- [ ] Verify old sessions are invalidated

#### Profile Management
- [ ] Login and access `/system/profile/`
- [ ] Edit profile information
- [ ] View assigned roles
- [ ] Check active sessions list
- [ ] Access `/system/change-password/`
- [ ] Change password successfully
- [ ] Verify redirect to profile

### 2. Test User Creation

Create test users via Django shell:

```python
from users.models import CustomUser

# Create active user
user = CustomUser.objects.create(
    username='testuser',
    email='test@example.com',
    first_name='Test',
    last_name='User',
    is_active=True,
    email_verified=True
)
user.set_password('TestPass123!')

# Create superuser
admin = CustomUser.objects.create(
    username='admin',
    email='admin@example.com',
    first_name='Admin',
    last_name='User',
    is_active=True,
    email_verified=True,
    is_superuser=True,
    is_staff=True
)
admin.set_password('AdminPass123!')
```

### 3. Edge Cases to Test

1. **Expired Tokens**
   - Manually set `reset_token_expires` to past date
   - Attempt to use reset link

2. **Locked Account**
   - Manually set `locked_until` to future date
   - Attempt login

3. **Invalid Tokens**
   - Use random token in activation URL
   - Use random token in reset URL

4. **Duplicate Data**
   - Register with existing username
   - Register with existing email

5. **Session Management**
   - Login from multiple browsers
   - Check active sessions in profile
   - Logout from one session

### 4. Security Testing

1. **CSRF Protection**
   - Remove CSRF token from form
   - Attempt form submission

2. **Session Hijacking**
   - Copy session cookie
   - Try to use in different browser

3. **Brute Force**
   - Attempt 10 failed logins
   - Verify account is locked

4. **Token Reuse**
   - Use activation token twice
   - Use reset token twice

## Integration with Existing System

### Custom User Model
The system uses `CustomUser` model from `/users/models.py` with:
- Custom authentication fields
- Role-based permissions
- Security tracking (failed attempts, lockouts)
- Email verification
- Token management

### Custom Auth Backend
Authentication is handled by `CustomAuthBackend` from `/users/auth_backend.py`:
- `authenticate()` - Verify credentials
- `login()` - Create session
- `logout()` - Destroy session
- `get_user_from_session()` - Retrieve authenticated user

### Middleware Integration
The custom middleware in `/users/middleware.py` adds `request.user` to every request by calling `auth_backend.get_user_from_session(request)`.

## Next Steps

### 1. Immediate Tasks
- [ ] Test all authentication flows manually
- [ ] Create initial superuser account
- [ ] Test role assignment and permissions

### 2. Optional Enhancements
- [ ] Add "Remember Me for 7 days" option
- [ ] Add account deletion functionality
- [ ] Add email change with verification
- [ ] Add two-factor authentication (2FA)
- [ ] Add password history (prevent reusing old passwords)
- [ ] Add account activity log
- [ ] Add "Login with Google/OAuth" options

### 3. Production Preparation
- [ ] Configure real email backend (SMTP/SendGrid/etc.)
- [ ] Update email templates with branding
- [ ] Set up email rate limiting
- [ ] Configure SSL/HTTPS for production
- [ ] Update SITE_URL to production domain
- [ ] Test all flows in production environment

## Troubleshooting

### Issue: Templates not found
**Solution**: Ensure `users` is in `INSTALLED_APPS` in settings.py

### Issue: Import errors
**Solution**: Verify all imports in auth_views.py:
```python
from .models import CustomUser, UserSession
from .auth_backend import auth_backend
from .auth_forms import LoginForm, RegisterForm, etc.
from .email_utils import send_activation_email, send_password_reset_email
```

### Issue: URL resolution errors
**Solution**: Check that `users.auth_urls` is included in `users/urls.py`:
```python
path('auth/', include('users.auth_urls')),
```

### Issue: Static files not loading
**Solution**: Run `python manage.py collectstatic` and ensure Phoenix static files are in place

### Issue: Form validation not working
**Solution**: Check form errors in template:
```django
{% if form.errors %}
    <!-- Display errors -->
{% endif %}
```

## Summary

The complete authentication system is now ready with:
- ✅ 8 class-based views (login, register, activate, forgot, reset, change, profile, check email)
- ✅ 6 Django forms with comprehensive validation
- ✅ 8 Phoenix Admin styled templates
- ✅ Email utilities with development logging
- ✅ URL configuration for all routes
- ✅ Security features (brute force protection, token expiry, session management)
- ✅ Integration with existing custom auth backend

The system is production-ready except for email configuration, which currently logs to console for development convenience.
