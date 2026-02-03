from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import Role  # UserProfile commented out - using CustomUser now
import json


class RoleForm(forms.ModelForm):
    """
    Form for creating and editing roles.
    Includes custom validation for the permissions JSON field.
    """
    permissions_json = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 10,
            'class': 'form-control',
            'placeholder': 'Enter permissions as JSON, e.g., {"can_edit": true, "can_delete": false}'
        }),
        required=False,
        label='Permissions (JSON)',
        help_text='Enter permissions as valid JSON. Example: {"can_view": true, "can_edit": false}'
    )

    class Meta:
        model = Role
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter role name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter role description'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Pre-populate the JSON field with formatted JSON
            self.fields['permissions_json'].initial = json.dumps(
                self.instance.permissions,
                indent=2
            )

    def clean_permissions_json(self):
        """
        Validate that the permissions field contains valid JSON.
        """
        permissions_str = self.cleaned_data.get('permissions_json', '').strip()

        if not permissions_str:
            return {}

        try:
            permissions = json.loads(permissions_str)
            if not isinstance(permissions, dict):
                raise forms.ValidationError(
                    'Permissions must be a JSON object (dictionary).'
                )
            return permissions
        except json.JSONDecodeError as e:
            raise forms.ValidationError(
                f'Invalid JSON format: {str(e)}'
            )

    def save(self, commit=True):
        """
        Override save to handle the permissions JSON field.
        """
        instance = super().save(commit=False)
        instance.permissions = self.cleaned_data.get('permissions_json', {})

        if commit:
            instance.save()
        return instance


# Commented out - UserProfile no longer exists, using CustomUser
# class UserProfileForm(forms.ModelForm):
#     """
#     Form for editing user profile information.
#     """
#     class Meta:
#         model = UserProfile
#         fields = ['phone_number', 'department', 'job_title', 'bio']
#         widgets = {
#             'phone_number': forms.TextInput(attrs={
#                 'class': 'form-control',
#                 'placeholder': 'Enter phone number'
#             }),
#             'department': forms.TextInput(attrs={
#                 'class': 'form-control',
#                 'placeholder': 'Enter department'
#             }),
#             'job_title': forms.TextInput(attrs={
#                 'class': 'form-control',
#                 'placeholder': 'Enter job title'
#             }),
#             'bio': forms.Textarea(attrs={
#                 'class': 'form-control',
#                 'rows': 4,
#                 'placeholder': 'Enter biography or notes'
#             }),
#         }


class UserCreateForm(UserCreationForm):
    """
    Form for creating new users with extended fields.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
    )
    first_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter first name'
        })
    )
    last_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter last name'
        })
    )
    phone_number = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter phone number'
        })
    )
    department = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter department'
        })
    )
    job_title = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter job title'
        })
    )
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter biography or notes'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name',
                  'password1', 'password2', 'is_active', 'is_staff']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter username'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_staff': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })

    def save(self, commit=True):
        """
        Save the user and update their profile with additional fields.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        if commit:
            user.save()
            # Update or create profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.phone_number = self.cleaned_data.get('phone_number', '')
            profile.department = self.cleaned_data.get('department', '')
            profile.job_title = self.cleaned_data.get('job_title', '')
            profile.bio = self.cleaned_data.get('bio', '')
            profile.save()

        return user


class UserUpdateForm(UserChangeForm):
    """
    Form for updating existing users.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
    )
    first_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter first name'
        })
    )
    last_name = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter last name'
        })
    )
    phone_number = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter phone number'
        })
    )
    department = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter department'
        })
    )
    job_title = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter job title'
        })
    )
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter biography or notes'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name',
                  'is_active', 'is_staff', 'is_superuser']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter username'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_staff': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_superuser': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the password field from the form
        if 'password' in self.fields:
            del self.fields['password']

        # Pre-populate profile fields
        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'profile'):
                profile = self.instance.profile
                self.fields['phone_number'].initial = profile.phone_number
                self.fields['department'].initial = profile.department
                self.fields['job_title'].initial = profile.job_title
                self.fields['bio'].initial = profile.bio

    def save(self, commit=True):
        """
        Save the user and update their profile with additional fields.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        if commit:
            user.save()
            # Update or create profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.phone_number = self.cleaned_data.get('phone_number', '')
            profile.department = self.cleaned_data.get('department', '')
            profile.job_title = self.cleaned_data.get('job_title', '')
            profile.bio = self.cleaned_data.get('bio', '')
            profile.save()

        return user


class UserRolesForm(forms.Form):
    """
    Form for assigning roles to users.
    """
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        required=False,
        label='Assign Roles',
        help_text='Select one or more roles to assign to this user'
    )

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user and hasattr(user, 'profile'):
            # Pre-select current roles
            self.fields['roles'].initial = user.profile.roles.all()

    def save(self):
        """
        Save the role assignments for the user.
        """
        if self.user and hasattr(self.user, 'profile'):
            profile = self.user.profile
            profile.roles.set(self.cleaned_data['roles'])
            return profile
        return None
