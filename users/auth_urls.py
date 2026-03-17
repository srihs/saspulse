"""
URL configuration for authentication views.

These URLs are prefixed with 'auth/' in the main saspulse urls.py:
- /auth/login/
- /auth/logout/
- /auth/register/
- etc.
"""

from django.urls import path
from . import auth_views

app_name = 'auth'

urlpatterns = [
    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', auth_views.RegisterView.as_view(), name='register'),

    # Account activation
    path('activate/<str:token>/', auth_views.ActivateAccountView.as_view(), name='activate'),

    # Password reset
    path('forgot-password/', auth_views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/<str:token>/', auth_views.ResetPasswordView.as_view(), name='reset_password'),

    # Check email (generic page for activation and reset)
    path('check-email/<str:email_type>/', auth_views.CheckEmailView.as_view(), name='check_email'),
]
