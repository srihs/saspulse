from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Role, CustomUser, UserSession
# from .models import UserProfile  # Commented out - will enable for migration


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin interface for Role model.
    """
    list_display = ['name', 'is_active', 'user_count', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Permissions', {
            'fields': ('permissions',),
            'description': 'Enter permissions as JSON. Example: {"can_view": true, "can_edit": false}'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_count(self, obj):
        """
        Display the number of users assigned to this role.
        """
        return obj.custom_users.count()  # Updated to use custom_users
    user_count.short_description = 'Users'

    def get_queryset(self, request):
        """
        Optimize queryset with prefetch_related for user count.
        """
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('custom_users')


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    """
    Admin interface for CustomUser model.
    """
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_active',
                    'is_staff', 'email_verified', 'get_roles', 'get_data_scope_display', 'last_login']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'email_verified',
                   'created_at', 'roles', 'assigned_branches']
    search_fields = ['username', 'email', 'first_name', 'last_name',
                     'department', 'job_title']
    filter_horizontal = ['roles', 'assigned_branches', 'assigned_schools']
    readonly_fields = ['created_at', 'updated_at', 'last_login', 'last_password_change',
                      'failed_login_attempts', 'locked_until']
    ordering = ['-created_at']

    fieldsets = (
        ('Authentication', {
            'fields': ('username', 'email', 'password_hash')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'phone_number', 'department',
                      'job_title', 'bio')
        }),
        ('Roles & Permissions', {
            'fields': ('roles', 'is_active', 'is_staff', 'is_superuser'),
            'description': 'Assign roles to control user permissions and access levels.'
        }),
        ('Data Scope & Assignments (RBAC)', {
            'fields': ('assigned_branches', 'assigned_branch', 'assigned_schools'),
            'description': '<strong>Store Managers:</strong> Assign branches using "assigned_branches".<br>'
                          '<strong>Sales Team:</strong> Assign schools using "assigned_schools".<br>'
                          '<em>Note: "assigned_branch" (singular) is deprecated - use "assigned_branches" instead.</em>',
            'classes': ('wide',)
        }),
        ('Account Status', {
            'fields': ('email_verified', 'failed_login_attempts', 'locked_until')
        }),
        ('Tokens', {
            'fields': ('activation_token', 'reset_token', 'reset_token_expires'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_login', 'last_password_change'),
            'classes': ('collapse',)
        }),
    )

    def get_roles(self, obj):
        """Display the roles assigned to the user."""
        roles = obj.roles.all()
        if roles:
            return ', '.join([role.name for role in roles])
        return '-'
    get_roles.short_description = 'Roles'

    def get_data_scope_display(self, obj):
        """Display the user's data scope (all, branch, school)."""
        scope = obj.get_data_scope()
        scope_map = {
            'all': '🌐 All Data',
            'branch': '🏪 Branch-Scoped',
            'school': '🎓 School-Scoped',
        }
        return scope_map.get(scope, scope)
    get_data_scope_display.short_description = 'Data Scope'

    def get_queryset(self, request):
        """Optimize queryset with prefetch_related."""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('roles', 'assigned_branches', 'assigned_schools')


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """
    Admin interface for UserSession model.
    """
    list_display = ['session_key', 'user', 'ip_address', 'is_active',
                    'remember_me', 'created_at', 'last_activity', 'expires_at']
    list_filter = ['is_active', 'remember_me', 'created_at', 'expires_at']
    search_fields = ['session_key', 'user__username', 'user__email', 'ip_address']
    readonly_fields = ['session_key', 'created_at', 'last_activity']
    ordering = ['-last_activity']

    fieldsets = (
        ('Session Info', {
            'fields': ('session_key', 'user', 'is_active')
        }),
        ('Client Info', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Expiration', {
            'fields': ('remember_me', 'expires_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_activity'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related('user')


# ==============================================================================
# OLD USER PROFILE ADMIN - TEMPORARILY COMMENTED OUT
# ==============================================================================
# This will be enabled during data migration phase
#
# class UserProfileInline(admin.StackedInline):
#     """
#     Inline admin for UserProfile to be displayed in the User admin.
#     """
#     model = UserProfile
#     can_delete = False
#     verbose_name = 'User Profile'
#     verbose_name_plural = 'User Profile'
#     filter_horizontal = ['roles']
#
#     fieldsets = (
#         ('Profile Information', {
#             'fields': ('phone_number', 'department', 'job_title', 'bio')
#         }),
#         ('Role Management', {
#             'fields': ('roles',)
#         }),
#     )
#
#
# class UserAdmin(BaseUserAdmin):
#     """
#     Extended User admin with UserProfile inline.
#     """
#     inlines = [UserProfileInline]
#
#     list_display = ['username', 'email', 'first_name', 'last_name',
#                     'is_active', 'is_staff', 'date_joined', 'get_roles']
#     list_filter = ['is_active', 'is_staff', 'is_superuser',
#                    'date_joined', 'profile__roles']
#     search_fields = ['username', 'email', 'first_name', 'last_name',
#                      'profile__department', 'profile__job_title']
#
#     def get_roles(self, obj):
#         """
#         Display the roles assigned to the user.
#         """
#         if hasattr(obj, 'profile'):
#             roles = obj.profile.roles.all()
#             if roles:
#                 return ', '.join([role.name for role in roles])
#         return '-'
#     get_roles.short_description = 'Roles'
#
#     def get_queryset(self, request):
#         """
#         Optimize queryset with select_related and prefetch_related.
#         """
#         queryset = super().get_queryset(request)
#         return queryset.select_related('profile').prefetch_related('profile__roles')
#
#
# # Unregister the default User admin and register our custom one
# admin.site.unregister(User)
# admin.site.register(User, UserAdmin)
#
#
# @admin.register(UserProfile)
# class UserProfileAdmin(admin.ModelAdmin):
#     """
#     Admin interface for UserProfile model (for direct access if needed).
#     """
#     list_display = ['user', 'department', 'job_title', 'get_roles', 'created_at']
#     list_filter = ['roles', 'department', 'created_at']
#     search_fields = ['user__username', 'user__email', 'user__first_name',
#                      'user__last_name', 'department', 'job_title']
#     filter_horizontal = ['roles']
#     readonly_fields = ['created_at', 'updated_at']
#
#     fieldsets = (
#         ('User', {
#             'fields': ('user',)
#         }),
#         ('Profile Information', {
#             'fields': ('phone_number', 'department', 'job_title', 'bio')
#         }),
#         ('Role Management', {
#             'fields': ('roles',)
#         }),
#         ('Timestamps', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )
#
#     def get_roles(self, obj):
#         """
#         Display the roles assigned to this profile.
#         """
#         roles = obj.roles.all()
#         if roles:
#             return ', '.join([role.name for role in roles])
#         return '-'
#     get_roles.short_description = 'Roles'
#
#     def get_queryset(self, request):
#         """
#         Optimize queryset with select_related and prefetch_related.
#         """
#         queryset = super().get_queryset(request)
#         return queryset.select_related('user').prefetch_related('roles')
