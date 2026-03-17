"""
Template context processors for injecting user permissions into all templates.

This module provides context processors that add user permission information
to the template context, making it available in all templates without having
to explicitly pass it from every view.

Usage:
    Add to settings.py TEMPLATES configuration:
    'context_processors': [
        ...
        'dashboard.context_processors.user_permissions',
    ]

    Then in templates:
    {% if user_permissions.dashboard.view %}
        <!-- Show dashboard link -->
    {% endif %}
"""

from dashboard.utils.permissions import get_user_context


def user_permissions(request):
    """
    Add user permissions to template context.

    This context processor injects user permission information into all templates,
    making it easy to conditionally show/hide UI elements based on permissions.

    Available in templates:
        - user_permissions: Dict of all user permissions
        - user_roles: List of role names assigned to user
        - user_data_scope: 'all', 'branch', or 'school'
        - user_branches: List of assigned branch names
        - user_schools: List of assigned school sub_categories
        - is_admin: Boolean - true if user is admin
        - is_store_manager: Boolean - true if user is store manager
        - is_demand_planner: Boolean - true if user is demand planner
        - is_sales_team: Boolean - true if user is sales team

    Examples in templates:
        {% if user_permissions.dashboard.view %}
            <a href="{% url 'dashboard:dashboard' %}">Dashboard</a>
        {% endif %}

        {% if is_store_manager %}
            <p>Your branches: {{ user_branches|join:", " }}</p>
        {% endif %}

        {% if user_data_scope == 'school' %}
            <p>Viewing data for: {{ user_schools|join:", " }}</p>
        {% endif %}
    """
    if not request.user.is_authenticated:
        return {
            'user_permissions': {},
            'user_roles': [],
            'user_data_scope': None,
            'user_branches': [],
            'user_schools': [],
            'is_admin': False,
            'is_store_manager': False,
            'is_demand_planner': False,
            'is_sales_team': False,
        }

    # Get full user context
    context = get_user_context(request.user)

    return context
