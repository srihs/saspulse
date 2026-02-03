"""
Users app - Custom Authentication System

This app provides a complete custom authentication system independent
of Django's built-in auth.

Quick imports (use after Django is ready):
    from users.models import CustomUser
    from users.auth_backend import auth_backend
    from users.decorators import login_required, permission_required
    from users.utils import hash_password, validate_password_strength
"""

# Default app config
default_app_config = 'users.apps.UsersConfig'

# Version info
__version__ = '1.0.0'
__author__ = 'SasPulse Team'
