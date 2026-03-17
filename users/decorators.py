"""
Custom Authentication Decorators for SasPulse.

This module provides decorators for protecting views with authentication,
permission, and role requirements.
"""

from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden, JsonResponse
from django.urls import reverse
from .auth_backend import AnonymousUser


def login_required(redirect_to='/auth/login/', raise_exception=False):
    """
    Decorator to require user authentication for a view.

    Args:
        redirect_to (str): URL to redirect to if not authenticated
        raise_exception (bool): If True, return 403 instead of redirecting

    Usage:
        @login_required()
        def my_view(request):
            ...

        @login_required(redirect_to='/custom-login/')
        def my_view(request):
            ...

        @login_required(raise_exception=True)
        def api_view(request):
            ...  # Returns 403 JSON for APIs
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is authenticated
            if isinstance(request.user, AnonymousUser):
                if raise_exception:
                    # For API views, return JSON response
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Authentication required',
                            'detail': 'You must be logged in to access this resource.'
                        }, status=403)
                    # For regular views, return HTTP 403
                    return HttpResponseForbidden('Authentication required. Please log in.')

                # Redirect to login page with next parameter
                next_url = request.get_full_path()
                return redirect(f"{redirect_to}?next={next_url}")

            # User is authenticated, proceed
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def permission_required(permission_key, raise_exception=True):
    """
    Decorator to require a specific permission for a view.

    Args:
        permission_key (str): Permission key to check (e.g., 'users.create')
        raise_exception (bool): If True, return 403 instead of redirecting

    Usage:
        @login_required()
        @permission_required('users.create')
        def create_user_view(request):
            ...

        @login_required()
        @permission_required('reports.view', raise_exception=False)
        def view_report(request):
            ...  # Redirects to access denied page
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is authenticated first
            if isinstance(request.user, AnonymousUser):
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Authentication required',
                            'detail': 'You must be logged in to access this resource.'
                        }, status=403)
                    return HttpResponseForbidden('Authentication required.')
                return redirect('/auth/login/')

            # Check if user has the required permission
            # Support both old flat permissions and new nested permissions (dot notation)
            has_perm = False
            if '.' in permission_key:
                # New hierarchical permission system (e.g., 'dashboard.view')
                has_perm = request.user.has_nested_permission(permission_key)
            else:
                # Old flat permission system (backward compatibility)
                has_perm = request.user.has_permission(permission_key)

            if not has_perm:
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Permission denied',
                            'detail': f'You do not have the required permission: {permission_key}'
                        }, status=403)
                    return HttpResponseForbidden(
                        f'Access denied. Required permission: {permission_key}'
                    )
                # Redirect to access denied page
                return redirect('/access-denied/')

            # User has permission, proceed
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def role_required(role_name, raise_exception=True):
    """
    Decorator to require a specific role for a view.

    Args:
        role_name (str): Role name to check (e.g., 'Admin', 'Manager')
        raise_exception (bool): If True, return 403 instead of redirecting

    Usage:
        @login_required()
        @role_required('Admin')
        def admin_view(request):
            ...

        @login_required()
        @role_required('Manager', raise_exception=False)
        def manager_view(request):
            ...  # Redirects to access denied page
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is authenticated first
            if isinstance(request.user, AnonymousUser):
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Authentication required',
                            'detail': 'You must be logged in to access this resource.'
                        }, status=403)
                    return HttpResponseForbidden('Authentication required.')
                return redirect('/auth/login/')

            # Check if user has the required role
            if not request.user.has_role(role_name):
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Role required',
                            'detail': f'You must have the role: {role_name}'
                        }, status=403)
                    return HttpResponseForbidden(
                        f'Access denied. Required role: {role_name}'
                    )
                # Redirect to access denied page
                return redirect('/access-denied/')

            # User has role, proceed
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def verified_email_required(redirect_to='/auth/verify-email/', raise_exception=False):
    """
    Decorator to require email verification for a view.

    Args:
        redirect_to (str): URL to redirect to if email not verified
        raise_exception (bool): If True, return 403 instead of redirecting

    Usage:
        @login_required()
        @verified_email_required()
        def sensitive_view(request):
            ...

        @login_required()
        @verified_email_required(redirect_to='/verify-prompt/')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is authenticated first
            if isinstance(request.user, AnonymousUser):
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Authentication required',
                            'detail': 'You must be logged in to access this resource.'
                        }, status=403)
                    return HttpResponseForbidden('Authentication required.')
                return redirect('/auth/login/')

            # Check if email is verified
            if not request.user.email_verified:
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Email verification required',
                            'detail': 'You must verify your email address to access this resource.'
                        }, status=403)
                    return HttpResponseForbidden('Email verification required.')

                # Redirect to email verification page
                return redirect(redirect_to)

            # Email is verified, proceed
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def staff_required(raise_exception=True):
    """
    Decorator to require staff status for a view.
    This is useful for admin/staff-only pages.

    Args:
        raise_exception (bool): If True, return 403 instead of redirecting

    Usage:
        @login_required()
        @staff_required()
        def admin_dashboard(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is authenticated first
            if isinstance(request.user, AnonymousUser):
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Authentication required',
                            'detail': 'You must be logged in to access this resource.'
                        }, status=403)
                    return HttpResponseForbidden('Authentication required.')
                return redirect('/auth/login/')

            # Check if user is staff
            if not (request.user.is_staff or request.user.is_superuser):
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Staff access required',
                            'detail': 'You must be a staff member to access this resource.'
                        }, status=403)
                    return HttpResponseForbidden('Staff access required.')
                return redirect('/access-denied/')

            # User is staff, proceed
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def superuser_required(raise_exception=True):
    """
    Decorator to require superuser status for a view.
    This is for the highest level of access.

    Args:
        raise_exception (bool): If True, return 403 instead of redirecting

    Usage:
        @login_required()
        @superuser_required()
        def system_settings(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is authenticated first
            if isinstance(request.user, AnonymousUser):
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Authentication required',
                            'detail': 'You must be logged in to access this resource.'
                        }, status=403)
                    return HttpResponseForbidden('Authentication required.')
                return redirect('/auth/login/')

            # Check if user is superuser
            if not request.user.is_superuser:
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Superuser access required',
                            'detail': 'You must be a superuser to access this resource.'
                        }, status=403)
                    return HttpResponseForbidden('Superuser access required.')
                return redirect('/access-denied/')

            # User is superuser, proceed
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def any_permission_required(*permission_keys, raise_exception=True):
    """
    Decorator to require ANY of the specified permissions.
    User needs at least one of the permissions to access the view.

    Args:
        *permission_keys: Permission keys to check
        raise_exception (bool): If True, return 403 instead of redirecting

    Usage:
        @login_required()
        @any_permission_required('users.view', 'users.create', 'users.edit')
        def user_management(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is authenticated first
            if isinstance(request.user, AnonymousUser):
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Authentication required',
                            'detail': 'You must be logged in to access this resource.'
                        }, status=403)
                    return HttpResponseForbidden('Authentication required.')
                return redirect('/auth/login/')

            # Check if user has any of the required permissions
            has_any = any(request.user.has_permission(perm) for perm in permission_keys)

            if not has_any:
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Permission denied',
                            'detail': f'You need one of these permissions: {", ".join(permission_keys)}'
                        }, status=403)
                    return HttpResponseForbidden(
                        f'Access denied. Required permissions (any): {", ".join(permission_keys)}'
                    )
                return redirect('/access-denied/')

            # User has at least one permission, proceed
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def all_permissions_required(*permission_keys, raise_exception=True):
    """
    Decorator to require ALL of the specified permissions.
    User needs all permissions to access the view.

    Args:
        *permission_keys: Permission keys to check
        raise_exception (bool): If True, return 403 instead of redirecting

    Usage:
        @login_required()
        @all_permissions_required('users.view', 'users.create', 'users.edit')
        def full_user_management(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user is authenticated first
            if isinstance(request.user, AnonymousUser):
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Authentication required',
                            'detail': 'You must be logged in to access this resource.'
                        }, status=403)
                    return HttpResponseForbidden('Authentication required.')
                return redirect('/auth/login/')

            # Check if user has all required permissions
            missing_perms = [
                perm for perm in permission_keys
                if not request.user.has_permission(perm)
            ]

            if missing_perms:
                if raise_exception:
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Permission denied',
                            'detail': f'Missing permissions: {", ".join(missing_perms)}'
                        }, status=403)
                    return HttpResponseForbidden(
                        f'Access denied. Missing permissions: {", ".join(missing_perms)}'
                    )
                return redirect('/access-denied/')

            # User has all permissions, proceed
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
