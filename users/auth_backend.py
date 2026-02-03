"""
Custom Authentication Backend for SasPulse.

This module provides a custom authentication system that replaces Django's
built-in authentication. It includes user authentication, session management,
and security features like brute force protection.
"""

import secrets
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from .models import CustomUser, UserSession


class AnonymousUser:
    """
    Represents an unauthenticated user.
    Compatible with Django's authentication system.
    """
    id = None
    pk = None
    username = ''
    is_staff = False
    is_active = False
    is_superuser = False
    is_authenticated = False

    def __str__(self):
        return 'AnonymousUser'

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __hash__(self):
        return 1  # instances always return the same hash value

    def has_permission(self, permission_key):
        return False

    def has_role(self, role_name):
        return False

    def get_all_permissions(self):
        return {}


class CustomAuthBackend:
    """
    Custom authentication backend for user login, logout, and session management.

    Features:
    - Username or email login
    - Brute force protection (account locking)
    - Session management with expiry
    - Remember me functionality
    - IP address and user agent tracking
    """

    # Security settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    SESSION_DURATION_HOURS = 2
    REMEMBER_ME_DURATION_DAYS = 30

    def authenticate(self, request, username=None, password=None):
        """
        Authenticate a user by username/email and password.

        Args:
            request: Django request object
            username (str): Username or email address
            password (str): Plain text password

        Returns:
            CustomUser: Authenticated user object or None
        """
        if not username or not password:
            return None

        try:
            # Try to find user by username or email
            user = CustomUser.objects.get(
                Q(username=username) | Q(email=username)
            )
        except CustomUser.DoesNotExist:
            return None
        except CustomUser.MultipleObjectsReturned:
            # This shouldn't happen due to unique constraints, but handle it
            return None

        # Check if account is locked
        if user.is_locked():
            return None

        # Check if account is active
        if not user.is_active:
            return None

        # Verify password
        if not user.check_password(password):
            # Increment failed login attempts
            user.failed_login_attempts += 1

            # Lock account if max attempts reached
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                user.lock_account(duration_minutes=self.LOCKOUT_DURATION_MINUTES)

            user.save(update_fields=['failed_login_attempts'])
            return None

        # Successful authentication - reset failed attempts
        user.failed_login_attempts = 0
        user.last_login = timezone.now()
        user.save(update_fields=['failed_login_attempts', 'last_login'])

        return user

    def login(self, request, user, remember_me=False):
        """
        Create a session for the authenticated user.

        Args:
            request: Django request object
            user (CustomUser): Authenticated user object
            remember_me (bool): Extend session duration to 30 days

        Returns:
            str: Generated session key
        """
        # Generate unique session key
        session_key = secrets.token_urlsafe(30)

        # Calculate expiry time
        if remember_me:
            expires_at = timezone.now() + timedelta(days=self.REMEMBER_ME_DURATION_DAYS)
        else:
            expires_at = timezone.now() + timedelta(hours=self.SESSION_DURATION_HOURS)

        # Get client info
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Create session record
        session = UserSession.objects.create(
            session_key=session_key,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            remember_me=remember_me,
            is_active=True
        )

        # Store session key in Django session
        request.session['custom_session_key'] = session_key

        # Set session expiry in Django session
        if remember_me:
            request.session.set_expiry(self.REMEMBER_ME_DURATION_DAYS * 24 * 60 * 60)
        else:
            request.session.set_expiry(self.SESSION_DURATION_HOURS * 60 * 60)

        return session_key

    def logout(self, request):
        """
        Destroy the user's session (logout).

        Args:
            request: Django request object

        Returns:
            bool: True if logout successful, False otherwise
        """
        session_key = request.session.get('custom_session_key')

        if session_key:
            try:
                # Deactivate the session
                session = UserSession.objects.get(session_key=session_key)
                session.deactivate()
            except UserSession.DoesNotExist:
                pass

        # Clear Django session
        request.session.flush()

        return True

    def get_user_from_session(self, request):
        """
        Retrieve the authenticated user from the session.

        Args:
            request: Django request object

        Returns:
            CustomUser or AnonymousUser: User object if authenticated
        """
        session_key = request.session.get('custom_session_key')

        if not session_key:
            return AnonymousUser()

        try:
            session = UserSession.objects.select_related('user').get(
                session_key=session_key,
                is_active=True
            )

            # Check if session has expired
            if session.is_expired():
                session.deactivate()
                request.session.flush()
                return AnonymousUser()

            # Check if user is still active
            if not session.user.is_active:
                session.deactivate()
                request.session.flush()
                return AnonymousUser()

            # Update last activity
            session.last_activity = timezone.now()
            session.save(update_fields=['last_activity'])

            # Optionally extend expiry on activity (sliding expiration)
            if session.remember_me:
                # For remember me, extend to 30 days from now
                new_expiry = timezone.now() + timedelta(days=self.REMEMBER_ME_DURATION_DAYS)
            else:
                # For regular sessions, extend to 2 hours from now
                new_expiry = timezone.now() + timedelta(hours=self.SESSION_DURATION_HOURS)

            session.expires_at = new_expiry
            session.save(update_fields=['expires_at'])

            return session.user

        except UserSession.DoesNotExist:
            request.session.flush()
            return AnonymousUser()

    def is_authenticated(self, request):
        """
        Check if the request has a valid authenticated session.

        Args:
            request: Django request object

        Returns:
            bool: True if authenticated, False otherwise
        """
        user = self.get_user_from_session(request)
        return not isinstance(user, AnonymousUser)

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

    def get_user(self, user_id):
        """
        Get a user by their ID.
        This is required by Django's authentication framework.

        Args:
            user_id (int): User's primary key

        Returns:
            CustomUser or None: User object if found
        """
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None


# Global instance for easy access
auth_backend = CustomAuthBackend()
