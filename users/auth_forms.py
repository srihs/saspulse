"""
Authentication forms for the SasPulse custom authentication system.

This module provides Django forms for user authentication operations including
login, registration, password reset, and profile management.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
import re
from .models import CustomUser


class LoginForm(forms.Form):
    """
    Form for user login.
    Accepts username or email for authentication.
    """
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username or Email',
            'autofocus': True
        }),
        label='Username or Email'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        }),
        label='Password'
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'remember-me'
        }),
        label='Remember me'
    )


class RegisterForm(forms.Form):
    """
    Form for user registration.
    Validates username uniqueness, email uniqueness, password strength, and terms acceptance.
    """
    username = forms.CharField(
        max_length=150,
        min_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username',
            'autofocus': True
        }),
        label='Username',
        help_text='3-150 characters. Letters, digits and @/./+/-/_ only.'
    )
    email = forms.EmailField(
        validators=[EmailValidator()],
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address'
        }),
        label='Email'
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        }),
        label='First Name'
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        }),
        label='Last Name'
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        }),
        label='Password',
        help_text='Minimum 8 characters with uppercase, lowercase, number, and special character.'
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        }),
        label='Confirm Password'
    )
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'terms-accepted'
        }),
        label='I accept the Terms and Conditions',
        error_messages={
            'required': 'You must accept the terms and conditions to register.'
        }
    )

    def clean_username(self):
        """Validate username uniqueness and format."""
        username = self.cleaned_data.get('username')

        # Check format
        if not re.match(r'^[\w.@+-]+$', username):
            raise ValidationError(
                'Username can only contain letters, numbers, and @/./+/-/_ characters.'
            )

        # Check uniqueness
        if CustomUser.objects.filter(username=username).exists():
            raise ValidationError('This username is already taken.')

        return username

    def clean_email(self):
        """Validate email uniqueness."""
        email = self.cleaned_data.get('email')

        # Check uniqueness
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError('This email address is already registered.')

        return email.lower()

    def clean_password(self):
        """Validate password strength."""
        password = self.cleaned_data.get('password')

        # Check minimum length
        if len(password) < 8:
            raise ValidationError('Password must be at least 8 characters long.')

        # Check for uppercase letter
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')

        # Check for lowercase letter
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')

        # Check for digit
        if not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one number.')

        # Check for special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one special character.')

        return password

    def clean(self):
        """Validate that passwords match."""
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise ValidationError({
                'password_confirm': 'Passwords do not match.'
            })

        return cleaned_data


class ForgotPasswordForm(forms.Form):
    """
    Form for requesting a password reset.
    Validates that the email exists in the system.
    """
    email = forms.EmailField(
        validators=[EmailValidator()],
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autofocus': True
        }),
        label='Email Address'
    )

    def clean_email(self):
        """Validate that the email exists."""
        email = self.cleaned_data.get('email')

        if not CustomUser.objects.filter(email=email).exists():
            raise ValidationError(
                'No account found with this email address.'
            )

        return email.lower()


class ResetPasswordForm(forms.Form):
    """
    Form for resetting password with a token.
    Validates password strength and confirmation.
    """
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New password',
            'autofocus': True
        }),
        label='New Password',
        help_text='Minimum 8 characters with uppercase, lowercase, number, and special character.'
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        }),
        label='Confirm New Password'
    )

    def clean_password(self):
        """Validate password strength."""
        password = self.cleaned_data.get('password')

        # Check minimum length
        if len(password) < 8:
            raise ValidationError('Password must be at least 8 characters long.')

        # Check for uppercase letter
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')

        # Check for lowercase letter
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')

        # Check for digit
        if not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one number.')

        # Check for special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one special character.')

        return password

    def clean(self):
        """Validate that passwords match."""
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise ValidationError({
                'password_confirm': 'Passwords do not match.'
            })

        return cleaned_data


class ChangePasswordForm(forms.Form):
    """
    Form for changing password (authenticated users).
    Validates old password and ensures new password is different.
    """
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Current password',
            'autofocus': True
        }),
        label='Current Password'
    )
    new_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New password'
        }),
        label='New Password',
        help_text='Minimum 8 characters with uppercase, lowercase, number, and special character.'
    )
    new_password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        }),
        label='Confirm New Password'
    )

    def __init__(self, user, *args, **kwargs):
        """Initialize form with user instance for validation."""
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        """Validate that old password is correct."""
        old_password = self.cleaned_data.get('old_password')

        if not self.user.check_password(old_password):
            raise ValidationError('Current password is incorrect.')

        return old_password

    def clean_new_password(self):
        """Validate new password strength."""
        new_password = self.cleaned_data.get('new_password')

        # Check minimum length
        if len(new_password) < 8:
            raise ValidationError('Password must be at least 8 characters long.')

        # Check for uppercase letter
        if not re.search(r'[A-Z]', new_password):
            raise ValidationError('Password must contain at least one uppercase letter.')

        # Check for lowercase letter
        if not re.search(r'[a-z]', new_password):
            raise ValidationError('Password must contain at least one lowercase letter.')

        # Check for digit
        if not re.search(r'\d', new_password):
            raise ValidationError('Password must contain at least one number.')

        # Check for special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            raise ValidationError('Password must contain at least one special character.')

        return new_password

    def clean(self):
        """Validate that passwords match and new password is different."""
        cleaned_data = super().clean()
        old_password = cleaned_data.get('old_password')
        new_password = cleaned_data.get('new_password')
        new_password_confirm = cleaned_data.get('new_password_confirm')

        # Check that passwords match
        if new_password and new_password_confirm and new_password != new_password_confirm:
            raise ValidationError({
                'new_password_confirm': 'Passwords do not match.'
            })

        # Check that new password is different from old password
        if old_password and new_password and old_password == new_password:
            raise ValidationError({
                'new_password': 'New password must be different from current password.'
            })

        return cleaned_data


class ProfileForm(forms.ModelForm):
    """
    Form for editing user profile information.
    Excludes sensitive fields like password and tokens.
    """
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone_number', 'department', 'job_title', 'bio']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Department'
            }),
            'job_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Job title'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Brief bio or notes',
                'rows': 4
            }),
        }
        labels = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'phone_number': 'Phone Number',
            'department': 'Department',
            'job_title': 'Job Title',
            'bio': 'Bio'
        }

    def clean_phone_number(self):
        """Basic phone number validation."""
        phone = self.cleaned_data.get('phone_number')

        if phone:
            # Remove common formatting characters
            phone_digits = re.sub(r'[\s\-\(\)\+]', '', phone)

            # Check if it contains only digits
            if not phone_digits.isdigit():
                raise ValidationError('Phone number can only contain digits and formatting characters.')

            # Check reasonable length (7-15 digits)
            if len(phone_digits) < 7 or len(phone_digits) > 15:
                raise ValidationError('Phone number must be between 7 and 15 digits.')

        return phone
