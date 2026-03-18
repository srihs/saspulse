from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, Role
from cin7.models import Branch, Product
import json


class RoleForm(forms.ModelForm):
    """
    Form for creating and editing roles.
    Uses individual checkboxes for a user-friendly permissions interface.
    """
    # Dashboard permissions
    perm_dashboard_view = forms.BooleanField(
        required=False,
        label='View Dashboard',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_dashboard_export = forms.BooleanField(
        required=False,
        label='Export Dashboard Data',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Forecasting permissions
    perm_forecasting_view = forms.BooleanField(
        required=False,
        label='View Forecasts',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_forecasting_edit = forms.BooleanField(
        required=False,
        label='Edit Forecasts',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_forecasting_export = forms.BooleanField(
        required=False,
        label='Export Forecasts',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Replenishment - Stores permissions
    perm_replenishment_stores_view = forms.BooleanField(
        required=False,
        label='View Store Requests',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_replenishment_stores_review = forms.BooleanField(
        required=False,
        label='Review Store Requests',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_replenishment_stores_create = forms.BooleanField(
        required=False,
        label='Create Store Requests',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_replenishment_stores_edit = forms.BooleanField(
        required=False,
        label='Edit Store Requests',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_replenishment_stores_submit = forms.BooleanField(
        required=False,
        label='Submit Store Requests',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Replenishment - Demand Planning permissions
    perm_replenishment_demand_view = forms.BooleanField(
        required=False,
        label='View Demand Planning',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_replenishment_demand_approve = forms.BooleanField(
        required=False,
        label='Approve Requests',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_replenishment_demand_reject = forms.BooleanField(
        required=False,
        label='Reject Requests',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_replenishment_demand_view_all = forms.BooleanField(
        required=False,
        label='View All Requests',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Replenishment - Daily Pick List permissions
    perm_replenishment_picklist_view = forms.BooleanField(
        required=False,
        label='View Daily Pick List',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_replenishment_picklist_export = forms.BooleanField(
        required=False,
        label='Export Daily Pick List',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Admin - Users permissions
    perm_admin_users_view = forms.BooleanField(
        required=False,
        label='View Users',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_admin_users_create = forms.BooleanField(
        required=False,
        label='Create Users',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_admin_users_edit = forms.BooleanField(
        required=False,
        label='Edit Users',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_admin_users_delete = forms.BooleanField(
        required=False,
        label='Delete Users',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Admin - Roles permissions
    perm_admin_roles_view = forms.BooleanField(
        required=False,
        label='View Roles',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_admin_roles_create = forms.BooleanField(
        required=False,
        label='Create Roles',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_admin_roles_edit = forms.BooleanField(
        required=False,
        label='Edit Roles',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_admin_roles_delete = forms.BooleanField(
        required=False,
        label='Delete Roles',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Admin - Settings permissions
    perm_admin_settings_view = forms.BooleanField(
        required=False,
        label='View Settings',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    perm_admin_settings_edit = forms.BooleanField(
        required=False,
        label='Edit Settings',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Data Scope
    data_scope = forms.ChoiceField(
        required=False,
        label='Data Access Scope',
        choices=[
            ('all', 'All Data (No Restrictions)'),
            ('branch', 'Branch Level (Store Managers)'),
            ('school', 'School Level (Sales Team)'),
            ('store', 'Store Level (Store-School Mapping)')
        ],
        initial='all',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Role
        fields = ['name', 'description', 'is_active']
        exclude = ['permissions']  # Exclude the model's permissions field
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
            # Pre-populate checkboxes from existing permissions JSON
            perms = self.instance.permissions

            # Dashboard
            self.fields['perm_dashboard_view'].initial = perms.get('dashboard', {}).get('view', False)
            self.fields['perm_dashboard_export'].initial = perms.get('dashboard', {}).get('export', False)

            # Forecasting
            self.fields['perm_forecasting_view'].initial = perms.get('forecasting', {}).get('view', False)
            self.fields['perm_forecasting_edit'].initial = perms.get('forecasting', {}).get('edit', False)
            self.fields['perm_forecasting_export'].initial = perms.get('forecasting', {}).get('export', False)

            # Replenishment - Stores
            stores = perms.get('replenishment', {}).get('stores', {})
            self.fields['perm_replenishment_stores_view'].initial = stores.get('view', False)
            self.fields['perm_replenishment_stores_review'].initial = stores.get('review', False)
            self.fields['perm_replenishment_stores_create'].initial = stores.get('create_request', False)
            self.fields['perm_replenishment_stores_edit'].initial = stores.get('edit_request', False)
            self.fields['perm_replenishment_stores_submit'].initial = stores.get('submit_request', False)

            # Replenishment - Demand Planning
            demand = perms.get('replenishment', {}).get('demand_planning', {})
            self.fields['perm_replenishment_demand_view'].initial = demand.get('view', False)
            self.fields['perm_replenishment_demand_approve'].initial = demand.get('approve', False)
            self.fields['perm_replenishment_demand_reject'].initial = demand.get('reject', False)
            self.fields['perm_replenishment_demand_view_all'].initial = demand.get('view_all_requests', False)

            # Replenishment - Pick List
            picklist = perms.get('replenishment', {}).get('daily_pick_list', {})
            self.fields['perm_replenishment_picklist_view'].initial = picklist.get('view', False)
            self.fields['perm_replenishment_picklist_export'].initial = picklist.get('export', False)

            # Admin - Users
            users = perms.get('admin', {}).get('users', {})
            self.fields['perm_admin_users_view'].initial = users.get('view', False)
            self.fields['perm_admin_users_create'].initial = users.get('create', False)
            self.fields['perm_admin_users_edit'].initial = users.get('edit', False)
            self.fields['perm_admin_users_delete'].initial = users.get('delete', False)

            # Admin - Roles
            roles = perms.get('admin', {}).get('roles', {})
            self.fields['perm_admin_roles_view'].initial = roles.get('view', False)
            self.fields['perm_admin_roles_create'].initial = roles.get('create', False)
            self.fields['perm_admin_roles_edit'].initial = roles.get('edit', False)
            self.fields['perm_admin_roles_delete'].initial = roles.get('delete', False)

            # Admin - Settings
            settings = perms.get('admin', {}).get('settings', {})
            self.fields['perm_admin_settings_view'].initial = settings.get('view', False)
            self.fields['perm_admin_settings_edit'].initial = settings.get('edit', False)

            # Data Scope
            self.fields['data_scope'].initial = perms.get('data_scope', {}).get('type', 'all')

    def save(self, commit=True):
        """
        Override save to construct permissions JSON from checkbox values.
        """
        instance = super().save(commit=False)

        # Build permissions JSON from form fields
        cd = self.cleaned_data

        instance.permissions = {
            'dashboard': {
                'view': cd.get('perm_dashboard_view', False),
                'export': cd.get('perm_dashboard_export', False)
            },
            'forecasting': {
                'view': cd.get('perm_forecasting_view', False),
                'edit': cd.get('perm_forecasting_edit', False),
                'export': cd.get('perm_forecasting_export', False)
            },
            'replenishment': {
                'stores': {
                    'view': cd.get('perm_replenishment_stores_view', False),
                    'review': cd.get('perm_replenishment_stores_review', False),
                    'create_request': cd.get('perm_replenishment_stores_create', False),
                    'edit_request': cd.get('perm_replenishment_stores_edit', False),
                    'submit_request': cd.get('perm_replenishment_stores_submit', False)
                },
                'demand_planning': {
                    'view': cd.get('perm_replenishment_demand_view', False),
                    'approve': cd.get('perm_replenishment_demand_approve', False),
                    'reject': cd.get('perm_replenishment_demand_reject', False),
                    'view_all_requests': cd.get('perm_replenishment_demand_view_all', False)
                },
                'daily_pick_list': {
                    'view': cd.get('perm_replenishment_picklist_view', False),
                    'export': cd.get('perm_replenishment_picklist_export', False)
                }
            },
            'admin': {
                'users': {
                    'view': cd.get('perm_admin_users_view', False),
                    'create': cd.get('perm_admin_users_create', False),
                    'edit': cd.get('perm_admin_users_edit', False),
                    'delete': cd.get('perm_admin_users_delete', False)
                },
                'roles': {
                    'view': cd.get('perm_admin_roles_view', False),
                    'create': cd.get('perm_admin_roles_create', False),
                    'edit': cd.get('perm_admin_roles_edit', False),
                    'delete': cd.get('perm_admin_roles_delete', False)
                },
                'settings': {
                    'view': cd.get('perm_admin_settings_view', False),
                    'edit': cd.get('perm_admin_settings_edit', False)
                }
            },
            'data_scope': {
                'type': cd.get('data_scope', 'all'),
                'filter_required': cd.get('data_scope', 'all') != 'all'
            }
        }

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
    Includes all user fields, roles, branches, schools, and stores.
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

    # Store assignment (from StoreSchoolMapping)
    assigned_stores = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input store-checkbox'
        }),
        required=False,
        label='Assigned Stores',
        help_text='Select stores for store-level data access (via StoreSchoolMapping)'
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

        # Populate store choices from StoreSchoolMapping
        store_choices = self._get_store_choices()
        self.fields['assigned_stores'].choices = store_choices

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

    def _get_store_choices(self):
        """
        Get unique store choices from StoreSchoolMapping.
        Returns a list of tuples (value, display_name) - value is store_name.
        """
        try:
            from dashboard.models import StoreSchoolMapping

            # Get distinct active store names
            stores = StoreSchoolMapping.objects.filter(
                is_active=True
            ).values_list('store_name', flat=True).distinct().order_by('store_name')

            return [(store, store) for store in stores]
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

            # Stores (convert store names to StoreSchoolMapping instances)
            if 'assigned_stores' in self.cleaned_data:
                selected_stores = self.cleaned_data['assigned_stores']
                if selected_stores:
                    from dashboard.models import StoreSchoolMapping
                    # Get StoreSchoolMapping objects matching selected store names
                    store_mappings = StoreSchoolMapping.objects.filter(
                        store_name__in=selected_stores,
                        is_active=True
                    ).distinct()
                    user.assigned_stores.set(store_mappings)
                else:
                    user.assigned_stores.clear()

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

    # Store assignment (from StoreSchoolMapping)
    assigned_stores = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input store-checkbox'
        }),
        required=False,
        label='Assigned Stores',
        help_text='Select stores for store-level data access (via StoreSchoolMapping)'
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

        # Populate store choices from StoreSchoolMapping
        store_choices = self._get_store_choices()
        self.fields['assigned_stores'].choices = store_choices

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

            # Pre-select current stores (get store names from assigned stores)
            try:
                current_store_names = list(
                    self.instance.assigned_stores.filter(is_active=True).values_list('store_name', flat=True).distinct()
                )
                self.fields['assigned_stores'].initial = current_store_names
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

    def _get_store_choices(self):
        """
        Get unique store choices from StoreSchoolMapping.
        Returns a list of tuples (value, display_name) - value is store_name.
        """
        try:
            from dashboard.models import StoreSchoolMapping

            # Get distinct active store names
            stores = StoreSchoolMapping.objects.filter(
                is_active=True
            ).values_list('store_name', flat=True).distinct().order_by('store_name')

            return [(store, store) for store in stores]
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

            # Stores (convert store names to StoreSchoolMapping instances)
            if 'assigned_stores' in self.cleaned_data:
                selected_stores = self.cleaned_data['assigned_stores']
                if selected_stores:
                    from dashboard.models import StoreSchoolMapping
                    # Get StoreSchoolMapping objects matching selected store names
                    store_mappings = StoreSchoolMapping.objects.filter(
                        store_name__in=selected_stores,
                        is_active=True
                    ).distinct()
                    user.assigned_stores.set(store_mappings)
                else:
                    # Clear all stores if none selected
                    user.assigned_stores.clear()

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


class ProfileEditForm(forms.ModelForm):
    """
    Form for users to edit their own profile information.
    Only allows editing of personal fields, not sensitive or admin-managed fields.
    """
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone_number', 'department', 'job_title', 'bio']
        widgets = {
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
                'placeholder': 'e.g., +64 21 123 4567'
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
                'placeholder': 'Brief description about yourself',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make first and last name required
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

    def clean_phone_number(self):
        """Basic phone number validation."""
        phone = self.cleaned_data.get('phone_number')

        if phone:
            # Remove common formatting characters
            import re
            phone_digits = re.sub(r'[\s\-\(\)\+]', '', phone)

            # Check if it contains only digits
            if not phone_digits.isdigit():
                raise forms.ValidationError('Phone number can only contain digits and formatting characters.')

            # Check reasonable length (7-15 digits)
            if len(phone_digits) < 7 or len(phone_digits) > 15:
                raise forms.ValidationError('Phone number must be between 7 and 15 digits.')

        return phone


class PriorityScoreSettingsForm(forms.ModelForm):
    """
    Form for configuring Priority Score calculation parameters.
    Validates threshold ordering and provides Bootstrap styling.
    """
    class Meta:
        from dashboard.models import PriorityScoreSettings

        model = PriorityScoreSettings
        fields = [
            'critical_risk_days', 'critical_risk_score',
            'high_risk_days', 'high_risk_score',
            'medium_risk_days', 'medium_risk_score',
            'low_risk_score',
            'top_customer_count', 'top_customer_weight',
            'high_velocity_weight'
        ]
        widgets = {
            'critical_risk_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'critical_risk_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'high_risk_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'high_risk_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'medium_risk_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'medium_risk_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'low_risk_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'top_customer_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'top_customer_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'high_velocity_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def clean(self):
        """
        Validate threshold ordering to ensure logical risk levels.
        Critical < High < Medium in terms of days.
        """
        cleaned_data = super().clean()
        critical_days = cleaned_data.get('critical_risk_days')
        high_days = cleaned_data.get('high_risk_days')
        medium_days = cleaned_data.get('medium_risk_days')

        # Validate threshold ordering
        if critical_days and high_days and critical_days >= high_days:
            raise forms.ValidationError('Critical risk days must be less than high risk days')

        if high_days and medium_days and high_days >= medium_days:
            raise forms.ValidationError('High risk days must be less than medium risk days')

        return cleaned_data
