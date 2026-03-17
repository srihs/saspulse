"""
Management command to seed standard roles for the RBAC system.

This command creates 4 standard roles:
1. Admin - Full system access
2. Store Manager - Replenishment section only, branch-filtered
3. Demand Planner - Dashboard, Forecasting, Replenishment (no Admin)
4. Sales Team - Dashboard only, school-filtered

Usage:
    python manage.py seed_roles
    python manage.py seed_roles --force  # Update existing roles
"""

from django.core.management.base import BaseCommand
from users.models import Role


class Command(BaseCommand):
    help = 'Seed standard roles for the RBAC system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing roles (will overwrite permissions)',
        )

    def handle(self, *args, **options):
        force = options['force']

        # Define the 4 standard roles with their permissions
        roles_data = [
            {
                'name': 'Admin',
                'description': 'Full system access. Can manage users, view all data, and access all features.',
                'permissions': {
                    'dashboard': {
                        'view': True,
                        'export': True
                    },
                    'forecasting': {
                        'view': True,
                        'edit': True,
                        'export': True
                    },
                    'replenishment': {
                        'stores': {
                            'view': True,
                            'review': True,
                            'create_request': True,
                            'edit_request': True,
                            'submit_request': True
                        },
                        'demand_planning': {
                            'view': True,
                            'approve': True,
                            'reject': True,
                            'view_all_requests': True
                        },
                        'daily_pick_list': {
                            'view': True,
                            'export': True
                        }
                    },
                    'admin': {
                        'users': {
                            'view': True,
                            'create': True,
                            'edit': True,
                            'delete': True
                        },
                        'roles': {
                            'view': True,
                            'create': True,
                            'edit': True,
                            'delete': True
                        },
                        'settings': {
                            'view': True,
                            'edit': True
                        }
                    },
                    'data_scope': {
                        'type': 'all',
                        'filter_required': False
                    }
                }
            },
            {
                'name': 'Store Manager',
                'description': 'Store-level management. Can view and manage replenishment requests for assigned branches only.',
                'permissions': {
                    'dashboard': {
                        'view': False,
                        'export': False
                    },
                    'forecasting': {
                        'view': False,
                        'edit': False,
                        'export': False
                    },
                    'replenishment': {
                        'stores': {
                            'view': True,
                            'review': True,
                            'create_request': True,
                            'edit_request': True,
                            'submit_request': True
                        },
                        'demand_planning': {
                            'view': False,
                            'approve': False,
                            'reject': False,
                            'view_all_requests': False
                        },
                        'daily_pick_list': {
                            'view': True,
                            'export': True
                        }
                    },
                    'admin': {
                        'users': {
                            'view': False,
                            'create': False,
                            'edit': False,
                            'delete': False
                        },
                        'roles': {
                            'view': False,
                            'create': False,
                            'edit': False,
                            'delete': False
                        },
                        'settings': {
                            'view': False,
                            'edit': False
                        }
                    },
                    'data_scope': {
                        'type': 'branch',
                        'filter_required': True
                    }
                }
            },
            {
                'name': 'Demand Planner',
                'description': 'Planning and forecasting. Can view all data, manage forecasts and replenishment, but cannot access admin features.',
                'permissions': {
                    'dashboard': {
                        'view': True,
                        'export': True
                    },
                    'forecasting': {
                        'view': True,
                        'edit': True,
                        'export': True
                    },
                    'replenishment': {
                        'stores': {
                            'view': True,
                            'review': True,
                            'create_request': False,
                            'edit_request': False,
                            'submit_request': False
                        },
                        'demand_planning': {
                            'view': True,
                            'approve': True,
                            'reject': True,
                            'view_all_requests': True
                        },
                        'daily_pick_list': {
                            'view': True,
                            'export': True
                        }
                    },
                    'admin': {
                        'users': {
                            'view': False,
                            'create': False,
                            'edit': False,
                            'delete': False
                        },
                        'roles': {
                            'view': False,
                            'create': False,
                            'edit': False,
                            'delete': False
                        },
                        'settings': {
                            'view': False,
                            'edit': False
                        }
                    },
                    'data_scope': {
                        'type': 'all',
                        'filter_required': False
                    }
                }
            },
            {
                'name': 'Sales Team',
                'description': 'Sales analytics. Can view dashboard data for assigned schools only.',
                'permissions': {
                    'dashboard': {
                        'view': True,
                        'export': True
                    },
                    'forecasting': {
                        'view': False,
                        'edit': False,
                        'export': False
                    },
                    'replenishment': {
                        'stores': {
                            'view': False,
                            'review': False,
                            'create_request': False,
                            'edit_request': False,
                            'submit_request': False
                        },
                        'demand_planning': {
                            'view': False,
                            'approve': False,
                            'reject': False,
                            'view_all_requests': False
                        },
                        'daily_pick_list': {
                            'view': False,
                            'export': False
                        }
                    },
                    'admin': {
                        'users': {
                            'view': False,
                            'create': False,
                            'edit': False,
                            'delete': False
                        },
                        'roles': {
                            'view': False,
                            'create': False,
                            'edit': False,
                            'delete': False
                        },
                        'settings': {
                            'view': False,
                            'edit': False
                        }
                    },
                    'data_scope': {
                        'type': 'school',
                        'filter_required': True
                    }
                }
            }
        ]

        # Create or update roles
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for role_data in roles_data:
            role_name = role_data['name']

            try:
                role, created = Role.objects.get_or_create(
                    name=role_name,
                    defaults={
                        'description': role_data['description'],
                        'permissions': role_data['permissions'],
                        'is_active': True
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created role: {role_name}')
                    )
                else:
                    if force:
                        # Update existing role
                        role.description = role_data['description']
                        role.permissions = role_data['permissions']
                        role.is_active = True
                        role.save()
                        updated_count += 1
                        self.stdout.write(
                            self.style.WARNING(f'↻ Updated role: {role_name}')
                        )
                    else:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.NOTICE(f'- Skipped existing role: {role_name} (use --force to update)')
                        )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error processing role {role_name}: {str(e)}')
                )

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Role Seeding Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count}'))
        if force:
            self.stdout.write(self.style.SUCCESS(f'  Updated: {updated_count}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  Skipped: {skipped_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')

        # Show next steps
        if created_count > 0 or updated_count > 0:
            self.stdout.write(self.style.NOTICE('Next steps:'))
            self.stdout.write(self.style.NOTICE('  1. Assign users to roles via Django admin'))
            self.stdout.write(self.style.NOTICE('  2. Assign branches to store managers'))
            self.stdout.write(self.style.NOTICE('  3. Assign schools to sales team'))
            self.stdout.write('')
