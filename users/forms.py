from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, Role
from cin7.models import Branch, Product
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


class CustomUserCreateForm(forms.ModelForm):
    """
    Form for creating new users with CustomUser model.
    Includes all user fields, roles, branches, and schools.
    """
    # Password fields
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        }),
        help_text='Enter a strong password'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        }),
        help_text='Enter the same password again'
    )

    # Role assignment
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input role-checkbox'
        }),
        required=False,
        label='Roles',
        help_text='Select one or more roles for this user'
    )

    # Branch assignment (shop names from Product.category_name ending with 'Shop')
    assigned_branches = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input branch-checkbox'
        }),
        required=False,
        label='Assigned Branches',
        help_text='Select branches/shops for store managers (can have multiple)'
    )

    # School assignment (unique sub_category values from Product where category_name ends with 'Shop')
    assigned_schools = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input school-checkbox'
        }),
        required=False,
        label='Assigned Schools',
        help_text='Select schools for sales team members'
    )

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone_number', 'department', 'job_title', 'bio',
            'is_active', 'is_staff', 'is_superuser', 'email_verified'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter username'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter last name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter department'
            }),
            'job_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter job title'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter biography or notes'
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
            'email_verified': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make email and first_name/last_name required
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

        # Populate branch choices from Product.category_name ending with 'Shop'
        branch_choices = self._get_branch_choices()
        self.fields['assigned_branches'].choices = branch_choices

        # Populate school choices from Product.sub_category where category_name ends with 'Shop'
        school_choices = self._get_school_choices()
        self.fields['assigned_schools'].choices = school_choices

    def _get_branch_choices(self):
        """
        Get unique branch/shop choices from ProductCategory table where name ends with 'Shop'.
        Returns a list of tuples (value, display_name).
        """
        try:
            from cin7.models import ProductCategory

            # Get root categories (shops) where name ends with 'Shop'
            shops = ProductCategory.objects.filter(
                parent__isnull=True,
                name__iendswith='Shop'
            ).order_by('name').values_list('name', flat=True)

            return [(shop, shop) for shop in shops if shop]
        except Exception:
            # If there's an error (e.g., table doesn't exist), return empty list
            return []

    def _get_school_choices(self):
        """
        Get unique school choices from Product.sub_category field where category_name ends with 'Shop'.
        Returns a list of tuples (value, display_name).
        """
        try:
            schools = Product.objects.filter(
                category_name__endswith='Shop',
                sub_category__isnull=False
            ).exclude(
                sub_category=''
            ).values_list('sub_category', flat=True).distinct().order_by('sub_category')

            return [(school, school) for school in schools]
        except Exception:
            # If there's an error (e.g., table doesn't exist), return empty list
            return []

    def clean_password2(self):
        """
        Validate that the two password fields match.
        """
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")

        return password2

    def clean_email(self):
        """
        Validate that the email is unique.
        """
        email = self.cleaned_data.get('email')
        if email and CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_username(self):
        """
        Validate that the username is unique.
        """
        username = self.cleaned_data.get('username')
        if username and CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean(self):
        """
        Validate role-based assignments.
        """
        cleaned_data = super().clean()
        roles = cleaned_data.get('roles', [])
        assigned_schools = cleaned_data.get('assigned_schools', [])
        assigned_branches = cleaned_data.get('assigned_branches', [])

        # Get role names
        role_names = [role.name for role in roles]

        # Sales Team role validation
        if 'Sales Team' in role_names and not assigned_schools:
            self.add_error('assigned_schools', 'Sales Team users must have at least one school assigned.')

        # Store Manager role validation
        if 'Store Manager' in role_names and not assigned_branches:
            self.add_error('assigned_branches', 'Store Manager users must have at least one branch assigned.')

        return cleaned_data

    def save(self, commit=True):
        """
        Save the user with hashed password and M2M relationships.
        """
        user = super().save(commit=False)

        # Hash and set the password
        from django.contrib.auth.hashers import make_password
        user.password_hash = make_password(self.cleaned_data['password1'])

        if commit:
            user.save()

            # Save M2M relationships
            # Roles
            if 'roles' in self.cleaned_data:
                user.roles.set(self.cleaned_data['roles'])

            # Branches (convert branch names to Branch instances)
            if 'assigned_branches' in self.cleaned_data:
                selected_branches = self.cleaned_data['assigned_branches']
                if selected_branches:
                    # Find Branch objects matching the selected category names
                    branch_objects = Branch.objects.filter(name__in=selected_branches)
                    user.assigned_branches.set(branch_objects)
                else:
                    user.assigned_branches.clear()

            # Schools (convert sub_category values to Product instances)
            if 'assigned_schools' in self.cleaned_data:
                selected_schools = self.cleaned_data['assigned_schools']
                if selected_schools:
                    # Get distinct Product objects where sub_category matches selected schools
                    # and category_name ends with 'Shop'
                    school_products = Product.objects.filter(
                        category_name__endswith='Shop',
                        sub_category__in=selected_schools
                    ).distinct()
                    user.assigned_schools.set(school_products)
                else:
                    user.assigned_schools.clear()

        return user


class CustomUserUpdateForm(forms.ModelForm):
    """
    Form for updating existing users with CustomUser model.
    Does not include password fields (use separate password change form).
    """
    # Role assignment
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input role-checkbox'
        }),
        required=False,
        label='Roles',
        help_text='Select one or more roles for this user'
    )

    # Branch assignment (shop names from Product.category_name ending with 'Shop')
    assigned_branches = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input branch-checkbox'
        }),
        required=False,
        label='Assigned Branches',
        help_text='Select branches/shops for store managers (can have multiple)'
    )

    # School assignment (unique sub_category values from Product where category_name ends with 'Shop')
    assigned_schools = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input school-checkbox'
        }),
        required=False,
        label='Assigned Schools',
        help_text='Select schools for sales team members'
    )

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone_number', 'department', 'job_title', 'bio',
            'is_active', 'is_staff', 'is_superuser', 'email_verified'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter username'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter last name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter department'
            }),
            'job_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter job title'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter biography or notes'
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
            'email_verified': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make email and first_name/last_name required
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

        # Populate branch choices from Product.category_name ending with 'Shop'
        branch_choices = self._get_branch_choices()
        self.fields['assigned_branches'].choices = branch_choices

        # Populate school choices from Product.sub_category where category_name ends with 'Shop'
        school_choices = self._get_school_choices()
        self.fields['assigned_schools'].choices = school_choices

        # Pre-populate M2M fields if this is an existing user
        if self.instance and self.instance.pk:
            # Pre-select current roles
            self.fields['roles'].initial = self.instance.roles.all()

            # Pre-select current branches (get branch names from assigned branches)
            try:
                current_branch_names = list(
                    self.instance.assigned_branches.values_list('name', flat=True)
                )
                self.fields['assigned_branches'].initial = current_branch_names
            except Exception:
                pass

            # Pre-select current schools (get unique sub_category values)
            try:
                current_school_subcategories = list(
                    self.instance.assigned_schools.values_list('sub_category', flat=True).distinct()
                )
                self.fields['assigned_schools'].initial = current_school_subcategories
            except Exception:
                pass

    def _get_branch_choices(self):
        """
        Get unique branch/shop choices from ProductCategory table where name ends with 'Shop'.
        Returns a list of tuples (value, display_name).
        """
        try:
            from cin7.models import ProductCategory

            # Get root categories (shops) where name ends with 'Shop'
            shops = ProductCategory.objects.filter(
                parent__isnull=True,
                name__iendswith='Shop'
            ).order_by('name').values_list('name', flat=True)

            return [(shop, shop) for shop in shops if shop]
        except Exception:
            # If there's an error (e.g., table doesn't exist), return empty list
            return []

    def _get_school_choices(self):
        """
        Get unique school choices from Product.sub_category field where category_name ends with 'Shop'.
        Returns a list of tuples (value, display_name).
        """
        try:
            schools = Product.objects.filter(
                category_name__endswith='Shop',
                sub_category__isnull=False
            ).exclude(
                sub_category=''
            ).values_list('sub_category', flat=True).distinct().order_by('sub_category')

            return [(school, school) for school in schools]
        except Exception:
            # If there's an error (e.g., table doesn't exist), return empty list
            return []

    def clean_email(self):
        """
        Validate that the email is unique (excluding current instance).
        """
        email = self.cleaned_data.get('email')
        if email:
            # Exclude current instance from the query
            qs = CustomUser.objects.filter(email=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_username(self):
        """
        Validate that the username is unique (excluding current instance).
        """
        username = self.cleaned_data.get('username')
        if username:
            # Exclude current instance from the query
            qs = CustomUser.objects.filter(username=username)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean(self):
        """
        Validate role-based assignments.
        """
        cleaned_data = super().clean()
        roles = cleaned_data.get('roles', [])
        assigned_schools = cleaned_data.get('assigned_schools', [])
        assigned_branches = cleaned_data.get('assigned_branches', [])

        # Get role names
        role_names = [role.name for role in roles]

        # Sales Team role validation
        if 'Sales Team' in role_names and not assigned_schools:
            self.add_error('assigned_schools', 'Sales Team users must have at least one school assigned.')

        # Store Manager role validation
        if 'Store Manager' in role_names and not assigned_branches:
            self.add_error('assigned_branches', 'Store Manager users must have at least one branch assigned.')

        return cleaned_data

    def save(self, commit=True):
        """
        Save the user and update M2M relationships.
        """
        user = super().save(commit=commit)

        if commit:
            # Save M2M relationships
            # Roles
            if 'roles' in self.cleaned_data:
                user.roles.set(self.cleaned_data['roles'])

            # Branches (convert branch names to Branch instances)
            if 'assigned_branches' in self.cleaned_data:
                selected_branches = self.cleaned_data['assigned_branches']
                if selected_branches:
                    # Find Branch objects matching the selected category names
                    branch_objects = Branch.objects.filter(name__in=selected_branches)
                    user.assigned_branches.set(branch_objects)
                else:
                    # Clear all branches if none selected
                    user.assigned_branches.clear()

            # Schools (convert sub_category values to Product instances)
            if 'assigned_schools' in self.cleaned_data:
                selected_schools = self.cleaned_data['assigned_schools']
                if selected_schools:
                    # Get distinct Product objects where sub_category matches selected schools
                    # and category_name ends with 'Shop'
                    school_products = Product.objects.filter(
                        category_name__endswith='Shop',
                        sub_category__in=selected_schools
                    ).distinct()
                    user.assigned_schools.set(school_products)
                else:
                    # Clear all schools if none selected
                    user.assigned_schools.clear()

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
