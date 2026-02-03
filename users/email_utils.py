"""
Email and token handling utilities for authentication.

This module provides email sending functionality for authentication operations.
For development, tokens are logged to console instead of being sent via email.
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_activation_email(user, activation_token):
    """
    Send account activation email to user.

    For development: Prints token to console instead of sending email.

    Args:
        user (CustomUser): User object
        activation_token (str): Generated activation token

    Returns:
        bool: True if successful
    """
    activation_url = f"{settings.SITE_URL}/system/auth/activate/{activation_token}/"

    # Log for development
    logger.info("=" * 80)
    logger.info("ACTIVATION EMAIL")
    logger.info("=" * 80)
    logger.info(f"To: {user.email}")
    logger.info(f"Subject: Activate your SasPulse account")
    logger.info(f"Username: {user.username}")
    logger.info(f"Activation Token: {activation_token}")
    logger.info(f"Activation URL: {activation_url}")
    logger.info("=" * 80)

    # TODO: Implement actual email sending in production
    # Example:
    # send_mail(
    #     subject='Activate your SasPulse account',
    #     message=f'Click here to activate: {activation_url}',
    #     from_email=settings.DEFAULT_FROM_EMAIL,
    #     recipient_list=[user.email],
    #     fail_silently=False,
    # )

    return True


def send_password_reset_email(user, reset_token):
    """
    Send password reset email to user.

    For development: Prints token to console instead of sending email.

    Args:
        user (CustomUser): User object
        reset_token (str): Generated reset token

    Returns:
        bool: True if successful
    """
    reset_url = f"{settings.SITE_URL}/system/auth/reset-password/{reset_token}/"

    # Log for development
    logger.info("=" * 80)
    logger.info("PASSWORD RESET EMAIL")
    logger.info("=" * 80)
    logger.info(f"To: {user.email}")
    logger.info(f"Subject: Reset your SasPulse password")
    logger.info(f"Username: {user.username}")
    logger.info(f"Reset Token: {reset_token}")
    logger.info(f"Reset URL: {reset_url}")
    logger.info("=" * 80)

    # TODO: Implement actual email sending in production
    # Example:
    # send_mail(
    #     subject='Reset your SasPulse password',
    #     message=f'Click here to reset: {reset_url}',
    #     from_email=settings.DEFAULT_FROM_EMAIL,
    #     recipient_list=[user.email],
    #     fail_silently=False,
    # )

    return True


def get_token_display_info(token_type, token):
    """
    Get token information for display in development mode.

    Args:
        token_type (str): 'activation' or 'reset'
        token (str): The token string

    Returns:
        dict: Token display information
    """
    if token_type == 'activation':
        url_path = f'/system/auth/activate/{token}/'
        title = 'Account Activation'
    elif token_type == 'reset':
        url_path = f'/system/auth/reset-password/{token}/'
        title = 'Password Reset'
    else:
        return None

    return {
        'title': title,
        'token': token,
        'url_path': url_path,
        'full_url': f"{settings.SITE_URL}{url_path}"
    }
