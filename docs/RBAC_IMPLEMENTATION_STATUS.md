# RBAC Implementation Status

## Progress Overview

**Last Updated**: 2026-03-16
**Overall Progress**: Phases 1, 2, 3 Complete + Middleware (75%)

---

## ✅ Phase 1: Database & Model Updates (COMPLETE)

### Completed Tasks

1. ✅ **Added `assigned_schools` ManyToMany field**
   - File: `users/models.py` (Lines 93-101)
   - Allows sales team to be assigned to multiple schools
   - Uses Product model's `sub_category` field for school representation

2. ✅ **Changed `assigned_branch` to `assigned_branches`**
   - File: `users/models.py` (Lines 74-91)
   - Changed from ForeignKey to ManyToMany
   - Kept old `assigned_branch` field temporarily for backward compatibility
   - Related name for legacy: `assigned_managers_legacy`

3. ✅ **Added Permission Helper Methods**
   - File: `users/models.py` (Lines 317-401)
   - `has_nested_permission(permission_path)` - Hierarchical permission checking
   - `get_data_scope()` - Returns 'all', 'branch', or 'school'
   - `requires_data_filter()` - Check if filtering needed
   - `get_assigned_branch_names()` - Get branch names for filtering
   - `get_assigned_school_subcategories()` - Get school values for filtering

4. ✅ **Created Management Command for Role Seeding**
   - File: `users/management/commands/seed_roles.py`
   - Command: `python manage.py seed_roles`
   - Creates 4 standard roles: Admin, Store Manager, Demand Planner, Sales Team
   - Supports `--force` flag to update existing roles

5. ✅ **Migrations Applied**
   - Migration 0005: Added new fields (assigned_branches, assigned_schools)
   - Migration 0006: Data migration to copy assigned_branch → assigned_branches
   - Status: All migrations applied successfully

6. ✅ **Roles Seeded**
   - Admin role created with full permissions
   - Store Manager role created (branch-scoped)
   - Demand Planner role created (all data, no admin)
   - Sales Team role created (school-scoped)

---

## ✅ Phase 2: Data Isolation Utilities (COMPLETE)

### Completed Tasks

1. ✅ **Created Permission Utilities Module**
   - File: `dashboard/utils/permissions.py`
   - Functions created:
     - `apply_branch_filter(user, queryset, branch_field)` - Filter by branches
     - `apply_school_filter(user, queryset, school_field)` - Filter by schools
     - `apply_data_scope(user, queryset, scope_field)` - Auto-detect and filter
     - `get_user_landing_page(user)` - Determine landing page by role
     - `check_view_permission(user, permission_path)` - Check permissions
     - `permission_required_or_403(permission_path)` - Decorator with 403 handling
     - `get_user_context(user)` - Get user context for templates

2. ✅ **Updated Existing Decorators**
   - File: `users/decorators.py` (Lines 96-117)
   - Updated `permission_required` decorator to support both:
     - Old flat permissions (backward compatible)
     - New hierarchical permissions with dot notation (e.g., 'dashboard.view')
   - Auto-detects format based on presence of '.' in permission key

---

## 🔄 Phase 2: View Protection (IN PROGRESS)

### Remaining Tasks

1. ⏳ **Audit All Dashboard Views**
   - Need to review all views in `dashboard/views.py` (~50+ views)
   - Categorize by required permission
   - Document which views need which permissions

2. ⏳ **Add Permission Decorators to Views**
   - Apply `@permission_required('permission.path')` to all views
   - Examples:
     ```python
     @login_required()
     @permission_required('dashboard.view')
     def dashboard(request):
         ...

     @login_required()
     @permission_required('replenishment.stores.review')
     def store_manager_review(request):
         ...
     ```

3. ⏳ **Apply Data Isolation Filters**
   - Update views to filter querysets by user scope
   - Examples:
     ```python
     from dashboard.utils.permissions import apply_data_scope

     # In view function
     queryset = SalesOrderLineItem.objects.all()
     queryset = apply_data_scope(request.user, queryset)
     ```

### Key Views to Update

| View Function | Required Permission | Data Filter Needed |
|--------------|--------------------|--------------------|
| `dashboard` | `dashboard.view` | Yes (school for sales) |
| `sales_forecasting` | `forecasting.view` | Yes (school for sales) |
| `forecast_product_breakdown` | `forecasting.view` | Yes (school for sales) |
| `store_manager_review` | `replenishment.stores.review` | Yes (branch for store mgr) |
| `store_daily_pick_list` | `replenishment.daily_pick_list.view` | Yes (branch for store mgr) |
| `dp_replenishment_approval` | `replenishment.demand_planning.approve` | No (all data) |
| `dp_replenishment_requests_list` | `replenishment.demand_planning.view_all_requests` | No (all data) |

---

## ✅ Phase 3: Template & UI Updates (COMPLETE)

### Completed Tasks

1. ✅ **Created Context Processor**
   - File: `dashboard/context_processors.py`
   - Added to `settings.py` TEMPLATES configuration
   - Injects user permissions into all templates automatically
   - Provides: `user_permissions`, `user_roles`, `user_data_scope`, `user_branches`, `user_schools`

2. ✅ **Created Template Tags**
   - File: `dashboard/templatetags/permission_tags.py`
   - Tags implemented:
     - `{% if user|has_perm:'dashboard.view' %}` - Check single permission
     - `{% if user|has_any_perm:'perm1,perm2' %}` - Check any permission
     - `{% if user|has_all_perms:'perm1,perm2' %}` - Check all permissions
     - `{% if user|has_role:'Admin' %}` - Check role
     - `{% can_view_menu user 'dashboard' as can_view %}` - Menu visibility check
     - `{% get_data_scope_display user %}` - Human-readable data scope

3. ✅ **Updated Menu in base.html**
   - File: `templates/base.html`
   - Added `{% load permission_tags %}` at top
   - Wrapped Forecasting section with `{% if request.user|has_perm:'forecasting.view' %}`
   - Wrapped Replenishment section with nested permission checks:
     - Stores submenu: Shows only if user has `replenishment.stores.view`
     - Demand Planning submenu: Shows only if user has `replenishment.demand_planning.view`
     - Individual menu items: Each wrapped with specific permission check
   - Wrapped Admin section with `{% if request.user|has_perm:'admin.users.view' %}`

4. ✅ **Created 403 Forbidden Template**
   - File: `templates/403.html`
   - User-friendly error page with:
     - Icon and clear messaging
     - Shows required permission (if available)
     - "Go Back" and "Return Home" buttons
     - Help section with contact information
     - Debug panel (development only)

---

## 🔄 Phase 4: Middleware & Testing (PARTIAL)

### Completed Tasks

1. ✅ **Created Permission Middleware**
   - File: `users/middleware.py` (appended to existing file)
   - Added `PermissionCheckMiddleware`:
     - Logs all 403 (Forbidden) responses
     - Captures: username, path, IP, user agent, HTTP method
     - Helps identify security issues and misconfigured permissions
   - Added `DataScopeMiddleware`:
     - Adds `request.user_data_scope` to all requests
     - Adds `request.user_branches` list
     - Adds `request.user_schools` list
     - Makes data scope easily accessible in views
   - Added to `settings.py` MIDDLEWARE configuration

2. ✅ **Updated settings.py Configuration**
   - Added `dashboard.context_processors.user_permissions` to TEMPLATES
   - Added `users.middleware.DataScopeMiddleware` to MIDDLEWARE
   - Added `users.middleware.PermissionCheckMiddleware` to MIDDLEWARE

### Remaining Tasks

1. ⏳ **Create Unit Tests**
   - File to create: `users/tests/test_permissions.py`
   - Test permission helper methods
   - Test data filtering functions

3. ⏳ **Create Integration Tests**
   - File to create: `dashboard/tests/test_views_permissions.py`
   - Test view access for each role
   - Test data isolation

4. ⏳ **Manual Testing**
   - Create test users for each role
   - Test access patterns
   - Verify data filtering works correctly

---

## 📁 Files Created

### New Files
1. ✅ `users/management/__init__.py`
2. ✅ `users/management/commands/__init__.py`
3. ✅ `users/management/commands/seed_roles.py`
4. ✅ `dashboard/utils/__init__.py`
5. ✅ `dashboard/utils/permissions.py`
6. ✅ `users/migrations/0005_customuser_assigned_branches_and_more.py`
7. ✅ `users/migrations/0006_copy_assigned_branch_to_branches.py`
8. ✅ `docs/RBAC_IMPLEMENTATION_PLAN.md`
9. ✅ `docs/RBAC_IMPLEMENTATION_STATUS.md` (this file)

### Modified Files
1. ✅ `users/models.py` - Added fields and helper methods
2. ✅ `users/decorators.py` - Updated permission_required decorator

---

## 🔧 How to Use (Current State)

### 1. Seed Roles
```bash
python manage.py seed_roles
python manage.py seed_roles --force  # Update existing roles
```

### 2. Assign Users to Roles (via Django shell)
```python
from users.models import CustomUser, Role

user = CustomUser.objects.get(username='john.doe')
store_manager_role = Role.objects.get(name='Store Manager')
user.roles.add(store_manager_role)
```

### 3. Assign Branches to Store Managers
```python
from users.models import CustomUser
from cin7.models import Branch

user = CustomUser.objects.get(username='store_mgr')
branch1 = Branch.objects.get(name='Avondale Shop')
branch2 = Branch.objects.get(name='KBHS Shop')

user.assigned_branches.add(branch1, branch2)
```

### 4. Assign Schools to Sales Team
```python
from users.models import CustomUser
from cin7.models import Product

user = CustomUser.objects.get(username='sales_person')

# Get unique schools (products with sub_category)
schools = Product.objects.filter(
    sub_category__isnull=False
).values_list('sub_category', flat=True).distinct()

# Get product records for those schools
kbhs = Product.objects.filter(sub_category='KBHS').first()
avondale = Product.objects.filter(sub_category='Avondale').first()

user.assigned_schools.add(kbhs, avondale)
```

### 5. Check Permissions (in code)
```python
# Check nested permission
if request.user.has_nested_permission('dashboard.view'):
    # User can view dashboard
    pass

# Get data scope
scope = request.user.get_data_scope()  # Returns: 'all', 'branch', or 'school'

# Apply data filtering
from dashboard.utils.permissions import apply_data_scope

queryset = SalesOrderLineItem.objects.all()
filtered = apply_data_scope(request.user, queryset)
```

### 6. Use in Views (ready to implement)
```python
from users.decorators import login_required, permission_required
from dashboard.utils.permissions import apply_data_scope

@login_required()
@permission_required('dashboard.view')
def dashboard(request):
    # Get sales data
    sales = SalesOrderLineItem.objects.filter(
        sales_order__invoice_date__isnull=False
    )

    # Apply automatic data scope filtering
    sales = apply_data_scope(request.user, sales, scope_field='product__sub_category')

    # Rest of view logic...
    return render(request, 'dashboard/dashboard.html', context)
```

---

## 🎯 Next Steps

1. **Immediate**: Begin auditing dashboard views for permission requirements
2. **Next**: Apply permission decorators to critical views (dashboard, forecasting, replenishment)
3. **Then**: Apply data isolation filters to views
4. **After**: Create template context processor and template tags
5. **Finally**: Update base.html menu and create 403 template

---

## 📊 Permission Structure Reference

### Admin
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

### Store Manager
```json
{
  "dashboard": {"view": false},
  "forecasting": {"view": false},
  "replenishment": {
    "stores": {"view": true, "review": true, "create_request": true, "edit_request": true, "submit_request": true},
    "demand_planning": {"view": false},
    "daily_pick_list": {"view": true, "export": true}
  },
  "admin": {"users": {"view": false}},
  "data_scope": {"type": "branch", "filter_required": true}
}
```

### Demand Planner
```json
{
  "dashboard": {"view": true, "export": true},
  "forecasting": {"view": true, "edit": true, "export": true},
  "replenishment": {
    "stores": {"view": true, "review": true},
    "demand_planning": {"view": true, "approve": true, "reject": true, "view_all_requests": true},
    "daily_pick_list": {"view": true, "export": true}
  },
  "admin": {"users": {"view": false}},
  "data_scope": {"type": "all", "filter_required": false}
}
```

### Sales Team
```json
{
  "dashboard": {"view": true, "export": true},
  "forecasting": {"view": false},
  "replenishment": {"stores": {"view": false}, "demand_planning": {"view": false}},
  "admin": {"users": {"view": false}},
  "data_scope": {"type": "school", "filter_required": true}
}
```

---

## ⚠️ Important Notes

1. **Backward Compatibility**: The old `assigned_branch` field is kept temporarily. Code should transition to use `assigned_branches` (plural).

2. **Data Migration**: Migration 0006 automatically copies data from `assigned_branch` to `assigned_branches`. No manual data migration needed.

3. **Permission Format**: The system now supports both:
   - Old format: `'users.create'` (flat permissions)
   - New format: `'admin.users.create'` (hierarchical/nested permissions)

4. **Testing Required**: After applying permission decorators to views, comprehensive testing is needed for all 4 roles.

5. **Menu Update Required**: The base.html menu currently shows all items to all users. This needs to be updated with conditional rendering.

---

## 🐛 Known Issues

None currently. Implementation is proceeding as planned.

---

## 📝 Change Log

### 2026-03-16 - Session 2 (Latest)
- ✅ Phase 3 complete: Template context processor, template tags, 403 template, menu updates
- ✅ Phase 4 middleware complete: Permission logging, data scope injection
- ✅ settings.py configured with context processor and middleware
- 🎯 Ready for view protection: Need to apply decorators to dashboard views
- 🎯 Ready for testing: RBAC system foundation complete

### 2026-03-16 - Session 1
- ✅ Phase 1 complete: Database models updated, migrations applied, roles seeded
- ✅ Phase 2 utilities complete: Permission utilities module created
- ✅ Updated permission_required decorator to support nested permissions
