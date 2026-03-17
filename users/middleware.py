"""
Custom Authentication Middleware for SasPulse.

This module provides middleware to attach the authenticated user to each request
and handle session security.
"""

from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject
from .auth_backend import auth_backend, AnonymousUser


def get_user(request):
    """
    Lazy function to get the user from the session.
    This is called only when request.user is accessed.

    Args:
        request: Django request object

    Returns:
        CustomUser or AnonymousUser: Authenticated user or anonymous
    """
    if not hasattr(request, '_cached_user'):
        request._cached_user = auth_backend.get_user_from_session(request)
    return request._cached_user


class AuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware to attach the authenticated user to the request object.

    This replaces Django's built-in AuthenticationMiddleware and uses our
    custom authentication backend to retrieve the user from the session.

    Usage:
        Add to MIDDLEWARE in settings.py:
        'users.middleware.AuthenticationMiddleware'
    """

    def process_request(self, request):
        """
        Process the request and attach the user.

        Args:
            request: Django request object
        """
        # Use SimpleLazyObject to defer user lookup until accessed
        request.user = SimpleLazyObject(lambda: get_user(request))


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Middleware to handle session security and automatic logout.

    Features:
    - Automatic session expiration
    - Session hijacking detection (optional)
    - IP address verification (optional)

    Usage:
        Add to MIDDLEWARE in settings.py after AuthenticationMiddleware:
        'users.middleware.SessionSecurityMiddleware'
    """

    # Configuration
    VERIFY_IP = False  # Set to True to enable IP verification
    VERIFY_USER_AGENT = False  # Set to True to enable user agent verification

    def process_request(self, request):
        """
        Process the request and perform security checks.

        Args:
            request: Django request object
        """
        # Skip for anonymous users
        if isinstance(request.user, AnonymousUser):
            return None

        # Get session key
        session_key = request.session.get('custom_session_key')
        if not session_key:
            return None

        # Import here to avoid circular imports
        from .models import UserSession

        try:
            session = UserSession.objects.get(session_key=session_key, is_active=True)

            # Check if session expired (already done in auth_backend, but double check)
            if session.is_expired():
                auth_backend.logout(request)
                return None

            # Optional: Verify IP address hasn't changed
            if self.VERIFY_IP:
                current_ip = self._get_client_ip(request)
                if session.ip_address and session.ip_address != current_ip:
                    # Potential session hijacking - logout
                    auth_backend.logout(request)
                    return None

            # Optional: Verify user agent hasn't changed
            if self.VERIFY_USER_AGENT:
                current_user_agent = request.META.get('HTTP_USER_AGENT', '')
                if session.user_agent and session.user_agent != current_user_agent:
                    # Potential session hijacking - logout
                    auth_backend.logout(request)
                    return None

        except UserSession.DoesNotExist:
            # Session doesn't exist - logout
            auth_backend.logout(request)
            return None

        return None

    def _get_client_ip(self, request):
        """
        Get the client's IP address from the request.

        Args:
            request: Django request object

        Returns:
            str: IP address or None
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RequireAuthenticationMiddleware(MiddlewareMixin):
    """
    Optional middleware to require authentication for all views except whitelisted ones.

    This is useful if you want to make your entire application require login
    by default, with specific exemptions.

    Usage:
        1. Add to MIDDLEWARE in settings.py after AuthenticationMiddleware
        2. Configure AUTHENTICATION_EXEMPT_URLS in settings.py

    Example settings:
        AUTHENTICATION_EXEMPT_URLS = [
            r'^/auth/login/',
            r'^/auth/register/',
            r'^/auth/forgot-password/',
            r'^/auth/reset-password/',
            r'^/auth/activate/',
            r'^/static/',
            r'^/media/',
        ]
    """

    def process_request(self, request):
        """
        Check if the user is authenticated for non-exempt URLs.

        Args:
            request: Django request object
        """
        # Skip if user is authenticated
        if not isinstance(request.user, AnonymousUser):
            return None

        # Check if URL is exempt
        from django.conf import settings
        from django.urls import reverse
        import re

        # Get exempt URLs from settings
        exempt_urls = getattr(settings, 'AUTHENTICATION_EXEMPT_URLS', [])

        path = request.path_info

        # Check if current path matches any exempt pattern
        for pattern in exempt_urls:
            if re.match(pattern, path):
                return None

        # Not exempt and not authenticated - redirect to login
        from django.shortcuts import redirect
        from django.urls import resolve, Resolver404

        try:
            # Try to resolve the login URL
            login_url = getattr(settings, 'LOGIN_URL', '/auth/login/')
            return redirect(f"{login_url}?next={path}")
        except Exception:
            # If we can't redirect, just continue
            return None


# ========================================
# RBAC System Middleware (Added 2026-03-16)
# ========================================

import logging

logger = logging.getLogger(__name__)


class PermissionCheckMiddleware(MiddlewareMixin):
    """
    Middleware to log unauthorized access attempts (403 responses).

    This middleware tracks when users attempt to access resources they don't
    have permission for, helping identify potential security issues or
    misconfigured permissions.

    Logs include:
        - Username
        - Request path
        - IP address
        - User agent
        - HTTP method
        - Timestamp (automatic)

    Configuration:
        Add to settings.py MIDDLEWARE:
        MIDDLEWARE = [
            ...
            'users.middleware.PermissionCheckMiddleware',
        ]
    """

    def process_response(self, request, response):
        """
        Process the response and log 403 errors.

        Args:
            request: Django request object
            response: Django response object

        Returns:
            response: Unmodified response
        """
        # Log 403 (Forbidden) responses
        if response.status_code == 403:
            self._log_unauthorized_access(request)

        return response

    def _log_unauthorized_access(self, request):
        """
        Log details of an unauthorized access attempt.

        Args:
            request: HttpRequest object
        """
        if not isinstance(request.user, AnonymousUser):
            logger.warning(
                f"Unauthorized access attempt | "
                f"User: {request.user.username} | "
                f"Path: {request.path} | "
                f"Method: {request.method} | "
                f"IP: {self._get_client_ip(request)} | "
                f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')[:100]}"
            )
        else:
            logger.warning(
                f"Unauthorized access attempt (unauthenticated) | "
                f"Path: {request.path} | "
                f"Method: {request.method} | "
                f"IP: {self._get_client_ip(request)} | "
                f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')[:100]}"
            )

    def _get_client_ip(self, request):
        """
        Get client IP address from request.

        Handles X-Forwarded-For header for proxied requests.

        Args:
            request: HttpRequest object

        Returns:
            str: Client IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'Unknown')
        return ip


class DataScopeMiddleware(MiddlewareMixin):
    """
    Middleware to automatically add user data scope to request object.

    This middleware adds data scope information to the request object,
    making it easily accessible in views without having to call methods
    repeatedly.

    Adds to request:
        - request.user_data_scope: 'all', 'branch', or 'school'
        - request.user_branches: List of assigned branch names
        - request.user_schools: List of assigned school sub_categories

    Configuration:
        Add to settings.py MIDDLEWARE:
        MIDDLEWARE = [
            ...
            'users.middleware.DataScopeMiddleware',
        ]

    Usage in views:
        def my_view(request):
            if request.user_data_scope == 'branch':
                # Filter by request.user_branches
                queryset = queryset.filter(branch_name__in=request.user_branches)
    """

    def process_request(self, request):
        """
        Add data scope information to request.

        Args:
            request: Django request object
        """
        # Add data scope information to request
        if not isinstance(request.user, AnonymousUser):
            request.user_data_scope = request.user.get_data_scope()
            request.user_branches = request.user.get_assigned_branch_names()
            request.user_schools = request.user.get_assigned_school_subcategories()
        else:
            request.user_data_scope = None
            request.user_branches = []
            request.user_schools = []

        return None
