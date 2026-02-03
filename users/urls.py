from django.urls import path, include
from . import views, auth_views

app_name = 'users'

urlpatterns = [
    # Authentication URLs (prefixed with auth/)
    path('auth/', include('users.auth_urls')),

    # Profile and Password Management (authenticated users)
    path('profile/', auth_views.ProfileView.as_view(), name='profile'),
    path('change-password/', auth_views.ChangePasswordView.as_view(), name='change_password'),

    # Role URLs
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:id>/', views.RoleDetailView.as_view(), name='role_detail'),
    path('roles/<int:id>/edit/', views.RoleUpdateView.as_view(), name='role_edit'),
    path('roles/<int:id>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),

    # User URLs
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:id>/', views.UserDetailView.as_view(), name='user_detail'),
    path('users/<int:id>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('users/<int:id>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/<int:id>/roles/', views.UserRolesView.as_view(), name='user_roles'),
]
