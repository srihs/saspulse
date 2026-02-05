"""
Authentication views for the SasPulse custom authentication system.

This module provides class-based views for all authentication operations including
login, logout, registration, account activation, password reset, and profile management.
"""

from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.urls import reverse

from .models import CustomUser, UserSession
from .auth_backend import auth_backend
from .auth_forms import (
    LoginForm, RegisterForm, ForgotPasswordForm,
    ResetPasswordForm, ChangePasswordForm, ProfileForm
)
from .email_utils import send_activation_email, send_password_reset_email


class LoginView(View):
    """
    Handle user login with email and password.
    Supports remember_me functionality and redirects to next parameter.
    """
    template_name = 'users/auth/login.html'

    def get(self, request):
        """Display login form."""
        # Redirect if already authenticated
        if auth_backend.is_authenticated(request):
            return redirect('dashboard:index')

        form = LoginForm()
        next_url = request.GET.get('next', '')

        return render(request, self.template_name, {
            'form': form,
            'next': next_url
        })

    def post(self, request):
        """Process login form submission."""
        form = LoginForm(request.POST)
        next_url = request.POST.get('next', '') or request.GET.get('next', '')

        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)

            # Authenticate user (pass email as username parameter)
            user = auth_backend.authenticate(request, username=email, password=password)

            if user is not None:
                # Check if user account is locked
                if user.is_locked():
                    minutes_left = int((user.locked_until - timezone.now()).total_seconds() / 60)
                    messages.error(
                        request,
                        f'Your account is locked due to multiple failed login attempts. '
                        f'Please try again in {minutes_left} minutes.'
                    )
                    return render(request, self.template_name, {
                        'form': form,
                        'next': next_url
                    })

                # Check if account is active
                if not user.is_active:
                    messages.error(
                        request,
                        'Your account is not active. Please check your email to activate your account.'
                    )
                    return render(request, self.template_name, {
                        'form': form,
                        'next': next_url
                    })

                # Login successful
                auth_backend.login(request, user, remember_me=remember_me)
                messages.success(request, f'Welcome back, {user.get_full_name()}!')

                # Redirect to next URL or dashboard
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect('dashboard:index')
            else:
                # Authentication failed
                messages.error(
                    request,
                    'Invalid username/email or password. Please try again.'
                )
        else:
            messages.error(request, 'Please correct the errors below.')

        return render(request, self.template_name, {
            'form': form,
            'next': next_url
        })


class LogoutView(View):
    """
    Handle user logout.
    POST only for security (CSRF protection).
    """
    def post(self, request):
        """Process logout request."""
        auth_backend.logout(request)
        messages.success(request, 'You have been successfully logged out.')
        return redirect('users:login')


class RegisterView(View):
    """
    Handle user registration.
    Creates a new user account and sends activation email.
    """
    template_name = 'users/auth/register.html'

    def get(self, request):
        """Display registration form."""
        # Redirect if already authenticated
        if auth_backend.is_authenticated(request):
            return redirect('dashboard:index')

        form = RegisterForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        """Process registration form submission."""
        form = RegisterForm(request.POST)

        if form.is_valid():
            # Create new user
            user = CustomUser(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                is_active=False,  # Require email activation
                email_verified=False
            )

            # Set password
            user.set_password(form.cleaned_data['password'])

            # Generate activation token
            activation_token = user.generate_activation_token()

            # Save user
            user.save()

            # Send activation email (logs to console in development)
            send_activation_email(user, activation_token)

            # Redirect to check email page
            messages.success(
                request,
                'Registration successful! Please check your email to activate your account.'
            )
            return redirect('users:check_email', email_type='activation')
        else:
            messages.error(request, 'Please correct the errors below.')

        return render(request, self.template_name, {'form': form})


class ActivateAccountView(View):
    """
    Handle account activation via email token.
    Validates token and activates the user account.
    """
    template_name = 'users/auth/activate.html'

    def get(self, request, token):
        """Process activation token."""
        try:
            # Find user by activation token
            user = CustomUser.objects.get(activation_token=token)

            # Check if already activated
            if user.is_active and user.email_verified:
                messages.info(request, 'Your account is already activated.')
                return redirect('users:login')

            # Activate account
            user.is_active = True
            user.email_verified = True
            user.activation_token = ''  # Clear token
            user.save(update_fields=['is_active', 'email_verified', 'activation_token'])

            messages.success(
                request,
                'Your account has been successfully activated! You can now log in.'
            )
            return render(request, self.template_name, {'success': True})

        except CustomUser.DoesNotExist:
            messages.error(
                request,
                'Invalid or expired activation link. Please request a new activation email.'
            )
            return render(request, self.template_name, {'success': False})


class ForgotPasswordView(View):
    """
    Handle forgot password request.
    Generates reset token and sends reset email.
    """
    template_name = 'users/auth/forgot_password.html'

    def get(self, request):
        """Display forgot password form."""
        # Redirect if already authenticated
        if auth_backend.is_authenticated(request):
            return redirect('dashboard:index')

        form = ForgotPasswordForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        """Process forgot password form submission."""
        form = ForgotPasswordForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data['email']

            try:
                user = CustomUser.objects.get(email=email)

                # Generate reset token (valid for 1 hour)
                reset_token = user.generate_reset_token(expiry_hours=1)

                # Send reset email (logs to console in development)
                send_password_reset_email(user, reset_token)

                messages.success(
                    request,
                    'Password reset instructions have been sent to your email.'
                )
                return redirect('users:check_email', email_type='reset')

            except CustomUser.DoesNotExist:
                # Don't reveal if email exists (security best practice)
                messages.success(
                    request,
                    'If an account exists with this email, you will receive reset instructions.'
                )
                return redirect('users:check_email', email_type='reset')
        else:
            messages.error(request, 'Please correct the errors below.')

        return render(request, self.template_name, {'form': form})


class ResetPasswordView(View):
    """
    Handle password reset with token.
    Validates token, sets new password, and invalidates all sessions.
    """
    template_name = 'users/auth/reset_password.html'

    def get(self, request, token):
        """Display reset password form."""
        # Validate token
        try:
            user = CustomUser.objects.get(
                reset_token=token,
                reset_token_expires__gt=timezone.now()
            )
            form = ResetPasswordForm()
            return render(request, self.template_name, {
                'form': form,
                'token': token,
                'valid': True
            })

        except CustomUser.DoesNotExist:
            messages.error(
                request,
                'Invalid or expired reset link. Please request a new password reset.'
            )
            return render(request, self.template_name, {'valid': False})

    def post(self, request, token):
        """Process password reset form submission."""
        # Validate token again
        try:
            user = CustomUser.objects.get(
                reset_token=token,
                reset_token_expires__gt=timezone.now()
            )
        except CustomUser.DoesNotExist:
            messages.error(
                request,
                'Invalid or expired reset link. Please request a new password reset.'
            )
            return render(request, self.template_name, {'valid': False})

        form = ResetPasswordForm(request.POST)

        if form.is_valid():
            # Set new password
            user.set_password(form.cleaned_data['password'])

            # Clear reset token
            user.reset_token = ''
            user.reset_token_expires = None
            user.save(update_fields=['reset_token', 'reset_token_expires'])

            # Invalidate all active sessions
            UserSession.objects.filter(user=user, is_active=True).update(is_active=False)

            messages.success(
                request,
                'Your password has been successfully reset. You can now log in with your new password.'
            )
            return redirect('users:login')
        else:
            messages.error(request, 'Please correct the errors below.')

        return render(request, self.template_name, {
            'form': form,
            'token': token,
            'valid': True
        })


class ChangePasswordView(View):
    """
    Handle password change for authenticated users.
    Requires old password verification.
    """
    template_name = 'users/auth/change_password.html'

    def get(self, request):
        """Display change password form."""
        # Check authentication
        user = auth_backend.get_user_from_session(request)
        if not user.is_authenticated:
            messages.error(request, 'Please log in to change your password.')
            return redirect('users:login')

        form = ChangePasswordForm(user=user)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        """Process change password form submission."""
        # Check authentication
        user = auth_backend.get_user_from_session(request)
        if not user.is_authenticated:
            messages.error(request, 'Please log in to change your password.')
            return redirect('users:login')

        form = ChangePasswordForm(user=user, data=request.POST)

        if form.is_valid():
            # Set new password
            user.set_password(form.cleaned_data['new_password'])

            messages.success(
                request,
                'Your password has been successfully changed.'
            )
            return redirect('users:profile')
        else:
            messages.error(request, 'Please correct the errors below.')

        return render(request, self.template_name, {'form': form})


class ProfileView(View):
    """
    Handle user profile viewing and editing.
    Displays user information, roles, and allows profile updates.
    """
    template_name = 'users/auth/profile.html'

    def get(self, request):
        """Display profile page."""
        # Check authentication
        user = auth_backend.get_user_from_session(request)
        if not user.is_authenticated:
            messages.error(request, 'Please log in to view your profile.')
            return redirect('users:login')

        form = ProfileForm(instance=user)

        # Get user's roles
        roles = user.roles.filter(is_active=True)

        # Get active sessions
        active_sessions = UserSession.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        ).order_by('-last_activity')

        return render(request, self.template_name, {
            'form': form,
            'user': user,
            'roles': roles,
            'active_sessions': active_sessions
        })

    def post(self, request):
        """Process profile update form submission."""
        # Check authentication
        user = auth_backend.get_user_from_session(request)
        if not user.is_authenticated:
            messages.error(request, 'Please log in to update your profile.')
            return redirect('users:login')

        form = ProfileForm(request.POST, instance=user)

        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been successfully updated.')
            return redirect('users:profile')
        else:
            messages.error(request, 'Please correct the errors below.')

        # Get user's roles for display
        roles = user.roles.filter(is_active=True)

        # Get active sessions
        active_sessions = UserSession.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        ).order_by('-last_activity')

        return render(request, self.template_name, {
            'form': form,
            'user': user,
            'roles': roles,
            'active_sessions': active_sessions
        })


class CheckEmailView(View):
    """
    Display a "check your email" message after registration or password reset.
    For development, displays the token for easy access.
    """
    template_name = 'users/auth/check_email.html'

    def get(self, request, email_type):
        """Display check email page."""
        if email_type not in ['activation', 'reset']:
            messages.error(request, 'Invalid email type.')
            return redirect('users:login')

        return render(request, self.template_name, {
            'email_type': email_type
        })
