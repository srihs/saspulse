# Quick Start: User Management System

## 🚀 Access the System

### URLs
- **Users:** http://localhost:8000/system/users/
- **Roles:** http://localhost:8000/system/roles/
- **Admin:** http://localhost:8000/admin/

### Default Admin Account
```
Username: admin
Email: admin@saspulse.com
```

**Set password:**
```bash
python3 manage.py changepassword admin
```

---

## 📋 Common Tasks

### 1. Create a New Role

**Via UI:**
1. Go to http://localhost:8000/system/roles/
2. Click "Create Role" button
3. Fill in:
   - **Name:** e.g., "Sales Manager"
   - **Description:** Role description
   - **Permissions:** JSON format
4. Click "Save Role"

**Permissions Example:**
```json
{
  "dashboard": {"can_view": true},
  "inventory": {"can_edit": true, "can_delete": false},
  "reports": {"can_view": true, "can_export": true},
  "sales": {"can_view": true, "can_edit": true}
}
```

**Via Django Shell:**
```python
from users.models import Role

role = Role.objects.create(
    name='Sales Manager',
    description='Can manage sales and view reports',
    permissions={
        'dashboard': {'can_view': True},
        'inventory': {'can_edit': True},
        'reports': {'can_view': True}
    }
)
```

---

### 2. Create a New User

**Via UI:**
1. Go to http://localhost:8000/system/users/
2. Click "Create User" button
3. Fill in:
   - Username
   - Email
   - First Name
   - Last Name
   - Password (2x for confirmation)
   - Check "Active" if user should be active
4. Click "Create User"

**Via Django Shell:**
```python
from django.contrib.auth.models import User

user = User.objects.create_user(
    username='john.smith',
    email='john@company.com',
    password='SecurePass123',
    first_name='John',
    last_name='Smith'
)

# Update profile
user.profile.phone_number = '+1234567890'
user.profile.department = 'Sales'
user.profile.job_title = 'Sales Manager'
user.profile.save()
```

---

### 3. Assign Roles to User

**Via UI:**
1. Go to http://localhost:8000/system/users/
2. Find the user in the table
3. Click the dropdown menu (three dots)
4. Select "Manage Roles"
5. Check the roles you want to assign
6. Click "Save Roles"

**Via Django Shell:**
```python
from django.contrib.auth.models import User
from users.models import Role

user = User.objects.get(username='john.smith')
role = Role.objects.get(name='Sales Manager')

# Assign role
user.profile.roles.add(role)

# Assign multiple roles
role2 = Role.objects.get(name='Report Viewer')
user.profile.roles.add(role, role2)

# Check assigned roles
print(user.profile.get_role_names())
# Output: ['Sales Manager', 'Report Viewer']
```

---

### 4. Check User Permissions

**In Views:**
```python
def my_view(request):
    # Check if user has specific permission
    if request.user.profile.has_permission('inventory.can_edit'):
        # Allow editing
        can_edit = True
    else:
        can_edit = False

    # Get all permissions
    all_permissions = request.user.profile.get_all_permissions()

    # Check if user has specific role
    if request.user.profile.has_role('Sales Manager'):
        # Show sales manager features
        pass
```

**In Templates:**
```django
{% if request.user.profile.has_permission.inventory.can_edit %}
  <button>Edit Inventory</button>
{% endif %}

<!-- Note: You may need to pass permissions to template context -->
```

**In Django Shell:**
```python
from django.contrib.auth.models import User

user = User.objects.get(username='john.smith')

# Check permission
has_perm = user.profile.has_permission('inventory.can_edit')
print(f"Can edit inventory: {has_perm}")

# Get all permissions
all_perms = user.profile.get_all_permissions()
print(all_perms)
```

---

### 5. Edit User Details

**Via UI:**
1. Go to http://localhost:8000/system/users/
2. Find the user
3. Click dropdown → "Edit"
4. Update fields
5. Click "Update User"

**Via Django Shell:**
```python
from django.contrib.auth.models import User

user = User.objects.get(username='john.smith')
user.email = 'john.smith@newdomain.com'
user.first_name = 'Jonathan'
user.save()

# Update profile
user.profile.department = 'Marketing'
user.profile.job_title = 'Marketing Director'
user.profile.save()
```

---

### 6. Deactivate User (Don't Delete)

**Via UI:**
1. Edit the user
2. Uncheck "Active" checkbox
3. Save

**Via Django Shell:**
```python
user = User.objects.get(username='john.smith')
user.is_active = False
user.save()
```

---

### 7. Delete User

**Via UI:**
1. Go to user list
2. Click dropdown → "Delete"
3. Confirm deletion

**Via Django Shell:**
```python
user = User.objects.get(username='john.smith')
user.delete()  # This also deletes the UserProfile
```

---

## 🔒 Permission System

### Permission Structure

Permissions are stored as JSON with flexible structure:

```json
{
  "module_name": {
    "can_view": true,
    "can_edit": true,
    "can_delete": false,
    "can_export": true
  },
  "another_module": {
    "access_level": "full",
    "features": ["feature1", "feature2"]
  }
}
```

### Common Permission Patterns

**Read-Only Access:**
```json
{
  "dashboard": {"can_view": true},
  "reports": {"can_view": true, "can_export": false}
}
```

**Manager Level:**
```json
{
  "dashboard": {"can_view": true},
  "inventory": {"can_view": true, "can_edit": true, "can_delete": false},
  "orders": {"can_view": true, "can_edit": true, "can_approve": true},
  "reports": {"can_view": true, "can_export": true}
}
```

**Admin Level:**
```json
{
  "dashboard": {"can_view": true},
  "inventory": {"can_view": true, "can_edit": true, "can_delete": true},
  "orders": {"can_view": true, "can_edit": true, "can_delete": true},
  "users": {"can_manage": true},
  "reports": {"can_view": true, "can_export": true, "can_configure": true}
}
```

---

## 📊 Navigation

The system is accessible via the **System** menu in the sidebar:

```
Navigation
├── Home
│   └── ...
├── System  ← NEW SECTION
│   ├── Users
│   └── Roles
└── ...
```

---

## 🛠️ Troubleshooting

### User profile not created automatically

**Problem:** UserProfile doesn't exist for a user

**Solution:**
```python
from django.contrib.auth.models import User
from users.models import UserProfile

user = User.objects.get(username='someuser')
if not hasattr(user, 'profile'):
    UserProfile.objects.create(user=user)
```

### Can't access system pages

**Problem:** "You must be logged in" error

**Solution:**
1. Make sure you're logged in: http://localhost:8000/admin/
2. Or create a login page and update LOGIN_URL in settings

### Permission not working

**Problem:** `has_permission()` returns False

**Solution:**
```python
# Check the exact permission key
user = User.objects.get(username='john')
perms = user.profile.get_all_permissions()
print(perms)  # See what permissions exist

# Make sure role is active
for role in user.profile.roles.all():
    print(f"{role.name}: is_active={role.is_active}")
```

---

## 📚 Example Workflows

### Setting Up a New Department

```python
from django.contrib.auth.models import User
from users.models import Role

# 1. Create department role
sales_role = Role.objects.create(
    name='Sales Team',
    description='Sales department staff',
    permissions={
        'dashboard': {'can_view': True},
        'customers': {'can_view': True, 'can_edit': True},
        'orders': {'can_view': True, 'can_create': True},
        'reports': {'can_view': True}
    }
)

# 2. Create manager role
manager_role = Role.objects.create(
    name='Sales Manager',
    description='Sales department manager',
    permissions={
        'dashboard': {'can_view': True},
        'customers': {'can_view': True, 'can_edit': True, 'can_delete': True},
        'orders': {'can_view': True, 'can_create': True, 'can_approve': True},
        'reports': {'can_view': True, 'can_export': True},
        'team': {'can_view': True}
    }
)

# 3. Create users
manager = User.objects.create_user(
    username='sales.manager',
    email='manager@company.com',
    password='SecurePass123',
    first_name='Jane',
    last_name='Manager'
)
manager.profile.department = 'Sales'
manager.profile.job_title = 'Sales Manager'
manager.profile.roles.add(manager_role)
manager.profile.save()

staff1 = User.objects.create_user(
    username='sales.staff1',
    email='staff1@company.com',
    password='SecurePass123',
    first_name='John',
    last_name='Staff'
)
staff1.profile.department = 'Sales'
staff1.profile.job_title = 'Sales Representative'
staff1.profile.roles.add(sales_role)
staff1.profile.save()
```

---

## 💡 Best Practices

1. **Role Naming:**
   - Use clear, descriptive names
   - Consider department + level (e.g., "Sales Manager", "IT Admin")

2. **Permission Structure:**
   - Keep permissions hierarchical
   - Use consistent naming (module.action)
   - Document your permission structure

3. **User Management:**
   - Always deactivate instead of delete when possible
   - Keep audit trail of changes
   - Regularly review role assignments

4. **Security:**
   - Use strong passwords
   - Review permissions regularly
   - Limit admin access to only necessary users
   - Enable two-factor authentication (future enhancement)

---

## 🎓 Learning Resources

### Django User Management
- [Django Authentication Docs](https://docs.djangoproject.com/en/stable/topics/auth/)
- [Django Permissions](https://docs.djangoproject.com/en/stable/topics/auth/default/#permissions-and-authorization)

### Project Files
- Models: `/users/models.py`
- Views: `/users/views.py`
- Forms: `/users/forms.py`
- Templates: `/users/templates/users/`
- Full Documentation: `/USER_MANAGEMENT_SUMMARY.md`

---

## 🆘 Getting Help

If you encounter issues:

1. Check Django logs: `tail -f /tmp/django.log`
2. Run system check: `python3 manage.py check`
3. Check migrations: `python3 manage.py showmigrations users`
4. Review the full documentation: `USER_MANAGEMENT_SUMMARY.md`

---

**That's it! You're ready to manage users and roles in SasPulse!** 🎉
