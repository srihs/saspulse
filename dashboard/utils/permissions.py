"""
Data isolation and permission utilities for RBAC system.

This module provides functions to filter querysets based on user's data scope
(all, branch, school) and role permissions.

Usage:
    from dashboard.utils.permissions import apply_data_scope, apply_branch_filter, apply_school_filter

    # Auto-detect scope and apply appropriate filter
    filtered_qs = apply_data_scope(request.user, queryset)

    # Specific filters
    filtered_qs = apply_branch_filter(request.user, queryset, branch_field='branch')
    filtered_qs = apply_school_filter(request.user, queryset, school_field='product__sub_category')
"""

from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import render


def apply_branch_filter(user, queryset, branch_field='branch'):
    """
    Filter queryset by user's assigned branches.

    Args:
        user: CustomUser instance
        queryset: Django QuerySet to filter
        branch_field: Name of branch field or path (default: 'branch')

    Returns:
        Filtered QuerySet

    Examples:
        # Filter by branch ForeignKey
        requests = ReplenishmentRequest.objects.all()
        requests = apply_branch_filter(user, requests, branch_field='branch')

        # Filter by branch name (VARCHAR)
        stock = Stock.objects.all()
        stock = apply_branch_filter(user, stock, branch_field='branch_name')
    """
    if user.is_superuser or user.get_data_scope() == 'all':
        return queryset

    if user.get_data_scope() == 'branch':
        # Get user's assigned branches
        user_branches = user.assigned_branches.all()

        # Backward compatibility: include legacy assigned_branch
        if user.assigned_branch and user.assigned_branch not in user_branches:
            user_branches = list(user_branches) + [user.assigned_branch]

        if not user_branches:
            # User has branch scope but no branches assigned - return empty
            return queryset.none()

        # Check if filtering by name (VARCHAR) or ForeignKey
        if branch_field.endswith('_name') or branch_field == 'branch_name':
            # Filter by branch name (VARCHAR field)
            branch_names = [b.name for b in user_branches]
            filter_kwargs = {f'{branch_field}__in': branch_names}
        else:
            # Filter by branch ForeignKey
            filter_kwargs = {f'{branch_field}__in': user_branches}

        return queryset.filter(**filter_kwargs)

    return queryset


def apply_school_filter(user, queryset, school_field='product__sub_category'):
    """
    Filter queryset by user's assigned schools.

    Args:
        user: CustomUser instance
        queryset: Django QuerySet to filter
        school_field: Path to school field (default: 'product__sub_category')

    Returns:
        Filtered QuerySet

    Examples:
        # Filter sales by school
        sales = SalesOrderLineItem.objects.all()
        sales = apply_school_filter(user, sales, school_field='product__sub_category')

        # Filter forecasts by school
        forecasts = SalesForecastBase.objects.all()
        forecasts = apply_school_filter(user, forecasts, school_field='product__sub_category')
    """
    if user.is_superuser or user.get_data_scope() == 'all':
        return queryset

    if user.get_data_scope() == 'school':
        # Get school sub_category values from assigned schools
        user_school_values = user.get_assigned_school_subcategories()

        if not user_school_values:
            # User has school scope but no schools assigned - return empty
            return queryset.none()

        # Filter by school sub_category values
        filter_kwargs = {f'{school_field}__in': user_school_values}
        return queryset.filter(**filter_kwargs)

    return queryset


def apply_data_scope(user, queryset, scope_field=None):
    """
    Automatically apply data scope filtering based on user's role.

    This is a convenience function that detects the user's data scope
    and applies the appropriate filter.

    Args:
        user: CustomUser instance
        queryset: Django QuerySet to filter
        scope_field: Optional field path for filtering (auto-detect if None)

    Returns:
        Filtered QuerySet

    Examples:
        # Auto-detect scope
        data = SalesOrderLineItem.objects.all()
        data = apply_data_scope(request.user, data)

        # With explicit field
        data = apply_data_scope(request.user, data, scope_field='branch')
    """
    scope = user.get_data_scope()

    if scope == 'all' or user.is_superuser:
        return queryset

    if scope == 'branch':
        # Try common branch field names
        branch_fields = ['branch', 'assigned_branch', 'branch_name']

        if scope_field and 'branch' in scope_field.lower():
            return apply_branch_filter(user, queryset, branch_field=scope_field)

        # Try common field names
        for field in branch_fields:
            try:
                return apply_branch_filter(user, queryset, branch_field=field)
            except Exception:
                continue

        # No valid branch field found - return empty to be safe
        return queryset.none()

    if scope == 'school':
        # Default school field path
        school_field = scope_field or 'product__sub_category'
        return apply_school_filter(user, queryset, school_field=school_field)

    return queryset


def get_user_landing_page(user):
    """
    Get the appropriate landing page URL for a user based on their role.

    Args:
        user: CustomUser instance

    Returns:
        str: URL path for user's landing page

    Examples:
        # In login view
        landing_url = get_user_landing_page(user)
        return redirect(landing_url)
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


def check_view_permission(user, permission_path):
    """
    Check if user has permission to access a view.

    Args:
        user: CustomUser instance
        permission_path: Dot-separated permission path (e.g., 'dashboard.view')

    Returns:
        bool: True if user has permission

    Examples:
        if check_view_permission(request.user, 'dashboard.view'):
            # User can access dashboard
            pass
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return user.has_nested_permission(permission_path)


def permission_required_or_403(permission_path):
    """
    Decorator to check permission and return 403 if unauthorized.

    This is a convenience decorator that combines permission checking
    with proper error handling.

    Args:
        permission_path: Dot-separated permission path

    Returns:
        Decorated view function

    Examples:
        @permission_required_or_403('dashboard.view')
        def dashboard_view(request):
            # View logic
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden(
                    render(request, '403.html', {'message': 'You must be logged in to access this page.'})
                )

            if not check_view_permission(request.user, permission_path):
                return HttpResponseForbidden(
                    render(request, '403.html', {
                        'message': f'You do not have permission to access this page.',
                        'required_permission': permission_path
                    })
                )

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_user_context(user):
    """
    Get user permission context for templates.

    Args:
        user: CustomUser instance

    Returns:
        dict: Context dictionary with user permissions

    Examples:
        # In view
        context = get_user_context(request.user)
        return render(request, 'template.html', context)
    """
    if not user.is_authenticated:
        return {
            'user_permissions': {},
            'user_roles': [],
            'user_data_scope': None,
            'user_branches': [],
            'user_schools': [],
        }

    return {
        'user_permissions': user.get_all_permissions(),
        'user_roles': list(user.roles.filter(is_active=True).values_list('name', flat=True)),
        'user_data_scope': user.get_data_scope(),
        'user_branches': user.get_assigned_branch_names(),
        'user_schools': user.get_assigned_school_subcategories(),
        'is_admin': user.is_superuser or user.has_nested_permission('admin.users.view'),
        'is_store_manager': user.has_role('Store Manager'),
        'is_demand_planner': user.has_role('Demand Planner'),
        'is_sales_team': user.has_role('Sales Team'),
    }
