from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from .models import Role  # UserProfile commented out - using CustomUser now
from .forms import (
    RoleForm, UserCreateForm, UserUpdateForm,
    # UserProfileForm,  # Commented out - using CustomUser now
    UserRolesForm
)


# ==================== Role Views ====================

class RoleListView(LoginRequiredMixin, ListView):
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


class RoleCreateView(LoginRequiredMixin, CreateView):
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


class RoleUpdateView(LoginRequiredMixin, UpdateView):
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


class RoleDeleteView(LoginRequiredMixin, DeleteView):
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
        context['user_count'] = self.object.user_profiles.count()
        return context


# ==================== User Views ====================

class UserListView(LoginRequiredMixin, ListView):
    """
    View to list all users with search functionality.
    """
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        queryset = User.objects.select_related('profile').prefetch_related('profile__roles')
        search_query = self.request.GET.get('search', '')

        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(profile__department__icontains=search_query) |
                Q(profile__job_title__icontains=search_query)
            )

        return queryset.order_by('username')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class UserCreateView(LoginRequiredMixin, CreateView):
    """
    View to create a new user.
    """
    model = User
    form_class = UserCreateForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:user_list')

    def form_valid(self, form):
        messages.success(self.request, f'User "{form.instance.username}" created successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Error creating user. Please check the form and try again.')
        return super().form_invalid(form)


class UserUpdateView(LoginRequiredMixin, UpdateView):
    """
    View to update an existing user.
    """
    model = User
    form_class = UserUpdateForm
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


class UserDeleteView(LoginRequiredMixin, DeleteView):
    """
    View to delete a user.
    """
    model = User
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
        if hasattr(self.object, 'profile'):
            context['user_roles'] = self.object.profile.roles.all()
        return context


class UserRolesView(LoginRequiredMixin, View):
    """
    View to manage role assignments for a user.
    """
    template_name = 'users/user_roles.html'

    def get(self, request, id):
        user = get_object_or_404(User, pk=id)
        form = UserRolesForm(user=user)

        context = {
            'user': user,
            'form': form,
            'current_roles': user.profile.roles.all() if hasattr(user, 'profile') else []
        }
        return render(request, self.template_name, context)

    def post(self, request, id):
        user = get_object_or_404(User, pk=id)
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
            'current_roles': user.profile.roles.all() if hasattr(user, 'profile') else []
        }
        return render(request, self.template_name, context)


# ==================== Additional Helper Views ====================

class UserDetailView(LoginRequiredMixin, View):
    """
    View to display detailed information about a user.
    This can be used as a quick overview before editing.
    """
    template_name = 'users/user_detail.html'

    def get(self, request, id):
        user = get_object_or_404(
            User.objects.select_related('profile').prefetch_related('profile__roles'),
            pk=id
        )

        context = {
            'user': user,
            'profile': user.profile if hasattr(user, 'profile') else None,
            'roles': user.profile.roles.all() if hasattr(user, 'profile') else []
        }
        return render(request, self.template_name, context)


class RoleDetailView(LoginRequiredMixin, View):
    """
    View to display detailed information about a role.
    Shows role details and users assigned to this role.
    """
    template_name = 'users/role_detail.html'

    def get(self, request, id):
        role = get_object_or_404(
            Role.objects.prefetch_related('user_profiles__user'),
            pk=id
        )

        # Get all users with this role
        users_with_role = User.objects.filter(
            profile__roles=role
        ).select_related('profile')

        context = {
            'role': role,
            'users_with_role': users_with_role,
            'user_count': users_with_role.count()
        }
        return render(request, self.template_name, context)
