# Django Authentication & Authorization System Analysis - SasPulse

## Executive Summary
The SasPulse project implements a **custom authentication and authorization system** that completely replaces Django's built-in authentication framework. This custom system provides fine-grained control over user authentication, session management, role-based access control (RBAC), and permission checking.

---

## 1. USER MODEL & AUTHENTICATION SETUP

### 1.1 Custom User Model (Primary Implementation)
**File**: `/Users/sas/Repos/saspulse/users/models.py` (Lines 10-313)

**Model**: `CustomUser` (completely independent of Django's User model)

**Key Characteristics**:
- **Table Name**: `custom_users`
- **Primary Key**: `BigAutoField`
- **Core Fields**:
  - `username` (CharField, unique, indexed)
  - `email` (EmailField, unique, indexed)
  - `password_hash` (CharField, Argon2 hashed)
  - `first_name`, `last_name`
  - `phone_number`, `department`, `job_title`, `bio`

**Branch/School Assignment**:
- **Line 74-82**: `assigned_branch` ForeignKey to `cin7.Branch`
  ```python
  assigned_branch = models.ForeignKey(
      'cin7.Branch',
      on_delete=models.SET_NULL,
      null=True,
      blank=True,
      related_name='assigned_managers',
      help_text="Assigned branch/shop for store managers"
  )
  ```
- **NO `assigned_school` field** - Schools are represented via the `sub_category` field in Product model (see cin7/models.py Line 162)

**Roles & Permissions**:
- **Line 67-72**: ManyToMany relationship with `Role` model
  ```python
  roles = models.ManyToManyField(
      'Role',
      related_name='custom_users',
      blank=True,
      help_text="Roles assigned to this user"
  )
  ```

**Status & Security Fields**:
- `is_active` (Line 85-88): Requires email verification
- `is_staff` (Line 89-92): Admin interface access
- `is_superuser` (Line 93-96): All permissions
- `email_verified` (Line 97-100)
- `failed_login_attempts` (Line 103-106): Brute force protection
- `locked_until` (Line 107-111): Account lockout mechanism
- `last_login` (Line 112-116)
- `last_password_change` (Line 117-121)

**Key Methods**:
- **Line 159-168**: `set_password(raw_password)` - Argon2 hashing
- **Line 170-180**: `check_password(raw_password)` - Password verification
- **Line 182-199**: `has_permission(permission_key)` - Permission checking
- **Line 201-211**: `has_role(role_name)` - Role checking
- **Line 283-296**: `get_all_permissions()` - Get merged permissions from all roles

### 1.2 Settings Configuration
**File**: `/Users/sas/Repos/saspulse/saspulse/settings.py`

**Authentication Backend** (Lines 141-144):
```python
AUTHENTICATION_BACKENDS = [
    'users.auth_backend.CustomAuthBackend',
]
```

**Login Configuration** (Lines 153-154):
```python
LOGIN_URL = '/auth/login/'
LOGOUT_REDIRECT_URL = '/auth/login/'
```

**Password Policy** (Lines 157-161):
```python
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_LOWERCASE = True
PASSWORD_REQUIRE_NUMBERS = True
PASSWORD_REQUIRE_SPECIAL = True
```

**Account Security** (Lines 163-167):
```python
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION = 30  # minutes
ACTIVATION_TOKEN_EXPIRY = 24  # hours
RESET_TOKEN_EXPIRY = 1  # hour
```

**Password Hashing** (Lines 134-139):
```python
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]
```

### 1.3 Role Model
**File**: `/Users/sas/Repos/saspulse/users/models.py` (Lines 405-472)

**Model**: `Role`

```python
class Role(models.Model):
    name = CharField(unique=True)  # Unique role identifier
    description = TextField()      # Purpose/responsibilities
    permissions = JSONField()      # Flexible permission structure
    is_active = BooleanField()     # Can be deactivated
    created_at = DateTimeField()
    updated_at = DateTimeField()
```

**Methods**:
- **Line 438-448**: `get_permission(permission_key)` - Retrieve specific permission
- **Line 450-459**: `set_permission(permission_key, value)` - Set permission
- **Line 461-471**: `has_permission(permission_key)` - Check if permission exists and is True

**Note**: Permissions are stored as **JSON dictionaries** allowing flexible key-value pairs, not fixed Django permissions.

### 1.4 UserSession Model (Custom Session Management)
**File**: `/Users/sas/Repos/saspulse/users/models.py` (Lines 315-403)

**Model**: `UserSession`

```python
class UserSession(models.Model):
    session_key = CharField(primary_key=True)      # Unique session ID
    user = ForeignKey(CustomUser, on_delete=CASCADE)
    ip_address = GenericIPAddressField()           # Client IP
    user_agent = TextField()                       # Browser info
    created_at = DateTimeField()
    last_activity = DateTimeField()
    expires_at = DateTimeField()
    is_active = BooleanField()
    remember_me = BooleanField()                   # Extended session flag
```

**Methods**:
- **Line 378-385**: `is_expired()` - Check session expiry
- **Line 387-395**: `extend_expiry(hours=2)` - Slide expiration window
- **Line 397-402**: `deactivate()` - Logout session

---

## 2. EXISTING PERMISSION/AUTHORIZATION PATTERNS

### 2.1 Custom Decorators
**File**: `/Users/sas/Repos/saspulse/users/decorators.py`

**Available Decorators**:

1. **`@login_required(redirect_to='/auth/login/', raise_exception=False)`** (Lines 15-60)
   - Checks if user is authenticated
   - Redirect to login or return 403 based on `raise_exception` parameter
   - Usage:
     ```python
     @login_required()
     def my_view(request):
         ...
     ```

2. **`@permission_required(permission_key, raise_exception=True)`** (Lines 63-115)
   - Checks specific permission through roles
   - Calls `request.user.has_permission(permission_key)`
   - Usage:
     ```python
     @login_required()
     @permission_required('users.create')
     def create_user_view(request):
         ...
     ```

3. **`@role_required(role_name, raise_exception=True)`** (Lines 118-170)
   - Checks if user has specific role
   - Calls `request.user.has_role(role_name)`
   - Usage:
     ```python
     @login_required()
     @role_required('Admin')
     def admin_view(request):
         ...
     ```

4. **`@verified_email_required(redirect_to='/auth/verify-email/', raise_exception=False)`** (Lines 173-224)
   - Checks if `request.user.email_verified == True`
   - Usage:
     ```python
     @login_required()
     @verified_email_required()
     def sensitive_view(request):
         ...
     ```

5. **`@staff_required(raise_exception=True)`** (Lines 227-271)
   - Checks if `request.user.is_staff or request.user.is_superuser`

6. **`@superuser_required(raise_exception=True)`** (Lines 274-318)
   - Checks if `request.user.is_superuser`

7. **`@any_permission_required(*permission_keys, raise_exception=True)`** (Lines 321-370)
   - User needs ANY one of the specified permissions
   - Usage:
     ```python
     @any_permission_required('users.view', 'users.create', 'users.edit')
     def user_management(request):
         ...
     ```

8. **`@all_permissions_required(*permission_keys, raise_exception=True)`** (Lines 373-425)
   - User needs ALL specified permissions
   - Usage:
     ```python
     @all_permissions_required('users.view', 'users.create', 'users.edit')
     def full_user_management(request):
         ...
     ```

### 2.2 Dashboard Views - Permission Pattern
**File**: `/Users/sas/Repos/saspulse/dashboard/views.py`

**Current Usage Pattern**: All dashboard views use basic `@login_required` decorator

Examples:
- **Line ~2000**: `@login_required` on `forecasting_filter_options(request)`
- **Line ~2500**: `@login_required` on `sales_forecasting(request)`
- **Line ~2800**: `@login_required` on `store_manager_replenishment(request)`
  - This view also checks `assigned_branch` (Line ~3100):
    ```python
    assigned_branch = getattr(user, 'assigned_branch', None)
    if assigned_branch:
        assigned_branch_id = assigned_branch.id
    ```

**Manual Permission Checks in Views**:
- **Line ~3100-3120**: Store Manager Replenishment view filters data based on `assigned_branch`
  ```python
  if not is_admin and assigned_branch_id:
      params.append(assigned_branch_id)
  ```

- **Line ~6500**: Store Daily Pick List filters by `assigned_branch`:
  ```python
  assigned_branch = getattr(user, 'assigned_branch', None)
  if not is_admin and not assigned_branch:
      # Show error or restricted view
  if not is_admin and assigned_branch:
      # Filter by branch_name
  ```

### 2.3 Authentication Middleware
**File**: `/Users/sas/Repos/saspulse/users/middleware.py`

**1. AuthenticationMiddleware** (Lines 29-49)
   - Attaches user to request via `SimpleLazyObject`
   - Calls `auth_backend.get_user_from_session(request)`
   - Replaces Django's built-in AuthenticationMiddleware

**2. SessionSecurityMiddleware** (Lines 52-135)
   - Automatic session expiration checking (Line 93-95)
   - Optional IP verification (Line 98-103): `VERIFY_IP = False`
   - Optional User-Agent verification (Line 106-111): `VERIFY_USER_AGENT = False`
   - Deactivates hijacked sessions

**3. RequireAuthenticationMiddleware** (Lines 138-197)
   - Optional: Require authentication for all views except whitelisted
   - **NOT currently active** in settings.py
   - Can be enabled with `AUTHENTICATION_EXEMPT_URLS` configuration

### 2.4 Custom Authentication Backend
**File**: `/Users/sas/Repos/saspulse/users/auth_backend.py`

**Class**: `CustomAuthBackend`

**Key Methods**:

1. **`authenticate(request, username=None, password=None)`** (Lines 66-117)
   - Finds user by username OR email
   - Checks if account is locked
   - Verifies password
   - Increments failed login attempts and locks account after MAX_FAILED_ATTEMPTS (5)
   - Updates `last_login` timestamp on success
   - Returns CustomUser or None

2. **`login(request, user, remember_me=False)`** (Lines 119-164)
   - Generates secure session key using `secrets.token_urlsafe(30)`
   - Creates UserSession record with:
     - IP address
     - User-Agent
     - Expiration time (2 hours default, 30 days if remember_me)
   - Stores session_key in Django session
   - Returns session_key

3. **`logout(request)`** (Lines 166-189)
   - Deactivates UserSession
   - Flushes Django session

4. **`get_user_from_session(request)`** (Lines 191-243)
   - Retrieves UserSession from database
   - Checks expiration (auto-logout if expired)
   - Checks user is still active
   - **Implements sliding window**: Extends expiry on every request
     - Regular: 2 hours from now
     - Remember Me: 30 days from now
   - Updates last_activity timestamp
   - Returns CustomUser or AnonymousUser

5. **`is_authenticated(request)`** (Lines 245-256)
   - Checks if valid authenticated session exists

6. **`get_user(user_id)`** (Lines 275-289)
   - Gets user by ID for Django framework compatibility

**AnonymousUser Class** (Lines 16-46)
- Compatible with Django's auth system
- `is_authenticated = False`
- All permission methods return False

**Security Settings** (Lines 60-64):
```python
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30
SESSION_DURATION_HOURS = 2
REMEMBER_ME_DURATION_DAYS = 30
```

---

## 3. USER-TO-BRANCH ASSIGNMENT IMPLEMENTATION

### 3.1 Data Model
**CustomUser Model** (`users/models.py`, Lines 74-82):
```python
assigned_branch = models.ForeignKey(
    'cin7.Branch',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='assigned_managers',
    help_text="Assigned branch/shop for store managers"
)
```

**Branch Model** (`cin7/models.py`, Lines 75-100):
```python
class Branch(TimestampedModel):
    cin7_id = IntegerField(unique=True)
    name = CharField(max_length=255)
    code = CharField(max_length=50, unique=True)
    address, city, state, country, postal_code
    is_active = BooleanField(default=True)
```

### 3.2 Usage in Views
**Store Manager Replenishment** (`dashboard/views.py`):
```python
assigned_branch = getattr(user, 'assigned_branch', None)
if assigned_branch:
    assigned_branch_id = assigned_branch.id
```

**Store Daily Pick List** (`dashboard/views.py`):
```python
assigned_branch = getattr(user, 'assigned_branch', None)
if not is_admin and not assigned_branch:
    # User doesn't have a branch assigned
if not is_admin and assigned_branch:
    # Filter by branch_name
```

### 3.3 School Assignment
**NO direct `assigned_school` field** exists in CustomUser.

**Schools are represented via `sub_category`** in the Product model:
- Product `sub_category` field (Line 162 of cin7/models.py) contains school names
- Example: "Avondale High School", "St Mary's College", etc.
- Used in dashboard queries to aggregate by school

---

## 4. MENU RENDERING IN BASE.HTML

**File**: `/Users/sas/Repos/saspulse/templates/base.html` (6718 lines)

### 4.1 Current Menu Structure
**NO permission checking** is currently implemented in the menu.

**Hard-coded Menu Sections** (Lines 74-264):

1. **Dashboard Section** (Lines 80-163):
   - BTS Dashboard
   - BTS Sales Forecasting
   - BTS Sell-Through Ratio
   - Inventory Health Score
   - Inventory Alignment Matrix
   - Stocks (submenu with 5 items)

2. **Forecasts Section** (Lines 165-176):
   - Sales Forecasts

3. **Replenishment Section** (Lines 178-223):
   - Stores (Store Manager Review, My Requests, Daily Pick List)
   - Demand Planning (DP Team Approval, All Requests)

4. **Finance Section** (Lines 225-242):
   - Reports

5. **Admin Section** (Lines 244-263):
   - Users

**Key Finding**: 
- **NO conditional rendering** based on user permissions or roles
- **ALL menu items displayed** to all authenticated users
- **NO `{% if user.has_permission %}`** tags

### 4.2 Menu Implementation Details
```html
<!-- Vertical navbar menu (display:none) -->
<nav class="navbar navbar-vertical" style="display:none;">
    <!-- Navigation items are hard-coded with no permission checks -->
    <ul class="navbar-nav flex-column" id="navbarVerticalNav">
        <li class="nav-item">
            <a class="nav-link" href="/dashboard/">Dashboard</a>
        </li>
        <!-- More items without conditional logic -->
    </ul>
</nav>

<!-- Horizontal top navbar (display:none) -->
<nav class="navbar navbar-top fixed-top" id="navbarDefault" style="display:none;">
    <!-- Similar structure without permission checks -->
</nav>
```

**Both navbars have `style="display:none"`** - Suggesting menu is not currently used and user navigation is likely handled through:
- Breadcrumbs
- Direct URL navigation
- JavaScript-based routing

---

## 5. DATABASE MODELS RELATED TO USERS/PERMISSIONS

### 5.1 User Models
- **CustomUser** (`users/models.py`, Lines 10-313)
- **UserSession** (`users/models.py`, Lines 315-403)
- **Role** (`users/models.py`, Lines 405-472)

### 5.2 Branch/School Models
**Branch** (`cin7/models.py`, Lines 75-100):
- Represents warehouses/branches
- Related field: `CustomUser.assigned_branch`

**Product** (`cin7/models.py`, Lines 121-250):
- `category_name`: "% Shop" suffix indicates product category
- `sub_category`: School/branch name (primary grouping mechanism)

### 5.3 Sales Models
- **SalesOrder** (`cin7/models.py`, Lines 534-680)
- **SalesOrderLineItem** (`cin7/models.py`, Lines 690-755)

### 5.4 Admin Configuration
**File**: `/Users/sas/Repos/saspulse/users/admin.py`

**Registered Models**:
1. **CustomUserAdmin** (Lines 48-100)
   - Fields: username, email, roles, assigned_branch, is_active, is_staff, is_superuser
   - List display shows: username, email, first/last name, is_active, is_staff, email_verified, roles, last_login
   - **Notable**: No assignment interface visible for assigned_branch in fieldsets shown

2. **RoleAdmin** (Lines 8-46)
   - Fields: name, description, permissions (JSON), is_active
   - Shows user count for each role

3. **UserSessionAdmin** (Lines 102-133)
   - Tracks active sessions with IP, user_agent, expiry time

---

## 6. AUTHENTICATION FLOW SUMMARY

### 6.1 Login Flow
1. User submits login form with email and password
2. `CustomAuthBackend.authenticate(request, username=email, password=password)` called
3. Check: User locked? → Return None
4. Check: User active? → Return None  
5. Check: Password correct?
   - If NO: Increment failed_login_attempts, lock after 5 attempts, return None
   - If YES: Reset failed_login_attempts, update last_login, return CustomUser
6. `CustomAuthBackend.login(request, user, remember_me)` creates UserSession
7. Session key stored in Django session
8. Expiry set: 2 hours (regular) or 30 days (remember_me)

### 6.2 Request Cycle
1. **Middleware** (AuthenticationMiddleware) attaches user to request
2. `get_user_from_session(request)` called (lazy)
3. Check: Valid session_key in Django session?
4. Check: UserSession exists and is active?
5. Check: Session expired?
6. Check: User still active?
7. **Sliding window**: Extend expiry (2 hours from now for regular sessions)
8. Update last_activity
9. Return CustomUser or AnonymousUser

### 6.3 Permission Checking
1. Decorator or manual check: `request.user.has_permission('permission_key')`
2. CustomUser.has_permission() iterates through active roles
3. Role.has_permission() checks JSON permissions dictionary
4. Superusers always return True
5. Return permission value or False

### 6.4 Logout Flow
1. Get session_key from Django session
2. Find and deactivate UserSession
3. Flush Django session
4. Redirect to login

---

## 7. SECURITY FEATURES

### 7.1 Password Security
- **Hashing**: Argon2 (primary) with fallbacks to PBKDF2, BCrypt
- **Validation**: 8+ chars, uppercase, lowercase, numbers, special characters
- **Change tracking**: last_password_change timestamp

### 7.2 Account Lockout
- **Failed attempts**: 5 max failed login attempts
- **Lockout duration**: 30 minutes
- **Auto-unlock**: After timeout expires

### 7.3 Session Security
- **Expiration**: 2 hours (regular), 30 days (remember_me)
- **Sliding window**: Extends on every activity
- **Activity tracking**: last_activity timestamp
- **Client info**: IP address and user-agent stored
- **Session hijacking detection**: Can enable IP/User-Agent verification

### 7.4 Email Security
- **Activation tokens**: Secure token generation for email verification
- **Reset tokens**: Expire after 1 hour
- **Email verification**: Required for is_active flag

### 7.5 Django Security Settings (settings.py, Lines 300-310)
```python
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
```

---

## 8. CURRENT IMPLEMENTATION GAPS & ISSUES

### 8.1 Menu Permission Checking
- **Issue**: Menu in base.html has NO permission checking
- **Impact**: All authenticated users see all menu options regardless of role
- **Solution**: Add conditional rendering with permission checks

### 8.2 School Assignment
- **Issue**: No direct school assignment (unlike branches)
- **Current**: Schools represented via Product.sub_category
- **Implication**: Can't easily restrict users to specific schools/categories
- **Recommendation**: Consider adding `assigned_schools` M2M field to CustomUser

### 8.3 View-Level Permissions
- **Issue**: Most views only use @login_required
- **Current**: Permissions checked manually in views (e.g., assigned_branch checks)
- **Missing**: No @permission_required or @role_required decorators in practice
- **Solution**: Systematically apply permission decorators

### 8.4 Dashboard Configuration
- **Issue**: Views don't have permission decorators
- **Example**: All users can access all dashboard views
- **Solution**: Add @permission_required decorators or role checks

### 8.5 Admin Interface
- **Issue**: Django admin interface not fully secured with custom auth
- **Current**: Using both Django's default User model references (commented out) and CustomUser
- **Impact**: Potential confusion in user management

---

## 9. KEY SECURITY CONCLUSIONS

### Strengths:
1. **Complete custom authentication** - Full control over implementation
2. **Strong password hashing** - Argon2 with secure fallbacks
3. **Account lockout mechanism** - Brute force protection
4. **Session security** - Sliding window, expiration, activity tracking
5. **Flexible permissions** - JSON-based role permissions
6. **Email verification** - Required for activation
7. **Token-based recovery** - Secure password reset

### Weaknesses:
1. **No menu permission rendering** - All users see all options
2. **Minimal view-level enforcement** - Most views undecorated
3. **Manual permission checks** - Hard to audit and maintain
4. **No school assignment field** - Category-based school grouping
5. **Django default auth still referenced** - Code duplication and confusion

---

## 10. FILE LOCATION REFERENCE

All findings with absolute paths:
- `/Users/sas/Repos/saspulse/saspulse/settings.py` - Configuration
- `/Users/sas/Repos/saspulse/users/models.py` - CustomUser, Role, UserSession
- `/Users/sas/Repos/saspulse/users/auth_backend.py` - CustomAuthBackend
- `/Users/sas/Repos/saspulse/users/decorators.py` - Permission decorators
- `/Users/sas/Repos/saspulse/users/middleware.py` - Custom middleware
- `/Users/sas/Repos/saspulse/users/auth_views.py` - Auth view logic
- `/Users/sas/Repos/saspulse/users/views.py` - Role management views
- `/Users/sas/Repos/saspulse/users/admin.py` - Django admin configuration
- `/Users/sas/Repos/saspulse/dashboard/views.py` - Dashboard views with branch checks
- `/Users/sas/Repos/saspulse/dashboard/urls.py` - URL routing
- `/Users/sas/Repos/saspulse/templates/base.html` - Menu template
- `/Users/sas/Repos/saspulse/cin7/models.py` - Branch and Product models

