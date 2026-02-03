"""
Utility functions for authentication and password management.

This module provides helper functions for password hashing, validation,
token generation, and other authentication-related tasks.
"""

import secrets
import string
import re
from django.contrib.auth.hashers import make_password, check_password as django_check_password
from django.core.exceptions import ValidationError


def hash_password(raw_password):
    """
    Hash a plain text password using Argon2.

    Args:
        raw_password (str): Plain text password

    Returns:
        str: Hashed password

    Example:
        hashed = hash_password('MySecurePassword123!')
    """
    return make_password(raw_password)


def check_password(raw_password, password_hash):
    """
    Verify a plain text password against a stored hash.

    Args:
        raw_password (str): Plain text password to verify
        password_hash (str): Stored hashed password

    Returns:
        bool: True if password matches, False otherwise

    Example:
        is_valid = check_password('MySecurePassword123!', user.password_hash)
    """
    return django_check_password(raw_password, password_hash)


def generate_token(length=32):
    """
    Generate a cryptographically secure random token.

    Args:
        length (int): Length of the token (default: 32)

    Returns:
        str: URL-safe random token

    Example:
        token = generate_token()
        reset_token = generate_token(64)
    """
    return secrets.token_urlsafe(length)


def generate_session_key():
    """
    Generate a session key (40 characters).

    Returns:
        str: Session key

    Example:
        session_key = generate_session_key()
    """
    return secrets.token_urlsafe(30)  # ~40 chars after base64 encoding


def generate_password(length=12, use_special=True):
    """
    Generate a random password that meets complexity requirements.

    Args:
        length (int): Length of the password (default: 12)
        use_special (bool): Include special characters (default: True)

    Returns:
        str: Generated password

    Example:
        temp_password = generate_password()
        simple_password = generate_password(8, use_special=False)
    """
    if length < 8:
        length = 8

    # Character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = '!@#$%^&*()_+-=[]{}|;:,.<>?'

    # Ensure at least one character from each required set
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
    ]

    if use_special:
        password.append(secrets.choice(special))
        all_chars = lowercase + uppercase + digits + special
    else:
        all_chars = lowercase + uppercase + digits

    # Fill the rest randomly
    remaining_length = length - len(password)
    password.extend(secrets.choice(all_chars) for _ in range(remaining_length))

    # Shuffle the password
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)


def validate_password_strength(password):
    """
    Validate password complexity requirements.

    Requirements:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    - At least 1 special character

    Args:
        password (str): Password to validate

    Returns:
        tuple: (is_valid: bool, error_messages: list)

    Example:
        is_valid, errors = validate_password_strength('MyPass123!')
        if not is_valid:
            print(errors)
    """
    errors = []

    # Minimum length check
    if len(password) < 8:
        errors.append('Password must be at least 8 characters long.')

    # Maximum length check (for security and storage)
    if len(password) > 128:
        errors.append('Password must not exceed 128 characters.')

    # Uppercase letter check
    if not re.search(r'[A-Z]', password):
        errors.append('Password must contain at least one uppercase letter.')

    # Lowercase letter check
    if not re.search(r'[a-z]', password):
        errors.append('Password must contain at least one lowercase letter.')

    # Number check
    if not re.search(r'[0-9]', password):
        errors.append('Password must contain at least one number.')

    # Special character check
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        errors.append('Password must contain at least one special character.')

    # Common password check (basic)
    common_passwords = [
        'password', 'password123', '12345678', 'qwerty', 'abc123',
        'password1', '123456789', '12345', '1234567890', 'letmein'
    ]
    if password.lower() in common_passwords:
        errors.append('Password is too common. Please choose a more unique password.')

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_username(username):
    """
    Validate username format and requirements.

    Requirements:
    - 3-150 characters
    - Alphanumeric characters, underscores, hyphens only
    - Must start with a letter or number
    - No spaces

    Args:
        username (str): Username to validate

    Returns:
        tuple: (is_valid: bool, error_message: str or None)

    Example:
        is_valid, error = validate_username('john_doe')
        if not is_valid:
            print(error)
    """
    # Length check
    if len(username) < 3:
        return False, 'Username must be at least 3 characters long.'

    if len(username) > 150:
        return False, 'Username must not exceed 150 characters.'

    # Format check (alphanumeric, underscore, hyphen only)
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', username):
        return False, 'Username must start with a letter or number and contain only letters, numbers, underscores, and hyphens.'

    # Reserved usernames
    reserved = [
        'admin', 'root', 'system', 'administrator', 'superuser',
        'test', 'guest', 'user', 'public', 'api', 'www'
    ]
    if username.lower() in reserved:
        return False, 'This username is reserved and cannot be used.'

    return True, None


def validate_email(email):
    """
    Validate email address format.

    Args:
        email (str): Email address to validate

    Returns:
        tuple: (is_valid: bool, error_message: str or None)

    Example:
        is_valid, error = validate_email('user@example.com')
        if not is_valid:
            print(error)
    """
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not email:
        return False, 'Email address is required.'

    if len(email) > 254:  # RFC 5321
        return False, 'Email address is too long.'

    if not re.match(pattern, email):
        return False, 'Invalid email address format.'

    return True, None


def sanitize_username(username):
    """
    Sanitize a username by removing invalid characters.

    Args:
        username (str): Username to sanitize

    Returns:
        str: Sanitized username

    Example:
        clean_username = sanitize_username('John Doe!')
        # Returns: 'JohnDoe'
    """
    # Remove spaces and special characters except underscore and hyphen
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', username)

    # Ensure it starts with alphanumeric
    sanitized = re.sub(r'^[^a-zA-Z0-9]+', '', sanitized)

    # Limit length
    sanitized = sanitized[:150]

    return sanitized


def get_password_strength_score(password):
    """
    Calculate a password strength score (0-5).

    Score criteria:
    - 0: Empty or very weak
    - 1: Weak (< 8 chars)
    - 2: Fair (8+ chars, but missing some requirements)
    - 3: Good (meets basic requirements)
    - 4: Strong (longer and diverse)
    - 5: Very strong (12+ chars with high entropy)

    Args:
        password (str): Password to score

    Returns:
        int: Strength score (0-5)

    Example:
        score = get_password_strength_score('MySecurePassword123!')
        # Returns: 4 or 5
    """
    if not password:
        return 0

    score = 0
    length = len(password)

    # Length scoring
    if length >= 8:
        score += 1
    if length >= 12:
        score += 1
    if length >= 16:
        score += 1

    # Character diversity scoring
    if re.search(r'[a-z]', password):
        score += 0.5
    if re.search(r'[A-Z]', password):
        score += 0.5
    if re.search(r'[0-9]', password):
        score += 0.5
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        score += 0.5

    # Round to integer
    score = int(round(score))

    # Cap at 5
    return min(score, 5)


def format_validation_errors(errors):
    """
    Format a list of validation errors into a single string.

    Args:
        errors (list): List of error messages

    Returns:
        str: Formatted error string

    Example:
        errors = ['Error 1', 'Error 2']
        message = format_validation_errors(errors)
        # Returns: '• Error 1\n• Error 2'
    """
    if not errors:
        return ''

    return '\n'.join(f'• {error}' for error in errors)


def is_password_compromised(password):
    """
    Check if a password appears in common breach lists.

    Note: This is a basic implementation. For production, consider using
    a service like Have I Been Pwned API.

    Args:
        password (str): Password to check

    Returns:
        bool: True if password is known to be compromised

    Example:
        if is_password_compromised('password123'):
            print('Password has been compromised!')
    """
    # Basic check against common passwords
    # In production, you would integrate with HIBP API
    common_passwords = [
        'password', 'password123', '12345678', 'qwerty', 'abc123',
        'password1', '123456789', '12345', '1234567890', 'letmein',
        'welcome', 'monkey', '1234567', 'password1234', 'admin'
    ]

    return password.lower() in common_passwords


def mask_email(email):
    """
    Mask an email address for display (privacy).

    Args:
        email (str): Email address to mask

    Returns:
        str: Masked email address

    Example:
        masked = mask_email('user@example.com')
        # Returns: 'u***@example.com'
    """
    if not email or '@' not in email:
        return email

    local, domain = email.split('@', 1)

    if len(local) <= 2:
        masked_local = local[0] + '*'
    else:
        masked_local = local[0] + '*' * (len(local) - 1)

    return f"{masked_local}@{domain}"


def get_client_ip(request):
    """
    Get the client's IP address from the request, handling proxies.

    Args:
        request: Django request object

    Returns:
        str: IP address

    Example:
        ip = get_client_ip(request)
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')

    return ip


def get_user_agent(request):
    """
    Get the user agent string from the request.

    Args:
        request: Django request object

    Returns:
        str: User agent string

    Example:
        user_agent = get_user_agent(request)
    """
    return request.META.get('HTTP_USER_AGENT', '')
