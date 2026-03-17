# Role-Based Access Control (RBAC) Implementation Plan
## SASPulse System Architecture

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Current System Analysis](#current-system-analysis)
3. [Requirements](#requirements)
4. [Architecture Design](#architecture-design)
5. [Database Schema Changes](#database-schema-changes)
6. [Permission Structure](#permission-structure)
7. [Implementation Phases](#implementation-phases)
8. [Data Isolation Strategy](#data-isolation-strategy)
9. [Menu & UI Access Control](#menu--ui-access-control)
10. [Security Considerations](#security-considerations)
11. [Testing Strategy](#testing-strategy)
12. [Migration & Rollout Plan](#migration--rollout-plan)

---

## Executive Summary

### Objective
Implement a comprehensive Role-Based Access Control (RBAC) system with data isolation for 4 user types:
- **Admins**: Full system access (excluding limitations)
- **Store Managers**: Replenishment section only, filtered by assigned branch(es)
- **Demand Planners**: Forecasts, Replenishment, Dashboard (no Admin section)
- **Sales Team**: Dashboard section only, filtered by assigned school(s)

### Current State
- ✅ Custom authentication system with `CustomUser` model
- ✅ Role model with flexible JSON permissions
- ✅ `assigned_branch` field for store managers
- ✅ Permission checking methods (`has_permission()`, `has_role()`)
- ❌ No `assigned_school` field for sales team
- ❌ Views only use `@login_required` (no granular permissions)
- ❌ No menu permission checking
- ❌ No standardized permission structure
- ❌ No data isolation filters in most views

---

## Current System Analysis

### Strengths
1. **Custom User Model** (`users/models.py:10-313`)
   - Complete control over authentication
   - ManyToMany relationship with Role model
   - Built-in permission checking: `user.has_permission(key)`
   - Argon2 password hashing
   - Account lockout mechanism

2. **Flexible Role Model** (`users/models.py:405-472`)
   - JSON-based permissions (flexible schema)
   - Methods: `get_permission()`, `set_permission()`, `has_permission()`
   - Can be activated/deactivated

3. **Custom Session Management** (`users/models.py:315-403`)
   - IP tracking, User-Agent logging
   - Remember me functionality
   - Sliding window expiration

4. **Security Decorators** (`users/decorators.py:15-425`)
   - `@login_required`
   - `@permission_required`
   - `@role_required`
   - `@email_verified_required`

### Gaps
1. **No School Assignment** - Sales team cannot be assigned to schools
2. **Inconsistent View Protection** - Most views only check login, not permissions
3. **No Menu Permission Logic** - All menu items visible to all logged-in users
4. **No Data Isolation** - Views don't filter by user's assigned branch/school
5. **No Standard Permission Keys** - JSON permissions are ad-hoc
6. **No Context Processor** - Templates can't easily check permissions

---

## Requirements

### 1. Admin Role
**Access Level**: Full system access
- ✅ Dashboard (all schools, all branches)
- ✅ Forecasting (all data)
- ✅ Replenishment (all stores, all requests)
- ✅ Admin section (user management, system settings)

**Data Scope**: ALL data (no filtering)

**Menu Items**:
- Dashboard
- Forecasting
- Replenishment (all sub-items)
- Admin/Settings

### 2. Store Manager Role
**Access Level**: Replenishment section ONLY
- ❌ Dashboard (no access)
- ❌ Forecasting (no access)
- ✅ Replenishment > Stores (filtered by assigned branch)
  - Store Manager Review
  - My Requests
  - Daily Pick List
- ❌ Replenishment > Demand Planning (no access)
- ❌ Admin section (no access)

**Data Scope**: ONLY assigned branch(es)
- Can be assigned to **one or more branches**
- See only replenishment requests for their branch(es)
- See only stock data for their branch(es)

**Menu Items**:
- Replenishment > Stores (only)
  - Store Manager Review
  - My Requests
  - Daily Pick List

### 3. Demand Planner Role
**Access Level**: Dashboard, Forecasting, Replenishment (like Admin but no Admin section)
- ✅ Dashboard (all schools, all branches)
- ✅ Forecasting (all data)
- ✅ Replenishment (all stores, all requests)
  - Stores section (view all)
  - Demand Planning section (approve/manage)
- ❌ Admin section (no access)

**Data Scope**: ALL data (no filtering)

**Menu Items**:
- Dashboard
- Forecasting
- Replenishment (all sub-items)

### 4. Sales Team Role
**Access Level**: Dashboard section ONLY
- ✅ Dashboard (filtered by assigned school(s))
- ❌ Forecasting (no access)
- ❌ Replenishment (no access)
- ❌ Admin section (no access)

**Data Scope**: ONLY assigned school(s)
- Can be assigned to **one or more schools**
- See only sales data for their school(s)
- School is represented by Product `sub_category` field

**Menu Items**:
- Dashboard (only)

---

## Architecture Design

### Design Principles
1. **Defense in Depth**: Multiple layers of security (view decorators, template checks, data filters)
2. **Fail-Safe Defaults**: Deny access unless explicitly granted
3. **Least Privilege**: Users get minimum permissions needed for their role
4. **Separation of Concerns**: Authorization logic separated from business logic
5. **DRY Principle**: Reusable permission checking utilities

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Request                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               Middleware Layer                               │
│  - AuthenticationMiddleware (existing)                       │
│  - PermissionCheckMiddleware (NEW)                          │
│  - SessionMiddleware                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  View Layer                                  │
│  - @role_required('store_manager') (NEW usage)              │
│  - @permission_required('replenishment.view') (NEW usage)   │
│  - Data isolation filters (NEW)                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               Template Layer                                 │
│  - Context processor injects permissions (NEW)               │
│  - {% if has_perm 'dashboard.view' %} (NEW template tag)    │
│  - Menu items conditionally rendered (NEW)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema Changes

### 1. Add School Assignment to CustomUser

**File**: `users/models.py` (add after `assigned_branch` field)

```python
# School Assignment (for sales team)
assigned_schools = models.ManyToManyField(
    'cin7.Product',
    related_name='assigned_sales_users',
    blank=True,
    limit_choices_to={'sub_category__isnull': False},
    help_text="Assigned schools for sales team (via Product sub_category)"
)
```

**Why ManyToMany?**
- Sales team can be assigned to **multiple schools**
- Store managers can be assigned to **multiple branches** (need to change ForeignKey to ManyToMany)

### 2. Change assigned_branch to ManyToMany

**Current** (`users/models.py:74-82`):
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

**New** (change to ManyToMany):
```python
assigned_branches = models.ManyToManyField(
    'cin7.Branch',
    related_name='assigned_managers',
    blank=True,
    help_text="Assigned branches/shops for store managers (can have multiple)"
)
```

**Migration Impact**:
- Need data migration to move existing `assigned_branch` to `assigned_branches`
- Update all views using `assigned_branch` to `assigned_branches`

### 3. Create School Helper Model (OPTIONAL)

**Alternative approach**: Create a dedicated School model instead of relying on Product `sub_category`

```python
class School(models.Model):
    """
    School/Campus entity for sales team assignment
    """
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)

    # Link to Product sub_category for data filtering
    sub_category_value = models.CharField(max_length=250, unique=True)

    class Meta:
        ordering = ['name']
```

**Benefits**:
- Clean separation of concerns
- Easier to manage school list
- Can add school-specific metadata (address, contact, etc.)

**Recommendation**: Start simple with Product `sub_category`, add School model later if needed

---

## Permission Structure

### Standardized Permission Keys

Define a standard JSON structure for the Role `permissions` field:

```json
{
  "dashboard": {
    "view": true,
    "export": true
  },
  "forecasting": {
    "view": true,
    "edit": false,
    "export": true
  },
  "replenishment": {
    "stores": {
      "view": true,
      "review": true,
      "create_request": true,
      "edit_request": true,
      "submit_request": true
    },
    "demand_planning": {
      "view": true,
      "approve": true,
      "reject": true,
      "view_all_requests": true
    },
    "daily_pick_list": {
      "view": true,
      "export": true
    }
  },
  "admin": {
    "users": {
      "view": true,
      "create": true,
      "edit": true,
      "delete": true
    },
    "roles": {
      "view": true,
      "create": true,
      "edit": true,
      "delete": true
    },
    "settings": {
      "view": true,
      "edit": true
    }
  },
  "data_scope": {
    "type": "all",  // Options: "all", "branch", "school"
    "filter_required": false
  }
}
```

### Permission Hierarchy

```
dashboard
  ├── view
  └── export

forecasting
  ├── view
  ├── edit
  └── export

replenishment
  ├── stores
  │   ├── view
  │   ├── review
  │   ├── create_request
  │   ├── edit_request
  │   └── submit_request
  ├── demand_planning
  │   ├── view
  │   ├── approve
  │   ├── reject
  │   └── view_all_requests
  └── daily_pick_list
      ├── view
      └── export

admin
  ├── users (view, create, edit, delete)
  ├── roles (view, create, edit, delete)
  └── settings (view, edit)
```

### Role Permission Templates

#### 1. Admin Role Permissions
```json
{
  "dashboard": {"view": true, "export": true},
  "forecasting": {"view": true, "edit": true, "export": true},
  "replenishment": {
    "stores": {"view": true, "review": true, "create_request": true, "edit_request": true, "submit_request": true},
    "demand_planning": {"view": true, "approve": true, "reject": true, "view_all_requests": true},
    "daily_pick_list": {"view": true, "export": true}
  },
  "admin": {
    "users": {"view": true, "create": true, "edit": true, "delete": true},
    "roles": {"view": true, "create": true, "edit": true, "delete": true},
    "settings": {"view": true, "edit": true}
  },
  "data_scope": {"type": "all", "filter_required": false}
}
```

#### 2. Store Manager Role Permissions
```json
{
  "dashboard": {"view": false, "export": false},
  "forecasting": {"view": false, "edit": false, "export": false},
  "replenishment": {
    "stores": {"view": true, "review": true, "create_request": true, "edit_request": true, "submit_request": true},
    "demand_planning": {"view": false, "approve": false, "reject": false, "view_all_requests": false},
    "daily_pick_list": {"view": true, "export": true}
  },
  "admin": {
    "users": {"view": false, "create": false, "edit": false, "delete": false},
    "roles": {"view": false, "create": false, "edit": false, "delete": false},
    "settings": {"view": false, "edit": false}
  },
  "data_scope": {"type": "branch", "filter_required": true}
}
```

#### 3. Demand Planner Role Permissions
```json
{
  "dashboard": {"view": true, "export": true},
  "forecasting": {"view": true, "edit": true, "export": true},
  "replenishment": {
    "stores": {"view": true, "review": true, "create_request": false, "edit_request": false, "submit_request": false},
    "demand_planning": {"view": true, "approve": true, "reject": true, "view_all_requests": true},
    "daily_pick_list": {"view": true, "export": true}
  },
  "admin": {
    "users": {"view": false, "create": false, "edit": false, "delete": false},
    "roles": {"view": false, "create": false, "edit": false, "delete": false},
    "settings": {"view": false, "edit": false}
  },
  "data_scope": {"type": "all", "filter_required": false}
}
```

#### 4. Sales Team Role Permissions
```json
{
  "dashboard": {"view": true, "export": true},
  "forecasting": {"view": false, "edit": false, "export": false},
  "replenishment": {
    "stores": {"view": false, "review": false, "create_request": false, "edit_request": false, "submit_request": false},
    "demand_planning": {"view": false, "approve": false, "reject": false, "view_all_requests": false},
    "daily_pick_list": {"view": false, "export": false}
  },
  "admin": {
    "users": {"view": false, "create": false, "edit": false, "delete": false},
    "roles": {"view": false, "create": false, "edit": false, "delete": false},
    "settings": {"view": false, "edit": false}
  },
  "data_scope": {"type": "school", "filter_required": true}
}
```

### Helper Methods for Permission Checking

**File**: `users/models.py` (add to CustomUser model)

```python
def has_nested_permission(self, permission_path):
    """
    Check nested permission using dot notation.

    Examples:
        user.has_nested_permission('dashboard.view')
        user.has_nested_permission('replenishment.stores.review')
        user.has_nested_permission('admin.users.create')

    Args:
        permission_path (str): Dot-separated permission path

    Returns:
        bool: True if user has the permission
    """
    if self.is_superuser:
        return True

    for role in self.roles.filter(is_active=True):
        keys = permission_path.split('.')
        value = role.permissions

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                break
        else:
            if value is True:
                return True

    return False

def get_data_scope(self):
    """
    Get user's data scope (all, branch, school).

    Returns:
        str: 'all', 'branch', or 'school'
    """
    if self.is_superuser:
        return 'all'

    for role in self.roles.filter(is_active=True):
        scope_type = role.permissions.get('data_scope', {}).get('type')
        if scope_type:
            return scope_type

    return 'all'  # Default to no restrictions

def requires_data_filter(self):
    """
    Check if user requires data filtering.

    Returns:
        bool: True if user needs data filtered by branch/school
    """
    scope = self.get_data_scope()
    return scope in ['branch', 'school']
```

---

## Implementation Phases

### Phase 1: Database & Model Updates (Week 1)

#### Tasks:
1. ✅ Add `assigned_schools` ManyToMany field to CustomUser
2. ✅ Change `assigned_branch` to `assigned_branches` ManyToMany
3. ✅ Create data migration to move existing branch assignments
4. ✅ Add helper methods: `has_nested_permission()`, `get_data_scope()`, `requires_data_filter()`
5. ✅ Create management command to seed 4 standard roles

**Files to Modify**:
- `users/models.py`
- `users/management/commands/seed_roles.py` (NEW)
- `users/migrations/000X_add_school_assignment.py` (NEW)

**Testing**:
- Unit tests for new helper methods
- Verify migration doesn't lose data
- Test role seeding command

---

### Phase 2: View Protection (Week 2)

#### Tasks:
1. ✅ Audit all dashboard views and categorize by required permission
2. ✅ Add permission decorators to all views
3. ✅ Implement data isolation filters (branch/school)
4. ✅ Create reusable filter utilities

**Files to Modify**:
- `dashboard/views.py` (~6000+ lines, ~50+ views)
- `dashboard/utils/permissions.py` (NEW)

**View Categorization**:

| View Function | Required Permission | Data Scope Filter |
|--------------|---------------------|-------------------|
| `dashboard` | `dashboard.view` | school (sales), none (others) |
| `sales_forecasting` | `forecasting.view` | school (sales), none (others) |
| `forecast_product_breakdown` | `forecasting.view` | school (sales), none (others) |
| `store_manager_review` | `replenishment.stores.review` | branch (store mgr) |
| `store_daily_pick_list` | `replenishment.daily_pick_list.view` | branch (store mgr) |
| `dp_replenishment_approval` | `replenishment.demand_planning.approve` | none |
| `dp_replenishment_requests_list` | `replenishment.demand_planning.view_all_requests` | none |

**Example Decorator Usage**:
```python
from users.decorators import permission_required
from dashboard.utils.permissions import apply_data_scope

@login_required
@permission_required('dashboard.view')
def dashboard(request):
    # Apply data scope filtering
    queryset = SalesOrderLineItem.objects.all()
    queryset = apply_data_scope(request.user, queryset, scope_field='product__sub_category')

    # Rest of view logic...
```

---

### Phase 3: Template & Menu Updates (Week 3)

#### Tasks:
1. ✅ Create context processor to inject permissions
2. ✅ Create custom template tags for permission checking
3. ✅ Update `base.html` menu with conditional rendering
4. ✅ Add permission checks to all sensitive UI elements

**Files to Modify**:
- `dashboard/context_processors.py` (NEW)
- `dashboard/templatetags/permission_tags.py` (NEW)
- `templates/base.html` (Lines 74-264)
- `saspulse/settings.py` (add context processor)

**Context Processor** (`dashboard/context_processors.py`):
```python
def user_permissions(request):
    """
    Add user permissions to template context.
    """
    if request.user.is_authenticated:
        return {
            'user_permissions': request.user.get_all_permissions(),
            'user_roles': list(request.user.roles.filter(is_active=True).values_list('name', flat=True)),
            'user_data_scope': request.user.get_data_scope(),
        }
    return {}
```

**Template Tag** (`dashboard/templatetags/permission_tags.py`):
```python
from django import template

register = template.Library()

@register.filter(name='has_perm')
def has_perm(user, permission_path):
    """
    Check if user has a specific permission.

    Usage in template:
        {% if request.user|has_perm:'dashboard.view' %}
        {% if request.user|has_perm:'replenishment.stores.review' %}
    """
    if not user.is_authenticated:
        return False
    return user.has_nested_permission(permission_path)

@register.simple_tag
def can_view_menu(user, menu_section):
    """
    Check if user can view a menu section.

    Usage:
        {% can_view_menu request.user 'dashboard' as can_view_dashboard %}
        {% if can_view_dashboard %}
    """
    permission_map = {
        'dashboard': 'dashboard.view',
        'forecasting': 'forecasting.view',
        'replenishment_stores': 'replenishment.stores.view',
        'replenishment_dp': 'replenishment.demand_planning.view',
        'admin': 'admin.users.view',
    }

    required_perm = permission_map.get(menu_section)
    if not required_perm:
        return False

    return user.has_nested_permission(required_perm)
```

**Menu Update** (`templates/base.html`):
```html
{% load permission_tags %}

<!-- Dashboard Menu Item -->
{% if request.user|has_perm:'dashboard.view' %}
<li class="nav-item">
    <a class="nav-link" href="{% url 'dashboard:dashboard' %}">
        <i data-feather="bar-chart-2"></i> Dashboard
    </a>
</li>
{% endif %}

<!-- Forecasting Menu Item -->
{% if request.user|has_perm:'forecasting.view' %}
<li class="nav-item">
    <a class="nav-link" href="{% url 'dashboard:sales_forecasting' %}">
        <i data-feather="trending-up"></i> Forecasting
    </a>
</li>
{% endif %}

<!-- Replenishment Menu (Collapsible) -->
{% if request.user|has_perm:'replenishment.stores.view' or request.user|has_perm:'replenishment.demand_planning.view' %}
<li class="nav-item">
    <a class="nav-link" data-bs-toggle="collapse" href="#replenishmentSubmenu">
        <i data-feather="package"></i> Replenishment
    </a>
    <div class="collapse" id="replenishmentSubmenu">
        <ul class="nav flex-column ms-3">
            <!-- Stores Submenu -->
            {% if request.user|has_perm:'replenishment.stores.view' %}
            <li class="nav-item">
                <a class="nav-link" data-bs-toggle="collapse" href="#storesSubmenu">
                    <i data-feather="shopping-bag"></i> Stores
                </a>
                <div class="collapse" id="storesSubmenu">
                    <ul class="nav flex-column ms-3">
                        {% if request.user|has_perm:'replenishment.stores.review' %}
                        <li class="nav-item">
                            <a class="nav-link" href="{% url 'dashboard:store_replenishment_review' %}">
                                Store Manager Review
                            </a>
                        </li>
                        {% endif %}
                        <!-- More store menu items... -->
                    </ul>
                </div>
            </li>
            {% endif %}

            <!-- Demand Planning Submenu -->
            {% if request.user|has_perm:'replenishment.demand_planning.view' %}
            <li class="nav-item">
                <a class="nav-link" data-bs-toggle="collapse" href="#dpSubmenu">
                    <i data-feather="trending-up"></i> Demand Planning
                </a>
                <div class="collapse" id="dpSubmenu">
                    <ul class="nav flex-column ms-3">
                        {% if request.user|has_perm:'replenishment.demand_planning.approve' %}
                        <li class="nav-item">
                            <a class="nav-link" href="{% url 'dashboard:dp_replenishment_approval' %}">
                                DP Team Approval
                            </a>
                        </li>
                        {% endif %}
                        <!-- More DP menu items... -->
                    </ul>
                </div>
            </li>
            {% endif %}
        </ul>
    </div>
</li>
{% endif %}

<!-- Admin Menu Item -->
{% if request.user|has_perm:'admin.users.view' %}
<li class="nav-item">
    <a class="nav-link" href="/admin/">
        <i data-feather="settings"></i> Admin
    </a>
</li>
{% endif %}
```

---

### Phase 4: Middleware & Error Handling (Week 3)

#### Tasks:
1. ✅ Create permission checking middleware
2. ✅ Create 403 Forbidden template
3. ✅ Add logging for unauthorized access attempts
4. ✅ Test error handling

**Files to Create**:
- `users/middleware.py` (NEW)
- `templates/403.html` (NEW)

**Middleware** (`users/middleware.py`):
```python
import logging
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.urls import resolve

logger = logging.getLogger(__name__)

class PermissionCheckMiddleware:
    """
    Middleware to check permissions for sensitive URLs.
    Logs unauthorized access attempts.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Log 403 responses
        if response.status_code == 403 and request.user.is_authenticated:
            logger.warning(
                f"Unauthorized access attempt: user={request.user.username}, "
                f"path={request.path}, ip={request.META.get('REMOTE_ADDR')}"
            )

        return response
```

**403 Template** (`templates/403.html`):
```html
{% extends "base.html" %}

{% block content %}
<div class="container mt-5">
    <div class="row justify-content-center">
        <div class="col-md-6 text-center">
            <i data-feather="alert-triangle" style="width: 64px; height: 64px; color: #dc3545;"></i>
            <h1 class="mt-3">Access Denied</h1>
            <p class="text-muted">
                You do not have permission to access this page.
            </p>
            <p class="text-muted">
                If you believe this is an error, please contact your administrator.
            </p>
            <a href="{% url 'dashboard:dashboard' %}" class="btn btn-primary mt-3">
                Return to Dashboard
            </a>
        </div>
    </div>
</div>
{% endblock %}
```

---

### Phase 5: Testing & Documentation (Week 4)

#### Tasks:
1. ✅ Create test users for each role
2. ✅ Test all views with each role type
3. ✅ Test data isolation (branch/school filtering)
4. ✅ Test menu rendering for each role
5. ✅ Create admin guide for managing users/roles
6. ✅ Create developer documentation

**Testing Checklist**:
- [ ] Admin can access all sections
- [ ] Store Manager can only access Replenishment > Stores
- [ ] Store Manager sees only their branch(es) data
- [ ] Demand Planner can access Dashboard, Forecasting, Replenishment
- [ ] Demand Planner cannot access Admin section
- [ ] Sales Team can only access Dashboard
- [ ] Sales Team sees only their school(s) data
- [ ] Unauthorized access returns 403
- [ ] Menu items hidden based on permissions

---

## Data Isolation Strategy

### Branch-Based Filtering (Store Managers)

**Affected Models**:
- `ReplenishmentRequest` (has `branch` field)
- `Stock` (has `branch_name` field)
- `SalesOrderLineItem` (indirect via branch)

**Filter Implementation**:
```python
def apply_branch_filter(user, queryset, branch_field='branch'):
    """
    Filter queryset by user's assigned branches.

    Args:
        user: CustomUser instance
        queryset: Django QuerySet
        branch_field: Name of branch field (default: 'branch')

    Returns:
        Filtered QuerySet
    """
    if user.is_superuser or user.get_data_scope() == 'all':
        return queryset

    if user.get_data_scope() == 'branch':
        user_branches = user.assigned_branches.all()
        if not user_branches.exists():
            # User has branch scope but no branches assigned - return empty
            return queryset.none()

        # Filter by assigned branches
        filter_kwargs = {f'{branch_field}__in': user_branches}
        return queryset.filter(**filter_kwargs)

    return queryset
```

**Usage Example**:
```python
@login_required
@permission_required('replenishment.stores.view')
def store_replenishment_review(request):
    # Get all requests
    requests = ReplenishmentRequest.objects.all()

    # Apply branch filter
    requests = apply_branch_filter(request.user, requests, branch_field='branch')

    # Rest of view logic...
```

### School-Based Filtering (Sales Team)

**Affected Models**:
- `SalesOrderLineItem` (via `product__sub_category`)
- `Product` (has `sub_category` field)
- `SalesForecastBase` (indirect via product)

**Filter Implementation**:
```python
def apply_school_filter(user, queryset, school_field='product__sub_category'):
    """
    Filter queryset by user's assigned schools.

    Args:
        user: CustomUser instance
        queryset: Django QuerySet
        school_field: Path to school field (default: 'product__sub_category')

    Returns:
        Filtered QuerySet
    """
    if user.is_superuser or user.get_data_scope() == 'all':
        return queryset

    if user.get_data_scope() == 'school':
        # Get school sub_category values from assigned schools (Product.sub_category)
        user_school_values = user.assigned_schools.values_list('sub_category', flat=True)

        if not user_school_values:
            # User has school scope but no schools assigned - return empty
            return queryset.none()

        # Filter by school sub_category values
        filter_kwargs = {f'{school_field}__in': user_school_values}
        return queryset.filter(**filter_kwargs)

    return queryset
```

**Usage Example**:
```python
@login_required
@permission_required('dashboard.view')
def dashboard(request):
    # Get sales data
    sales = SalesOrderLineItem.objects.filter(
        sales_order__invoice_date__isnull=False
    )

    # Apply school filter
    sales = apply_school_filter(request.user, sales, school_field='product__sub_category')

    # Rest of view logic...
```

### Utility Module

**File**: `dashboard/utils/permissions.py` (NEW)

```python
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import render

def apply_data_scope(user, queryset, scope_field=None):
    """
    Automatically apply data scope filtering based on user's role.

    Args:
        user: CustomUser instance
        queryset: Django QuerySet
        scope_field: Optional field path for filtering

    Returns:
        Filtered QuerySet
    """
    scope = user.get_data_scope()

    if scope == 'all' or user.is_superuser:
        return queryset

    if scope == 'branch':
        # Default branch field names to try
        branch_fields = ['branch', 'assigned_branch', 'branch_name']

        if scope_field and 'branch' in scope_field:
            return apply_branch_filter(user, queryset, branch_field=scope_field)

        # Try common branch field names
        for field in branch_fields:
            try:
                return apply_branch_filter(user, queryset, branch_field=field)
            except:
                continue

        # No valid branch field found
        return queryset.none()

    if scope == 'school':
        # Default school field path
        school_field = scope_field or 'product__sub_category'
        return apply_school_filter(user, queryset, school_field=school_field)

    return queryset

def apply_branch_filter(user, queryset, branch_field='branch'):
    """Filter by assigned branches (see implementation above)"""
    # ... (implementation from above)

def apply_school_filter(user, queryset, school_field='product__sub_category'):
    """Filter by assigned schools (see implementation above)"""
    # ... (implementation from above)
```

---

## Menu & UI Access Control

### Menu Structure by Role

#### Admin Menu
```
- Dashboard
- Forecasting
- Replenishment
  ├── Stores
  │   ├── Store Manager Review
  │   ├── My Requests
  │   └── Daily Pick List
  └── Demand Planning
      ├── DP Team Approval
      └── All Requests
- Admin/Settings
```

#### Store Manager Menu
```
- Replenishment
  └── Stores
      ├── Store Manager Review
      ├── My Requests
      └── Daily Pick List
```

#### Demand Planner Menu
```
- Dashboard
- Forecasting
- Replenishment
  ├── Stores
  │   ├── Store Manager Review
  │   ├── My Requests
  │   └── Daily Pick List
  └── Demand Planning
      ├── DP Team Approval
      └── All Requests
```

#### Sales Team Menu
```
- Dashboard
```

### Landing Page by Role

**File**: `dashboard/views.py` (update redirect logic)

```python
def get_user_landing_page(user):
    """
    Get the appropriate landing page URL for a user based on their role.

    Returns:
        str: URL path for user's landing page
    """
    if user.is_superuser:
        return '/dashboard/'

    # Check permissions in priority order
    if user.has_nested_permission('dashboard.view'):
        return '/dashboard/'
    elif user.has_nested_permission('forecasting.view'):
        return '/dashboard/forecasting/'
    elif user.has_nested_permission('replenishment.stores.view'):
        return '/dashboard/replenishment/store/'
    elif user.has_nested_permission('admin.users.view'):
        return '/admin/'
    else:
        # No permissions - redirect to login
        return '/auth/login/'
```

**Update login redirect** (`users/views.py`):
```python
from dashboard.views import get_user_landing_page

def login_view(request):
    # ... authentication logic ...

    if user.is_authenticated:
        # Redirect to appropriate landing page
        landing_url = get_user_landing_page(user)
        return redirect(landing_url)
```

---

## Security Considerations

### 1. Defense in Depth
- **Layer 1**: URL-level protection (decorators on views)
- **Layer 2**: Template-level protection (hide unauthorized UI elements)
- **Layer 3**: Data-level protection (filter queries by scope)
- **Layer 4**: Logging & monitoring (track unauthorized attempts)

### 2. Fail-Safe Defaults
- Default permission: **DENY** (explicitly grant access)
- Empty assigned_branches/assigned_schools: Return **empty queryset**
- Unknown permission key: Return **False**
- Missing role: No permissions

### 3. SQL Injection Prevention
- Use Django ORM (parameterized queries)
- Never construct raw SQL with user input
- Use `.filter()` with keyword arguments

### 4. Privilege Escalation Prevention
- Don't allow users to edit their own roles
- Role assignment only via admin interface
- Superuser flag only settable by existing superusers
- Log all role/permission changes

### 5. Session Security
- Existing session management already robust
- Consider adding: Re-authenticate for sensitive actions
- Consider adding: Session invalidation on role change

### 6. Audit Trail
- Log all permission checks (optional, performance impact)
- Log unauthorized access attempts (✅ in middleware)
- Log role/permission modifications
- Log data exports (especially for restricted users)

---

## Testing Strategy

### Unit Tests

**File**: `users/tests/test_permissions.py` (NEW)

```python
from django.test import TestCase
from users.models import CustomUser, Role
from cin7.models import Branch, Product

class RBACTestCase(TestCase):
    def setUp(self):
        # Create test roles
        self.admin_role = Role.objects.create(
            name='Admin',
            permissions={...}  # Full permissions
        )
        self.store_mgr_role = Role.objects.create(
            name='Store Manager',
            permissions={...}  # Limited permissions
        )

        # Create test users
        self.admin = CustomUser.objects.create(
            username='admin',
            is_superuser=True
        )
        self.store_mgr = CustomUser.objects.create(
            username='store_mgr'
        )
        self.store_mgr.roles.add(self.store_mgr_role)

        # Create test branch
        self.branch = Branch.objects.create(name='Test Store')
        self.store_mgr.assigned_branches.add(self.branch)

    def test_admin_has_all_permissions(self):
        self.assertTrue(self.admin.has_nested_permission('dashboard.view'))
        self.assertTrue(self.admin.has_nested_permission('admin.users.delete'))

    def test_store_manager_has_limited_permissions(self):
        self.assertTrue(self.store_mgr.has_nested_permission('replenishment.stores.view'))
        self.assertFalse(self.store_mgr.has_nested_permission('dashboard.view'))
        self.assertFalse(self.store_mgr.has_nested_permission('admin.users.view'))

    def test_data_scope_filtering(self):
        scope = self.store_mgr.get_data_scope()
        self.assertEqual(scope, 'branch')

        scope = self.admin.get_data_scope()
        self.assertEqual(scope, 'all')

    def test_branch_filtering(self):
        from dashboard.utils.permissions import apply_branch_filter

        # Create another branch
        other_branch = Branch.objects.create(name='Other Store')

        # Create requests for both branches
        req1 = ReplenishmentRequest.objects.create(branch=self.branch)
        req2 = ReplenishmentRequest.objects.create(branch=other_branch)

        # Store manager should only see their branch
        qs = ReplenishmentRequest.objects.all()
        filtered = apply_branch_filter(self.store_mgr, qs)

        self.assertEqual(filtered.count(), 1)
        self.assertIn(req1, filtered)
        self.assertNotIn(req2, filtered)

        # Admin should see all
        filtered_admin = apply_branch_filter(self.admin, qs)
        self.assertEqual(filtered_admin.count(), 2)
```

### Integration Tests

**File**: `dashboard/tests/test_views_permissions.py` (NEW)

```python
from django.test import TestCase, Client
from django.urls import reverse
from users.models import CustomUser, Role

class ViewPermissionTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Create store manager
        self.store_mgr_role = Role.objects.create(
            name='Store Manager',
            permissions={
                'replenishment': {
                    'stores': {'view': True, 'review': True}
                }
            }
        )
        self.store_mgr = CustomUser.objects.create(username='store_mgr')
        self.store_mgr.set_password('password123')
        self.store_mgr.roles.add(self.store_mgr_role)
        self.store_mgr.save()

    def test_store_manager_cannot_access_dashboard(self):
        self.client.login(username='store_mgr', password='password123')

        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_store_manager_can_access_replenishment(self):
        self.client.login(username='store_mgr', password='password123')

        response = self.client.get(reverse('dashboard:store_replenishment_review'))
        self.assertEqual(response.status_code, 200)  # OK
```

### Manual Testing Checklist

**Test Users to Create**:
1. `admin_user` - Admin role
2. `store_mgr_avondale` - Store Manager, Avondale branch
3. `store_mgr_multi` - Store Manager, multiple branches
4. `demand_planner` - Demand Planner role
5. `sales_kbhs` - Sales Team, KBHS school
6. `sales_multi` - Sales Team, multiple schools

**Test Scenarios**:
- [ ] Login as each user type
- [ ] Verify correct landing page
- [ ] Verify menu items match role
- [ ] Try accessing unauthorized URLs directly (should get 403)
- [ ] Verify data filtering (store managers see only their branch)
- [ ] Verify data filtering (sales team see only their schools)
- [ ] Test approve/reject functionality for appropriate roles
- [ ] Test export functionality
- [ ] Verify admin can manage users/roles

---

## Migration & Rollout Plan

### Pre-Deployment

#### 1. Database Backup
```bash
# Backup production database
mysqldump -u root -p db_dataSync > backup_before_rbac_$(date +%Y%m%d).sql
```

#### 2. Create Roles
```bash
python manage.py seed_roles
```

This creates 4 standard roles:
- Admin
- Store Manager
- Demand Planner
- Sales Team

#### 3. Assign Users to Roles

**Option A: Via Django Admin**
- Go to `/admin/users/customuser/`
- Edit each user
- Select appropriate role(s)
- Assign branches (for store managers)
- Assign schools (for sales team)

**Option B: Via Management Command** (NEW)
```bash
python manage.py assign_user_role <username> <role_name>
python manage.py assign_user_branches <username> <branch1> <branch2> ...
python manage.py assign_user_schools <username> <school1> <school2> ...
```

### Deployment Steps

#### 1. Deploy Code
```bash
git pull origin main
```

#### 2. Run Migrations
```bash
python manage.py migrate
```

#### 3. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

#### 4. Seed Roles
```bash
python manage.py seed_roles
```

#### 5. Restart Application
```bash
# Restart Gunicorn/uWSGI
sudo systemctl restart gunicorn
```

#### 6. Clear Cache
```bash
python manage.py clear_cache
# or via Django shell
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
```

### Post-Deployment Verification

#### 1. Smoke Tests
- [ ] Admin login works
- [ ] Store manager login works
- [ ] Demand planner login works
- [ ] Sales team login works

#### 2. Permission Tests
- [ ] Store manager cannot access dashboard
- [ ] Sales team cannot access forecasting
- [ ] Demand planner cannot access admin

#### 3. Data Isolation Tests
- [ ] Store manager sees only their branch data
- [ ] Sales team sees only their school data

#### 4. Monitor Logs
```bash
tail -f /var/log/saspulse/app.log | grep "Unauthorized"
```

### Rollback Plan

If critical issues are found:

#### 1. Restore Database Backup
```bash
mysql -u root -p db_dataSync < backup_before_rbac_YYYYMMDD.sql
```

#### 2. Revert Code
```bash
git revert <commit_hash>
git push origin main
```

#### 3. Restart Application
```bash
sudo systemctl restart gunicorn
```

---

## Development Timeline

### Week 1: Foundation
- [ ] Day 1-2: Database schema changes, migrations
- [ ] Day 3-4: Helper methods, permission structure
- [ ] Day 5: Role seeding command, testing

### Week 2: Views
- [ ] Day 1-2: Audit views, add decorators
- [ ] Day 3-4: Data isolation filters
- [ ] Day 5: View testing

### Week 3: UI
- [ ] Day 1-2: Context processors, template tags
- [ ] Day 3-4: Menu updates, 403 template
- [ ] Day 5: UI testing

### Week 4: Testing & Docs
- [ ] Day 1-2: Integration tests
- [ ] Day 3: Manual testing
- [ ] Day 4: Documentation
- [ ] Day 5: Deployment preparation

**Total Estimated Effort**: 4 weeks (1 developer)

---

## Success Criteria

### Functional Requirements
- ✅ 4 role types implemented and working
- ✅ Users can be assigned to roles
- ✅ Store managers can be assigned to multiple branches
- ✅ Sales team can be assigned to multiple schools
- ✅ Views protected by permission decorators
- ✅ Data isolation working (branch/school filtering)
- ✅ Menu items conditional on permissions
- ✅ Unauthorized access returns 403

### Non-Functional Requirements
- ✅ No performance degradation (< 5% overhead)
- ✅ Comprehensive test coverage (> 80%)
- ✅ Security audit passed
- ✅ Documentation complete
- ✅ Zero data loss during migration

### Acceptance Testing
- [ ] Admin can access everything
- [ ] Store manager restricted to Replenishment > Stores, filtered by branch
- [ ] Demand planner can access Dashboard, Forecasting, Replenishment (no Admin)
- [ ] Sales team restricted to Dashboard, filtered by school
- [ ] Unauthorized users get 403 error
- [ ] Menu items match role permissions

---

## Appendix A: File Inventory

### Files to Create (NEW)
1. `users/management/commands/seed_roles.py` - Role seeding command
2. `users/management/commands/assign_user_role.py` - User role assignment CLI
3. `users/management/commands/assign_user_branches.py` - Branch assignment CLI
4. `users/management/commands/assign_user_schools.py` - School assignment CLI
5. `users/middleware.py` - Permission checking middleware
6. `dashboard/utils/permissions.py` - Data isolation utilities
7. `dashboard/context_processors.py` - Template context processor
8. `dashboard/templatetags/permission_tags.py` - Permission template tags
9. `templates/403.html` - Forbidden error page
10. `users/tests/test_permissions.py` - Unit tests
11. `dashboard/tests/test_views_permissions.py` - Integration tests

### Files to Modify (EXISTING)
1. `users/models.py` - Add assigned_schools, change assigned_branch to assigned_branches
2. `dashboard/views.py` - Add decorators, data isolation filters
3. `templates/base.html` - Conditional menu rendering
4. `saspulse/settings.py` - Add context processor, middleware
5. `users/views.py` - Update login redirect logic

### Migration Files (AUTO-GENERATED)
1. `users/migrations/000X_add_assigned_schools.py`
2. `users/migrations/000X_change_assigned_branch_to_many.py`

---

## Appendix B: Permission Matrix

| Feature | Admin | Store Mgr | Demand Planner | Sales Team |
|---------|-------|-----------|----------------|------------|
| **Dashboard** | ✅ All data | ❌ | ✅ All data | ✅ Filtered by school |
| **Forecasting** | ✅ All data | ❌ | ✅ All data | ❌ |
| **Replenishment - Stores** |  |  |  |  |
| - Store Manager Review | ✅ All branches | ✅ Assigned branches | ✅ All branches | ❌ |
| - My Requests | ✅ All requests | ✅ Own requests | ✅ All requests | ❌ |
| - Daily Pick List | ✅ All branches | ✅ Assigned branches | ✅ All branches | ❌ |
| **Replenishment - DP** |  |  |  |  |
| - DP Team Approval | ✅ | ❌ | ✅ | ❌ |
| - All Requests | ✅ | ❌ | ✅ | ❌ |
| **Admin Section** | ✅ | ❌ | ❌ | ❌ |

---

## Appendix C: Database Schema Diagram

```
┌─────────────────────────┐
│      CustomUser         │
├─────────────────────────┤
│ id (PK)                 │
│ username                │
│ email                   │
│ password_hash           │
│ is_superuser            │
│ is_staff                │
│ is_active               │
└─────────────────────────┘
         │ │
         │ │ ManyToMany
         │ └──────────────────┐
         │                    │
         │ ManyToMany         ▼
         │              ┌─────────────────────────┐
         │              │         Role            │
         │              ├─────────────────────────┤
         │              │ id (PK)                 │
         │              │ name                    │
         │              │ permissions (JSON)      │
         │              │ is_active               │
         │              └─────────────────────────┘
         │
         │ ManyToMany (assigned_branches)
         ├──────────────────┐
         │                  │
         │                  ▼
         │            ┌─────────────────────────┐
         │            │       Branch            │
         │            ├─────────────────────────┤
         │            │ id (PK)                 │
         │            │ name                    │
         │            │ code                    │
         │            └─────────────────────────┘
         │
         │ ManyToMany (assigned_schools)
         └──────────────────┐
                            │
                            ▼
                      ┌─────────────────────────┐
                      │       Product           │
                      ├─────────────────────────┤
                      │ id (PK)                 │
                      │ name                    │
                      │ sub_category (SCHOOL)   │
                      └─────────────────────────┘
```

---

## Appendix D: Quick Reference Commands

### Seed Roles
```bash
python manage.py seed_roles
```

### Assign User to Role
```bash
python manage.py assign_user_role john.doe store_manager
```

### Assign Branches to User
```bash
python manage.py assign_user_branches john.doe "Avondale Shop" "KBHS Shop"
```

### Assign Schools to User
```bash
python manage.py assign_user_schools jane.smith "KBHS" "Avondale"
```

### Check User Permissions (Django Shell)
```python
python manage.py shell

from users.models import CustomUser

user = CustomUser.objects.get(username='john.doe')
print(user.has_nested_permission('dashboard.view'))
print(user.get_data_scope())
print(user.get_all_permissions())
```

### List All Roles
```bash
python manage.py shell -c "from users.models import Role; print('\n'.join([r.name for r in Role.objects.all()]))"
```

---

## Summary

This implementation plan provides a comprehensive RBAC system that:

1. **Leverages existing infrastructure** - Uses the existing Role and CustomUser models
2. **Adds school assignment** - ManyToMany field for sales team
3. **Changes branch assignment** - ForeignKey → ManyToMany for multiple branches
4. **Standardizes permissions** - JSON structure with nested keys
5. **Protects views** - Decorators on all sensitive views
6. **Isolates data** - Branch/school filtering based on user scope
7. **Controls UI** - Menu items conditional on permissions
8. **Handles errors** - 403 template and logging
9. **Provides testing** - Unit, integration, and manual tests
10. **Includes migration plan** - Step-by-step deployment guide

The system is designed to be:
- **Secure** - Defense in depth, fail-safe defaults
- **Flexible** - Easy to add new roles/permissions
- **Maintainable** - Clear structure, well-documented
- **Performant** - Minimal overhead, efficient queries
- **User-friendly** - Clear error messages, intuitive behavior

Implementation can begin immediately with Phase 1 (database changes) and proceed through the 4-week timeline.
