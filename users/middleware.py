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
