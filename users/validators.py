"""
Password and user input validators for Django forms and models.

This module provides validators that can be used with Django's form validation
system to enforce password complexity and other security requirements.
"""

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PasswordComplexityValidator:
    """
    Validates that a password meets complexity requirements.

    Requirements:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    - At least 1 special character

    Usage:
        In forms:
            password = forms.CharField(validators=[PasswordComplexityValidator()])

        In models:
            password = models.CharField(validators=[PasswordComplexityValidator()])
    """

    def __init__(self, min_length=8):
        """
        Initialize the validator.

        Args:
            min_length (int): Minimum password length (default: 8)
        """
        self.min_length = min_length

    def __call__(self, value):
        """
        Validate the password.

        Args:
            value (str): Password to validate

        Raises:
            ValidationError: If password doesn't meet requirements
        """
        errors = []

        # Minimum length check
        if len(value) < self.min_length:
            errors.append(
                _(f'Password must be at least {self.min_length} characters long.')
            )

        # Maximum length check
        if len(value) > 128:
            errors.append(
                _('Password must not exceed 128 characters.')
            )

        # Uppercase letter check
        if not re.search(r'[A-Z]', value):
            errors.append(
                _('Password must contain at least one uppercase letter.')
            )

        # Lowercase letter check
        if not re.search(r'[a-z]', value):
            errors.append(
                _('Password must contain at least one lowercase letter.')
            )

        # Number check
        if not re.search(r'[0-9]', value):
            errors.append(
                _('Password must contain at least one number.')
            )

        # Special character check
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', value):
            errors.append(
                _('Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?).')
            )

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        """
        Return help text for form fields.

        Returns:
            str: Help text describing requirements
        """
        return _(
            f'Your password must be at least {self.min_length} characters long and contain '
            'at least one uppercase letter, one lowercase letter, one number, '
            'and one special character.'
        )


class CommonPasswordValidator:
    """
    Validates that a password is not in a list of common passwords.

    Usage:
        password = forms.CharField(validators=[CommonPasswordValidator()])
    """

    # List of common passwords
    COMMON_PASSWORDS = [
        'password', 'password123', '12345678', 'qwerty', 'abc123',
        'password1', '123456789', '12345', '1234567890', 'letmein',
        'welcome', 'monkey', '1234567', 'password1234', 'admin',
        '123456', 'qwertyuiop', 'iloveyou', '1q2w3e4r', 'password!',
        'password@', 'passw0rd', 'P@ssw0rd', 'admin123', 'root',
        'user', 'test', 'guest', 'demo', 'default'
    ]

    def __call__(self, value):
        """
        Validate the password.

        Args:
            value (str): Password to validate

        Raises:
            ValidationError: If password is too common
        """
        if value.lower() in self.COMMON_PASSWORDS:
            raise ValidationError(
                _('This password is too common. Please choose a more unique password.'),
                code='common_password'
            )

    def get_help_text(self):
        """
        Return help text for form fields.

        Returns:
            str: Help text
        """
        return _('Your password must not be a commonly used password.')


class UserAttributeSimilarityValidator:
    """
    Validates that a password doesn't contain username or email.

    Usage:
        # In forms, pass user data to the validator
        validator = UserAttributeSimilarityValidator(user=user)
    """

    def __init__(self, user=None):
        """
        Initialize the validator.

        Args:
            user: User object (optional, for checking similarity)
        """
        self.user = user

    def __call__(self, value):
        """
        Validate the password.

        Args:
            value (str): Password to validate

        Raises:
            ValidationError: If password contains user attributes
        """
        if not self.user:
            return

        # Check if password contains username
        if self.user.username and self.user.username.lower() in value.lower():
            raise ValidationError(
                _('Password cannot contain your username.'),
                code='password_contains_username'
            )

        # Check if password contains email local part
        if self.user.email:
            email_local = self.user.email.split('@')[0]
            if email_local.lower() in value.lower():
                raise ValidationError(
                    _('Password cannot contain your email address.'),
                    code='password_contains_email'
                )

        # Check if password contains first or last name
        if self.user.first_name and len(self.user.first_name) > 2:
            if self.user.first_name.lower() in value.lower():
                raise ValidationError(
                    _('Password cannot contain your first name.'),
                    code='password_contains_first_name'
                )

        if self.user.last_name and len(self.user.last_name) > 2:
            if self.user.last_name.lower() in value.lower():
                raise ValidationError(
                    _('Password cannot contain your last name.'),
                    code='password_contains_last_name'
                )

    def get_help_text(self):
        """
        Return help text for form fields.

        Returns:
            str: Help text
        """
        return _('Your password cannot be too similar to your other personal information.')


class UsernameValidator:
    """
    Validates username format and requirements.

    Requirements:
    - 3-150 characters
    - Alphanumeric, underscores, hyphens only
    - Must start with letter or number
    - No reserved names

    Usage:
        username = forms.CharField(validators=[UsernameValidator()])
    """

    RESERVED_USERNAMES = [
        'admin', 'root', 'system', 'administrator', 'superuser',
        'test', 'guest', 'user', 'public', 'api', 'www',
        'mail', 'support', 'help', 'info', 'webmaster'
    ]

    def __init__(self, min_length=3, max_length=150):
        """
        Initialize the validator.

        Args:
            min_length (int): Minimum username length (default: 3)
            max_length (int): Maximum username length (default: 150)
        """
        self.min_length = min_length
        self.max_length = max_length

    def __call__(self, value):
        """
        Validate the username.

        Args:
            value (str): Username to validate

        Raises:
            ValidationError: If username doesn't meet requirements
        """
        # Length check
        if len(value) < self.min_length:
            raise ValidationError(
                _(f'Username must be at least {self.min_length} characters long.'),
                code='username_too_short'
            )

        if len(value) > self.max_length:
            raise ValidationError(
                _(f'Username must not exceed {self.max_length} characters.'),
                code='username_too_long'
            )

        # Format check
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', value):
            raise ValidationError(
                _('Username must start with a letter or number and contain only '
                  'letters, numbers, underscores, and hyphens.'),
                code='invalid_username_format'
            )

        # Reserved names check
        if value.lower() in self.RESERVED_USERNAMES:
            raise ValidationError(
                _('This username is reserved and cannot be used.'),
                code='reserved_username'
            )

    def get_help_text(self):
        """
        Return help text for form fields.

        Returns:
            str: Help text
        """
        return _(
            f'Username must be {self.min_length}-{self.max_length} characters long, '
            'start with a letter or number, and contain only letters, numbers, '
            'underscores, and hyphens.'
        )


class EmailValidator:
    """
    Enhanced email validator with additional checks.

    Usage:
        email = forms.EmailField(validators=[EmailValidator()])
    """

    DISPOSABLE_EMAIL_DOMAINS = [
        'tempmail.com', 'throwaway.email', '10minutemail.com',
        'guerrillamail.com', 'mailinator.com', 'trash-mail.com'
    ]

    def __init__(self, allow_disposable=True):
        """
        Initialize the validator.

        Args:
            allow_disposable (bool): Allow disposable email addresses (default: True)
        """
        self.allow_disposable = allow_disposable

    def __call__(self, value):
        """
        Validate the email address.

        Args:
            value (str): Email address to validate

        Raises:
            ValidationError: If email doesn't meet requirements
        """
        # Basic format check
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not re.match(pattern, value):
            raise ValidationError(
                _('Enter a valid email address.'),
                code='invalid_email_format'
            )

        # Length check (RFC 5321)
        if len(value) > 254:
            raise ValidationError(
                _('Email address is too long.'),
                code='email_too_long'
            )

        # Disposable email check (if enabled)
        if not self.allow_disposable:
            domain = value.split('@')[1].lower()
            if domain in self.DISPOSABLE_EMAIL_DOMAINS:
                raise ValidationError(
                    _('Disposable email addresses are not allowed.'),
                    code='disposable_email'
                )

    def get_help_text(self):
        """
        Return help text for form fields.

        Returns:
            str: Help text
        """
        return _('Enter a valid email address.')


class PasswordMatchValidator:
    """
    Validates that two password fields match (for password confirmation).

    Usage:
        # In forms
        def clean(self):
            cleaned_data = super().clean()
            validator = PasswordMatchValidator()
            validator(
                cleaned_data.get('password'),
                cleaned_data.get('password_confirm')
            )
            return cleaned_data
    """

    def __call__(self, password1, password2):
        """
        Validate that passwords match.

        Args:
            password1 (str): First password
            password2 (str): Second password (confirmation)

        Raises:
            ValidationError: If passwords don't match
        """
        if password1 != password2:
            raise ValidationError(
                _('Passwords do not match.'),
                code='password_mismatch'
            )

    def get_help_text(self):
        """
        Return help text for form fields.

        Returns:
            str: Help text
        """
        return _('Enter the same password as before, for verification.')


def validate_password(password, user=None):
    """
    Validate a password against all validators.

    This is a convenience function that runs all password validators.

    Args:
        password (str): Password to validate
        user: User object (optional, for similarity checking)

    Raises:
        ValidationError: If password doesn't meet requirements

    Example:
        try:
            validate_password('MyPassword123!', user=user)
        except ValidationError as e:
            print(e.messages)
    """
    validators = [
        PasswordComplexityValidator(),
        CommonPasswordValidator(),
    ]

    if user:
        validators.append(UserAttributeSimilarityValidator(user=user))

    errors = []
    for validator in validators:
        try:
            validator(password)
        except ValidationError as e:
            errors.extend(e.messages)

    if errors:
        raise ValidationError(errors)
