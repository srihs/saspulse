"""
Celery configuration for SasPulse project.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saspulse.settings')

app = Celery('saspulse')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    # Full sync daily at 2 AM UTC
    'full-sync-daily': {
        'task': 'apps.cin7.tasks.full_sync_task',
        'schedule': crontab(hour=2, minute=0),
        'options': {'expires': 3600},  # Task expires after 1 hour if not executed
    },

    # Incremental sync every 5 minutes
    'incremental-sync': {
        'task': 'apps.cin7.tasks.incremental_sync_task',
        'schedule': crontab(minute='*/5'),
        'options': {'expires': 300},
    },

    # Inventory sync every 10 minutes
    'inventory-sync': {
        'task': 'apps.cin7.tasks.sync_inventory_task',
        'schedule': crontab(minute='*/10'),
        'options': {'expires': 600},
    },

    # Orders sync every 3 minutes (more frequent for real-time needs)
    'orders-sync': {
        'task': 'apps.cin7.tasks.sync_orders_task',
        'schedule': crontab(minute='*/3'),
        'options': {'expires': 180},
    },

    # Reset Cin7 API daily counter at midnight UTC
    'reset-cin7-counter': {
        'task': 'apps.cin7.tasks.reset_daily_api_counter',
        'schedule': crontab(hour=0, minute=0),
    },
}

# Celery task configuration
app.conf.task_routes = {
    'apps.cin7.tasks.*': {'queue': 'cin7'},
    'apps.dashboard.tasks.*': {'queue': 'dashboard'},
}

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')
