from django.db import models
# from django.contrib.auth.models import User as DjangoUser  # Commented out - will enable for migration
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password as django_check_password
import secrets


class CustomUser(models.Model):
    """
    Custom User model - completely independent of Django's auth system.
    Provides full control over user authentication and authorization.
    """
    # Core Identity
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        help_text="Unique username for login"
    )
    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="Unique email address"
    )

    # Authentication
    password_hash = models.CharField(
        max_length=255,
        help_text="Argon2 hashed password"
    )

    # Personal Information
    first_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="User's first name"
    )
    last_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="User's last name"
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="User's phone number"
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text="User's department"
    )
    job_title = models.CharField(
        max_length=100,
        blank=True,
        help_text="User's job title"
    )
    bio = models.TextField(
        blank=True,
        help_text="User biography or notes"
    )

    # Roles & Permissions
    roles = models.ManyToManyField(
        'Role',
        related_name='custom_users',
        blank=True,
        help_text="Roles assigned to this user"
    )

    # Status & Flags
    is_active = models.BooleanField(
        default=False,
        help_text="User account is active (requires email verification)"
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="User can access admin interface"
    )
    is_superuser = models.BooleanField(
        default=False,
        help_text="User has all permissions"
    )
    email_verified = models.BooleanField(
        default=False,
        help_text="Email address has been verified"
    )

    # Security
    failed_login_attempts = models.IntegerField(
        default=0,
        help_text="Number of consecutive failed login attempts"
    )
    locked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Account is locked until this timestamp"
    )
    last_login = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last successful login timestamp"
    )
    last_password_change = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last password change timestamp"
    )

    # Tokens
    activation_token = models.CharField(
        max_length=64,
        blank=True,
        help_text="Email activation token"
    )
    reset_token = models.CharField(
        max_length=64,
        blank=True,
        help_text="Password reset token"
    )
    reset_token_expires = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Password reset token expiration"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'custom_users'
        ordering = ['username']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
            models.Index(fields=['email_verified']),
        ]

    def __str__(self):
        return self.username

    def set_password(self, raw_password):
        """
        Hash and set the user's password using Argon2.

        Args:
            raw_password (str): Plain text password
        """
        self.password_hash = make_password(raw_password)
        self.last_password_change = timezone.now()
        self.save(update_fields=['password_hash', 'last_password_change'])

    def check_password(self, raw_password):
        """
        Verify a plain text password against the stored hash.

        Args:
            raw_password (str): Plain text password to verify

        Returns:
            bool: True if password matches, False otherwise
        """
        return django_check_password(raw_password, self.password_hash)

    def has_permission(self, permission_key):
        """
        Check if user has a specific permission through any of their roles.
        Superusers always have all permissions.

        Args:
            permission_key (str): The key of the permission to check

        Returns:
            bool: True if user has the permission, False otherwise
        """
        if self.is_superuser:
            return True

        for role in self.roles.filter(is_active=True):
            if role.has_permission(permission_key):
                return True
        return False

    def has_role(self, role_name):
        """
        Check if user has a specific role.

        Args:
            role_name (str): The name of the role to check

        Returns:
            bool: True if user has the role, False otherwise
        """
        return self.roles.filter(name=role_name, is_active=True).exists()

    def get_full_name(self):
        """
        Get user's full name (first name + last name).

        Returns:
            str: Full name or username if names not set
        """
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.username

    def generate_activation_token(self):
        """
        Generate a secure activation token for email verification.

        Returns:
            str: Generated token
        """
        self.activation_token = secrets.token_urlsafe(32)
        self.save(update_fields=['activation_token'])
        return self.activation_token

    def generate_reset_token(self, expiry_hours=1):
        """
        Generate a secure password reset token.

        Args:
            expiry_hours (int): Token validity duration in hours

        Returns:
            str: Generated token
        """
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = timezone.now() + timezone.timedelta(hours=expiry_hours)
        self.save(update_fields=['reset_token', 'reset_token_expires'])
        return self.reset_token

    def is_locked(self):
        """
        Check if the account is currently locked.

        Returns:
            bool: True if account is locked, False otherwise
        """
        if self.locked_until:
            if timezone.now() < self.locked_until:
                return True
            else:
                # Auto-unlock if lock period has expired
                self.unlock_account()
        return False

    def lock_account(self, duration_minutes=30):
        """
        Lock the user account for a specified duration.

        Args:
            duration_minutes (int): Lock duration in minutes
        """
        self.locked_until = timezone.now() + timezone.timedelta(minutes=duration_minutes)
        self.save(update_fields=['locked_until'])

    def unlock_account(self):
        """
        Unlock the user account and reset failed login attempts.
        """
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=['locked_until', 'failed_login_attempts'])

    def get_all_permissions(self):
        """
        Get all permissions from all active roles assigned to this user.

        Returns:
            dict: Merged dictionary of all permissions
        """
        if self.is_superuser:
            return {'*': True}  # Superuser has all permissions

        all_permissions = {}
        for role in self.roles.filter(is_active=True):
            all_permissions.update(role.permissions)
        return all_permissions

    @property
    def is_authenticated(self):
        """
        Always return True for authenticated users.
        This is required by Django's authentication system.
        """
        return True

    @property
    def is_anonymous(self):
        """
        Always return False for authenticated users.
        This is required by Django's authentication system.
        """
        return False


class UserSession(models.Model):
    """
    Custom session management for tracking user sessions.
    Provides more control than Django's default session framework.
    """
    session_key = models.CharField(
        max_length=40,
        primary_key=True,
        help_text="Unique session identifier"
    )
    user = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        related_name='sessions',
        help_text="Associated user"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the session"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="Browser user agent string"
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Session creation timestamp"
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text="Last activity timestamp"
    )
    expires_at = models.DateTimeField(
        help_text="Session expiration timestamp"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Session is currently active"
    )
    remember_me = models.BooleanField(
        default=False,
        help_text="Extended session duration (30 days)"
    )

    class Meta:
        db_table = 'user_sessions'
        ordering = ['-last_activity']
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['last_activity']),
        ]

    def __str__(self):
        return f"Session for {self.user.username} ({self.session_key[:8]}...)"

    def is_expired(self):
        """
        Check if the session has expired.

        Returns:
            bool: True if expired, False otherwise
        """
        return timezone.now() > self.expires_at

    def extend_expiry(self, hours=2):
        """
        Extend the session expiry time.

        Args:
            hours (int): Hours to extend from now
        """
        self.expires_at = timezone.now() + timezone.timedelta(hours=hours)
        self.save(update_fields=['expires_at'])

    def deactivate(self):
        """
        Deactivate the session (logout).
        """
        self.is_active = False
        self.save(update_fields=['is_active'])


class Role(models.Model):
    """
    Role model for defining user roles with flexible permissions.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name for the role"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the role's purpose and responsibilities"
    )
    permissions = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON field for flexible permission configuration"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this role is currently active"
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.name

    def get_permission(self, permission_key):
        """
        Helper method to retrieve a specific permission from the JSON field.

        Args:
            permission_key (str): The key of the permission to retrieve

        Returns:
            The permission value or None if not found
        """
        return self.permissions.get(permission_key)

    def set_permission(self, permission_key, value):
        """
        Helper method to set a specific permission in the JSON field.

        Args:
            permission_key (str): The key of the permission to set
            value: The value to set for the permission
        """
        self.permissions[permission_key] = value
        self.save()

    def has_permission(self, permission_key):
        """
        Check if a permission exists and is set to True.

        Args:
            permission_key (str): The key of the permission to check

        Returns:
            bool: True if the permission exists and is True, False otherwise
        """
        return self.permissions.get(permission_key, False) is True


# ==============================================================================
# OLD USER PROFILE MODEL - TEMPORARILY COMMENTED OUT
# ==============================================================================
# This will be enabled during data migration phase when we move from Django User
# to CustomUser. For now, it's commented out to allow the system to boot.
#
# class UserProfile(models.Model):
#     """
#     UserProfile model to extend Django's User model with role relationships.
#     This uses a one-to-one relationship with the User model and adds
#     a many-to-many relationship with roles.
#     NOTE: This is kept temporarily for migration purposes only.
#     """
#     user = models.OneToOneField(
#         DjangoUser,
#         on_delete=models.CASCADE,
#         related_name='profile',
#         help_text="Associated Django User"
#     )
#     roles = models.ManyToManyField(
#         Role,
#         related_name='user_profiles',
#         blank=True,
#         help_text="Roles assigned to this user"
#     )
#     phone_number = models.CharField(
#         max_length=20,
#         blank=True,
#         help_text="User's phone number"
#     )
#     department = models.CharField(
#         max_length=100,
#         blank=True,
#         help_text="User's department"
#     )
#     job_title = models.CharField(
#         max_length=100,
#         blank=True,
#         help_text="User's job title"
#     )
#     bio = models.TextField(
#         blank=True,
#         help_text="User biography or notes"
#     )
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     class Meta:
#         ordering = ['user__username']
#         verbose_name = 'User Profile'
#         verbose_name_plural = 'User Profiles'
#
#     def __str__(self):
#         return f"{self.user.username}'s profile"
#
#     def get_role_names(self):
#         """
#         Get a list of role names assigned to this user.
#
#         Returns:
#             list: List of role names
#         """
#         return list(self.roles.values_list('name', flat=True))
#
#     def has_role(self, role_name):
#         """
#         Check if the user has a specific role.
#
#         Args:
#             role_name (str): The name of the role to check
#
#         Returns:
#             bool: True if user has the role, False otherwise
#         """
#         return self.roles.filter(name=role_name).exists()
#
#     def has_permission(self, permission_key):
#         """
#         Check if the user has a specific permission through any of their roles.
#
#         Args:
#             permission_key (str): The key of the permission to check
#
#         Returns:
#             bool: True if user has the permission through any role, False otherwise
#         """
#         for role in self.roles.filter(is_active=True):
#             if role.has_permission(permission_key):
#                 return True
#         return False
#
#     def get_all_permissions(self):
#         """
#         Get all permissions from all active roles assigned to this user.
#
#         Returns:
#             dict: Merged dictionary of all permissions
#         """
#         all_permissions = {}
#         for role in self.roles.filter(is_active=True):
#             all_permissions.update(role.permissions)
#         return all_permissions
#
#
# @receiver(post_save, sender=DjangoUser)
# def create_user_profile(sender, instance, created, **kwargs):
#     """
#     Signal to automatically create a UserProfile when a new DjangoUser is created.
#     NOTE: This is kept temporarily for migration purposes only.
#     """
#     if created:
#         UserProfile.objects.create(user=instance)
#
#
# @receiver(post_save, sender=DjangoUser)
# def save_user_profile(sender, instance, **kwargs):
#     """
#     Signal to automatically save the UserProfile when the DjangoUser is saved.
#     NOTE: This is kept temporarily for migration purposes only.
#     """
#     if hasattr(instance, 'profile'):
#         instance.profile.save()
