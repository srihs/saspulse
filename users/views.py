from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from datetime import date
from .models import CustomUser, Role
from .forms import RoleForm, CustomUserCreateForm, CustomUserUpdateForm, UserRolesForm, ProfileEditForm
from .auth_backend import auth_backend


# ==================== Permission Mixin ====================

class PermissionRequiredMixin:
    """Mixin to check RBAC permissions for class-based views"""
    permission_required = None  # Override in subclass

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('auth:login')

        if self.permission_required and not request.user.has_nested_permission(self.permission_required):
            raise PermissionDenied(f"You don't have permission: {self.permission_required}")

        return super().dispatch(request, *args, **kwargs)


# ==================== Role Views ====================

class RoleListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    permission_required = 'admin.users.view'
    """
    View to list all roles with search functionality.
    """
    model = Role
    template_name = 'users/role_list.html'
    context_object_name = 'roles'
    paginate_by = 20

    def get_queryset(self):
        queryset = Role.objects.all()
        search_query = self.request.GET.get('search', '')

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class RoleCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    permission_required = 'admin.users.create'
    """
    View to create a new role.
    """
    model = Role
    form_class = RoleForm
    template_name = 'users/role_form.html'
    success_url = reverse_lazy('users:role_list')

    def form_valid(self, form):
        messages.success(self.request, f'Role "{form.instance.name}" created successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Error creating role. Please check the form and try again.')
        return super().form_invalid(form)


class RoleUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    permission_required = 'admin.users.edit'
    """
    View to update an existing role.
    """
    model = Role
    form_class = RoleForm
    template_name = 'users/role_form.html'
    success_url = reverse_lazy('users:role_list')
    pk_url_kwarg = 'id'

    def form_valid(self, form):
        messages.success(self.request, f'Role "{form.instance.name}" updated successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Error updating role. Please check the form and try again.')
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True
        return context


class RoleDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    permission_required = 'admin.users.delete'
    """
    View to delete a role.
    """
    model = Role
    template_name = 'users/role_confirm_delete.html'
    success_url = reverse_lazy('users:role_list')
    pk_url_kwarg = 'id'

    def delete(self, request, *args, **kwargs):
        role = self.get_object()
        messages.success(request, f'Role "{role.name}" deleted successfully.')
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Count users with this role
        context['user_count'] = self.object.custom_users.count()
        return context


# ==================== User Views ====================

class UserListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    permission_required = 'admin.users.view'
    """
    View to list all users with search functionality.
    """
    model = CustomUser
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        queryset = CustomUser.objects.prefetch_related('roles', 'assigned_branches', 'assigned_schools')
        search_query = self.request.GET.get('search', '')

        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(department__icontains=search_query) |
                Q(job_title__icontains=search_query)
            )

        return queryset.order_by('username')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class UserCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    permission_required = 'admin.users.create'
    """
    View to create a new user.
    """
    model = CustomUser
    form_class = CustomUserCreateForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:user_list')

    def form_valid(self, form):
        messages.success(self.request, f'User "{form.instance.username}" created successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Error creating user. Please check the form and try again.')
        return super().form_invalid(form)


class UserUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    permission_required = 'admin.users.edit'
    """
    View to update an existing user.
    """
    model = CustomUser
    form_class = CustomUserUpdateForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:user_list')
    pk_url_kwarg = 'id'

    def form_valid(self, form):
        messages.success(self.request, f'User "{form.instance.username}" updated successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Error updating user. Please check the form and try again.')
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True
        return context


class UserDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    permission_required = 'admin.users.delete'
    """
    View to delete a user.
    """
    model = CustomUser
    template_name = 'users/user_confirm_delete.html'
    success_url = reverse_lazy('users:user_list')
    pk_url_kwarg = 'id'

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        username = user.username
        messages.success(request, f'User "{username}" deleted successfully.')
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get user's roles
        context['user_roles'] = self.object.roles.all()
        return context


class UserRolesView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = 'admin.users.edit'
    """
    View to manage role assignments for a user.
    """
    template_name = 'users/user_roles.html'

    def get(self, request, id):
        user = get_object_or_404(CustomUser, pk=id)
        form = UserRolesForm(user=user)

        context = {
            'user': user,
            'form': form,
            'current_roles': user.roles.all()
        }
        return render(request, self.template_name, context)

    def post(self, request, id):
        user = get_object_or_404(CustomUser, pk=id)
        form = UserRolesForm(user=user, data=request.POST)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Roles updated successfully for user "{user.username}".'
            )
            return redirect('users:user_list')
        else:
            messages.error(
                request,
                'Error updating roles. Please check the form and try again.'
            )

        context = {
            'user': user,
            'form': form,
            'current_roles': user.roles.all()
        }
        return render(request, self.template_name, context)


# ==================== Additional Helper Views ====================

class UserDetailView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = 'admin.users.view'
    """
    View to display detailed information about a user.
    This can be used as a quick overview before editing.
    """
    template_name = 'users/user_detail.html'

    def get(self, request, id):
        user = get_object_or_404(
            CustomUser.objects.prefetch_related('roles', 'assigned_branches', 'assigned_schools'),
            pk=id
        )

        context = {
            'user': user,
            'roles': user.roles.all(),
            'branches': user.assigned_branches.all(),
            'schools': user.assigned_schools.all(),
        }
        return render(request, self.template_name, context)


class RoleDetailView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = 'admin.users.view'
    """
    View to display detailed information about a role.
    Shows role details and users assigned to this role.
    """
    template_name = 'users/role_detail.html'

    def get(self, request, id):
        role = get_object_or_404(
            Role.objects.prefetch_related('custom_users'),
            pk=id
        )

        # Get all users with this role
        users_with_role = role.custom_users.all()

        context = {
            'role': role,
            'users_with_role': users_with_role,
            'user_count': users_with_role.count()
        }
        return render(request, self.template_name, context)


# ==================== User Profile Views (Self-Service) ====================

class UserProfileView(LoginRequiredMixin, View):
    """
    View for users to see their own profile information.
    This is a read-only view - users must navigate to profile_edit to make changes.
    """
    template_name = 'users/profile.html'

    def get(self, request):
        """Display user's profile page."""
        # Get the authenticated user from custom auth backend
        user = auth_backend.get_user_from_session(request)

        if not user or not user.is_authenticated:
            messages.error(request, 'Please log in to view your profile.')
            return redirect('auth:login')

        context = {
            'user': user,
        }
        return render(request, self.template_name, context)


class UserProfileEditView(LoginRequiredMixin, View):
    """
    View for users to edit their own profile information.
    Only allows editing personal fields (not roles, branches, schools, or account status).
    """
    template_name = 'users/profile_edit.html'

    def get(self, request):
        """Display profile edit form."""
        # Get the authenticated user from custom auth backend
        user = auth_backend.get_user_from_session(request)

        if not user or not user.is_authenticated:
            messages.error(request, 'Please log in to edit your profile.')
            return redirect('auth:login')

        form = ProfileEditForm(instance=user)

        context = {
            'user': user,
            'form': form,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """Process profile edit form submission."""
        # Get the authenticated user from custom auth backend
        user = auth_backend.get_user_from_session(request)

        if not user or not user.is_authenticated:
            messages.error(request, 'Please log in to edit your profile.')
            return redirect('auth:login')

        form = ProfileEditForm(request.POST, instance=user)

        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('users:profile')
        else:
            messages.error(request, 'Please correct the errors below.')

        context = {
            'user': user,
            'form': form,
        }
        return render(request, self.template_name, context)


# ==================== System Settings Views ====================

class SystemSettingsView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = 'admin.settings.edit'
    """
    View for managing system-wide settings like financial year configuration.
    """
    template_name = 'users/system_settings.html'

    def get(self, request):
        """Display system settings form."""
        from dashboard.models import SystemSettings
        from dashboard.utils.financial_year import get_current_financial_year_dates, format_date_range

        # Load current settings
        settings = SystemSettings.load()

        # Calculate current FY for display
        try:
            fy_start, fy_end = get_current_financial_year_dates()
            current_fy_display = format_date_range(fy_start, fy_end)
        except Exception as e:
            current_fy_display = "Unable to calculate (check settings)"

        # Month names for display
        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }

        context = {
            'settings': settings,
            'current_fy_display': current_fy_display,
            'month_names': month_names,
            'days': range(1, 32),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """Process system settings update."""
        from dashboard.models import SystemSettings
        from dashboard.utils.financial_year import get_current_financial_year_dates, format_date_range

        # Load current settings
        settings = SystemSettings.load()

        # Get form data
        try:
            fy_start_month = int(request.POST.get('fy_start_month'))
            fy_start_day = int(request.POST.get('fy_start_day'))
            fy_end_month = int(request.POST.get('fy_end_month'))
            fy_end_day = int(request.POST.get('fy_end_day'))

            # Validate ranges
            if not (1 <= fy_start_month <= 12):
                raise ValueError("Start month must be between 1 and 12")
            if not (1 <= fy_start_day <= 31):
                raise ValueError("Start day must be between 1 and 31")
            if not (1 <= fy_end_month <= 12):
                raise ValueError("End month must be between 1 and 12")
            if not (1 <= fy_end_day <= 31):
                raise ValueError("End day must be between 1 and 31")

            # Validate date exists (e.g., no Feb 31)
            try:
                date(2024, fy_start_month, fy_start_day)  # 2024 is a leap year
            except ValueError:
                raise ValueError(f"Invalid start date: month {fy_start_month} doesn't have {fy_start_day} days")

            try:
                date(2024, fy_end_month, fy_end_day)
            except ValueError:
                raise ValueError(f"Invalid end date: month {fy_end_month} doesn't have {fy_end_day} days")

            # Update settings
            settings.fy_start_month = fy_start_month
            settings.fy_start_day = fy_start_day
            settings.fy_end_month = fy_end_month
            settings.fy_end_day = fy_end_day
            settings.updated_by = request.user
            settings.save()

            messages.success(
                request,
                'System settings updated successfully. Financial year changes will apply across all reports.'
            )
            return redirect('users:system_settings')

        except ValueError as e:
            messages.error(request, f'Invalid input: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating settings: {str(e)}')

        # Re-render form with error
        try:
            fy_start, fy_end = get_current_financial_year_dates()
            current_fy_display = format_date_range(fy_start, fy_end)
        except Exception:
            current_fy_display = "Unable to calculate (check settings)"

        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }

        context = {
            'settings': settings,
            'current_fy_display': current_fy_display,
            'month_names': month_names,
            'days': range(1, 32),
        }
        return render(request, self.template_name, context)


# ==================== Store-School Mapping Views ====================

class StoreSchoolMappingView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = 'admin.settings.view'
    """
    View for managing store-school mappings
    Displays and allows management of relationships between stores/shops and schools
    """
    template_name = 'users/store_school_mapping.html'

    def get(self, request):
        """Display store-school mapping list."""
        from dashboard.models import StoreSchoolMapping

        # Get all mappings
        mappings = StoreSchoolMapping.objects.all()

        # Calculate statistics
        total_stores = mappings.values('store_name').distinct().count()
        total_schools = mappings.values('school_name').distinct().count()
        total_mappings = mappings.count()
        active_mappings = mappings.filter(is_active=True).count()

        context = {
            'mappings': mappings,
            'total_stores': total_stores,
            'total_schools': total_schools,
            'total_mappings': total_mappings,
            'active_mappings': active_mappings,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """Handle bulk actions and sync operations."""
        from dashboard.models import StoreSchoolMapping
        from cin7.models import Product

        action = request.POST.get('action')

        if action == 'sync':
            # Sync mappings from product table
            try:
                # Query products where category_name ends with 'Store' or 'Shop'
                stores = Product.objects.filter(
                    Q(category_name__iendswith='Store') | Q(category_name__iendswith='Shop')
                ).exclude(
                    category_name__in=['Store', 'Shop']
                ).exclude(
                    category_name__istartswith='Wholesale'
                ).values('category_name', 'sub_category').annotate(
                    product_count=Count('id')
                ).distinct()

                # Track statistics
                created_count = 0
                updated_count = 0

                for store_data in stores:
                    category_name = store_data['category_name']
                    school_name = store_data['sub_category']
                    product_count = store_data['product_count']

                    # Skip if school_name is empty
                    if not school_name or school_name.strip() == '':
                        continue

                    # Extract store name (remove ' Store' or ' Shop' suffix)
                    store_name = category_name
                    if store_name.endswith(' Store'):
                        store_name = store_name[:-6]
                    elif store_name.endswith(' Shop'):
                        store_name = store_name[:-5]

                    # Create or update mapping
                    mapping, created = StoreSchoolMapping.objects.update_or_create(
                        category_name=category_name,
                        school_name=school_name,
                        defaults={
                            'store_name': store_name,
                            'product_count': product_count,
                            'is_active': True,
                        }
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                messages.success(
                    request,
                    f'Sync completed successfully. Created {created_count} new mappings, updated {updated_count} existing mappings.'
                )
            except Exception as e:
                messages.error(request, f'Error syncing mappings: {str(e)}')

        elif action == 'toggle_active':
            # Toggle active status for selected mappings
            mapping_ids = request.POST.getlist('mapping_ids[]')
            if mapping_ids:
                try:
                    mappings = StoreSchoolMapping.objects.filter(id__in=mapping_ids)
                    for mapping in mappings:
                        mapping.is_active = not mapping.is_active
                        mapping.save()
                    messages.success(request, f'Updated {len(mapping_ids)} mapping(s).')
                except Exception as e:
                    messages.error(request, f'Error updating mappings: {str(e)}')
            else:
                messages.warning(request, 'No mappings selected.')

        elif action == 'bulk_activate':
            # Activate selected mappings
            mapping_ids = request.POST.getlist('mapping_ids[]')
            if mapping_ids:
                try:
                    StoreSchoolMapping.objects.filter(id__in=mapping_ids).update(is_active=True)
                    messages.success(request, f'Activated {len(mapping_ids)} mapping(s).')
                except Exception as e:
                    messages.error(request, f'Error activating mappings: {str(e)}')
            else:
                messages.warning(request, 'No mappings selected.')

        elif action == 'bulk_deactivate':
            # Deactivate selected mappings
            mapping_ids = request.POST.getlist('mapping_ids[]')
            if mapping_ids:
                try:
                    StoreSchoolMapping.objects.filter(id__in=mapping_ids).update(is_active=False)
                    messages.success(request, f'Deactivated {len(mapping_ids)} mapping(s).')
                except Exception as e:
                    messages.error(request, f'Error deactivating mappings: {str(e)}')
            else:
                messages.warning(request, 'No mappings selected.')

        return redirect('users:store_school_mapping')
