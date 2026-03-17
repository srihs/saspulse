"""
Template tags for permission checking in templates.

This module provides custom template tags and filters for checking user
permissions in Django templates.

Usage:
    {% load permission_tags %}

    {% if request.user|has_perm:'dashboard.view' %}
        <!-- User can view dashboard -->
    {% endif %}

    {% can_view_menu request.user 'dashboard' as can_view_dashboard %}
    {% if can_view_dashboard %}
        <a href="{% url 'dashboard:dashboard' %}">Dashboard</a>
    {% endif %}
"""

from django import template

register = template.Library()


@register.filter(name='has_perm')
def has_perm(user, permission_path):
    """
    Check if user has a specific permission.

    This filter uses the hierarchical permission system with dot notation.

    Args:
        user: CustomUser instance
        permission_path: Dot-separated permission path (e.g., 'dashboard.view')

    Returns:
        bool: True if user has permission

    Usage in templates:
        {% load permission_tags %}

        {% if request.user|has_perm:'dashboard.view' %}
            <a href="{% url 'dashboard:dashboard' %}">Dashboard</a>
        {% endif %}

        {% if request.user|has_perm:'replenishment.stores.review' %}
            <a href="{% url 'dashboard:store_replenishment_review' %}">Store Review</a>
        {% endif %}

        {% if request.user|has_perm:'admin.users.create' %}
            <button>Create User</button>
        {% endif %}
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return user.has_nested_permission(permission_path)


@register.filter(name='has_any_perm')
def has_any_perm(user, permission_paths):
    """
    Check if user has ANY of the specified permissions.

    Args:
        user: CustomUser instance
        permission_paths: Comma-separated list of permission paths

    Returns:
        bool: True if user has at least one permission

    Usage in templates:
        {% load permission_tags %}

        {% if request.user|has_any_perm:'dashboard.view,forecasting.view' %}
            <!-- User can view either dashboard or forecasting -->
        {% endif %}
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    paths = [p.strip() for p in permission_paths.split(',')]
    for path in paths:
        if user.has_nested_permission(path):
            return True

    return False


@register.filter(name='has_all_perms')
def has_all_perms(user, permission_paths):
    """
    Check if user has ALL of the specified permissions.

    Args:
        user: CustomUser instance
        permission_paths: Comma-separated list of permission paths

    Returns:
        bool: True if user has all permissions

    Usage in templates:
        {% load permission_tags %}

        {% if request.user|has_all_perms:'replenishment.stores.view,replenishment.stores.review' %}
            <!-- User has both permissions -->
        {% endif %}
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    paths = [p.strip() for p in permission_paths.split(',')]
    for path in paths:
        if not user.has_nested_permission(path):
            return False

    return True


@register.filter(name='has_role')
def has_role(user, role_name):
    """
    Check if user has a specific role.

    Args:
        user: CustomUser instance
        role_name: Name of the role (e.g., 'Admin', 'Store Manager')

    Returns:
        bool: True if user has the role

    Usage in templates:
        {% load permission_tags %}

        {% if request.user|has_role:'Store Manager' %}
            <p>Welcome, Store Manager!</p>
        {% endif %}
    """
    if not user.is_authenticated:
        return False

    return user.has_role(role_name)


@register.simple_tag
def can_view_menu(user, menu_section):
    """
    Check if user can view a menu section.

    This tag maps menu sections to their required permissions.

    Args:
        user: CustomUser instance
        menu_section: Menu section identifier

    Returns:
        bool: True if user can view the menu section

    Usage in templates:
        {% load permission_tags %}

        {% can_view_menu request.user 'dashboard' as can_view_dashboard %}
        {% if can_view_dashboard %}
            <li><a href="{% url 'dashboard:dashboard' %}">Dashboard</a></li>
        {% endif %}

        {% can_view_menu request.user 'replenishment_stores' as can_view_stores %}
        {% if can_view_stores %}
            <!-- Show stores submenu -->
        {% endif %}
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    # Map menu sections to required permissions
    permission_map = {
        'dashboard': 'dashboard.view',
        'forecasting': 'forecasting.view',
        'replenishment': 'replenishment.stores.view',  # Show if can view either stores or DP
        'replenishment_stores': 'replenishment.stores.view',
        'replenishment_dp': 'replenishment.demand_planning.view',
        'store_manager_review': 'replenishment.stores.review',
        'my_requests': 'replenishment.stores.view',
        'daily_pick_list': 'replenishment.daily_pick_list.view',
        'dp_approval': 'replenishment.demand_planning.approve',
        'dp_all_requests': 'replenishment.demand_planning.view_all_requests',
        'admin': 'admin.users.view',
    }

    # Special case: Show replenishment menu if user has access to either stores OR DP
    if menu_section == 'replenishment':
        return (user.has_nested_permission('replenishment.stores.view') or
                user.has_nested_permission('replenishment.demand_planning.view'))

    required_perm = permission_map.get(menu_section)
    if not required_perm:
        return False

    return user.has_nested_permission(required_perm)


@register.simple_tag
def get_data_scope_display(user):
    """
    Get human-readable data scope for display.

    Args:
        user: CustomUser instance

    Returns:
        str: Human-readable data scope

    Usage in templates:
        {% load permission_tags %}

        {% get_data_scope_display request.user as scope_display %}
        <p>Data scope: {{ scope_display }}</p>
    """
    if not user.is_authenticated:
        return 'Not authenticated'

    scope = user.get_data_scope()

    scope_map = {
        'all': 'All Data',
        'branch': 'Branch-Specific',
        'school': 'School-Specific',
    }

    return scope_map.get(scope, 'Unknown')


@register.inclusion_tag('dashboard/partials/permission_debug.html', takes_context=True)
def show_permission_debug(context):
    """
    Show permission debug information (for development only).

    This inclusion tag renders a debug panel showing the user's permissions,
    roles, and data scope. Should only be used in development.

    Args:
        context: Template context

    Returns:
        dict: Context for the debug template

    Usage in templates:
        {% load permission_tags %}

        {% if DEBUG %}
            {% show_permission_debug %}
        {% endif %}
    """
    user = context['request'].user

    if not user.is_authenticated:
        return {
            'authenticated': False,
            'user': None,
        }

    return {
        'authenticated': True,
        'user': user,
        'permissions': user.get_all_permissions(),
        'roles': list(user.roles.filter(is_active=True).values_list('name', flat=True)),
        'data_scope': user.get_data_scope(),
        'branches': user.get_assigned_branch_names(),
        'schools': user.get_assigned_school_subcategories(),
        'is_superuser': user.is_superuser,
    }
