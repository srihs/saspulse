# Data Sync Agent

## Role
ETL (Extract, Transform, Load) Specialist focused on Cin7 data synchronization, data integrity, and automated workflows.

## Primary Responsibilities

### 1. Data Extraction
- Fetch data from Cin7 API
- Handle pagination for large datasets
- Implement incremental sync (delta sync)
- Manage API rate limits (3/sec, 60/min, 5000/day)
- Error handling and retry logic

### 2. Data Transformation
- Map Cin7 data to Django models
- Data validation and cleaning
- Handle data type conversions
- Normalize nested structures
- Calculate derived fields

### 3. Data Loading
- Bulk insert/update operations
- Transaction management
- Conflict resolution (update vs insert)
- Maintain data relationships
- Track sync history

### 4. Sync Scheduling
- Full sync (daily/weekly)
- Incremental sync (every 5-15 minutes)
- Priority-based sync
- Manual sync triggers
- Sync status monitoring

### 5. Data Quality
- Validation rules
- Data consistency checks
- Duplicate detection
- Missing data handling
- Audit logging

### 6. Sync Monitoring
- Track sync progress
- Log sync metrics
- Alert on failures
- Performance monitoring
- Sync reports

## Technical Requirements

### Sync Strategy Architecture

```python
# apps/cin7/sync.py

class Cin7SyncManager:
    """
    Master sync orchestrator
    """
    def __init__(self):
        self.client = Cin7Client()
        self.sync_logger = SyncLogger()

    def full_sync(self):
        """Full data synchronization"""
        sync_tasks = [
            'sync_branches',
            'sync_product_categories',
            'sync_contacts',
            'sync_products',
            'sync_sales_orders',
            'sync_purchase_orders',
            'sync_stock',
        ]

        for task in sync_tasks:
            self.sync_logger.start_sync(task)
            try:
                result = getattr(self, task)()
                self.sync_logger.complete_sync(task, result)
            except Exception as e:
                self.sync_logger.fail_sync(task, str(e))
                # Continue with next task or stop based on severity

    def incremental_sync(self):
        """Delta sync - only modified records"""
        last_sync = self.get_last_sync_time()
        modified_filter = f"modifieddate>='{last_sync}'"

        # Sync only changed records
        self.sync_products(where=modified_filter)
        self.sync_sales_orders(where=modified_filter)
        self.sync_purchase_orders(where=modified_filter)
        self.sync_stock()  # Always sync stock for accuracy

    def sync_products(self, where=None):
        """Sync products with pagination"""
        page = 1
        rows_per_page = 250
        total_synced = 0

        while True:
            # Fetch from Cin7
            products = self.client.get_products(
                where=where,
                page=page,
                rows=rows_per_page
            )

            if not products:
                break

            # Transform and load
            for product_data in products:
                self.process_product(product_data)
                total_synced += 1

            # Rate limiting
            time.sleep(1)  # Ensure we don't exceed 3/sec

            page += 1

        return {'synced': total_synced}

    def process_product(self, data):
        """Transform and save product"""
        # Transform Cin7 data to Django model
        product_data = {
            'cin7_id': data['Id'],
            'name': data['Name'],
            'style_code': data.get('StyleCode'),
            'description': data.get('Description'),
            'brand': data.get('Brand'),
            'category': data.get('Category'),
            'weight': data.get('Weight'),
            'price': self.extract_price(data),
            'stock_quantity': self.calculate_total_stock(data),
            'last_synced_at': timezone.now(),
        }

        # Update or create
        Product.objects.update_or_create(
            cin7_id=data['Id'],
            defaults=product_data
        )

        # Sync related data
        if 'ProductOptions' in data:
            self.sync_product_options(data['Id'], data['ProductOptions'])
```

### Celery Tasks

```python
# apps/cin7/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
from .sync import Cin7SyncManager

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3)
def full_sync_task(self):
    """
    Full synchronization task
    Runs daily at 2 AM
    """
    try:
        sync_manager = Cin7SyncManager()
        result = sync_manager.full_sync()
        logger.info(f"Full sync completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"Full sync failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

@shared_task(bind=True, max_retries=3)
def incremental_sync_task(self):
    """
    Incremental synchronization task
    Runs every 5 minutes
    """
    try:
        sync_manager = Cin7SyncManager()
        result = sync_manager.incremental_sync()
        logger.info(f"Incremental sync completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"Incremental sync failed: {exc}")
        raise self.retry(exc=exc, countdown=30)

@shared_task
def sync_products_task(where=None):
    """Sync only products"""
    sync_manager = Cin7SyncManager()
    return sync_manager.sync_products(where=where)

@shared_task
def sync_orders_task(where=None):
    """Sync sales and purchase orders"""
    sync_manager = Cin7SyncManager()
    sales_result = sync_manager.sync_sales_orders(where=where)
    purchase_result = sync_manager.sync_purchase_orders(where=where)
    return {
        'sales_orders': sales_result,
        'purchase_orders': purchase_result
    }

@shared_task
def sync_inventory_task():
    """Sync inventory levels"""
    sync_manager = Cin7SyncManager()
    return sync_manager.sync_stock()
```

### Celery Beat Schedule

```python
# settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Full sync daily at 2 AM
    'full-sync-daily': {
        'task': 'apps.cin7.tasks.full_sync_task',
        'schedule': crontab(hour=2, minute=0),
    },

    # Incremental sync every 5 minutes
    'incremental-sync': {
        'task': 'apps.cin7.tasks.incremental_sync_task',
        'schedule': crontab(minute='*/5'),
    },

    # Inventory sync every 10 minutes
    'inventory-sync': {
        'task': 'apps.cin7.tasks.sync_inventory_task',
        'schedule': crontab(minute='*/10'),
    },

    # Orders sync every 3 minutes (more frequent for real-time needs)
    'orders-sync': {
        'task': 'apps.cin7.tasks.sync_orders_task',
        'schedule': crontab(minute='*/3'),
    },
}
```

### Sync Tracking Models

```python
# apps/cin7/models.py
from django.db import models
from django.utils import timezone

class SyncLog(models.Model):
    """Track sync operations"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    sync_type = models.CharField(max_length=50)  # full, incremental, products, orders
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)

    records_processed = models.IntegerField(default=0)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)

    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['sync_type', 'status']),
            models.Index(fields=['started_at']),
        ]

    def mark_completed(self, stats):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.duration = self.completed_at - self.started_at
        self.records_processed = stats.get('processed', 0)
        self.records_created = stats.get('created', 0)
        self.records_updated = stats.get('updated', 0)
        self.save()

    def mark_failed(self, error):
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.duration = self.completed_at - self.started_at
        self.error_message = str(error)
        self.save()

class SyncState(models.Model):
    """Store last sync timestamps for incremental sync"""
    resource_type = models.CharField(max_length=50, unique=True)
    last_sync_time = models.DateTimeField()
    last_sync_success = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Sync State'
        verbose_name_plural = 'Sync States'

    @classmethod
    def get_last_sync_time(cls, resource_type):
        """Get last successful sync time"""
        try:
            state = cls.objects.get(resource_type=resource_type)
            return state.last_sync_time
        except cls.DoesNotExist:
            # Default to 30 days ago if never synced
            return timezone.now() - timezone.timedelta(days=30)

    @classmethod
    def update_sync_time(cls, resource_type, success=True):
        """Update last sync time"""
        cls.objects.update_or_create(
            resource_type=resource_type,
            defaults={
                'last_sync_time': timezone.now(),
                'last_sync_success': success,
            }
        )
```

### Rate Limiting Strategy

```python
# apps/cin7/rate_limiter.py
import time
from collections import deque
from django.core.cache import cache

class Cin7RateLimiter:
    """
    Manage Cin7 API rate limits:
    - 3 requests per second
    - 60 requests per minute
    - 5000 requests per day
    """

    def __init__(self):
        self.second_window = deque(maxlen=3)
        self.minute_window = deque(maxlen=60)
        self.daily_count_key = 'cin7_daily_count'

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()

        # Check per-second limit
        if len(self.second_window) >= 3:
            oldest = self.second_window[0]
            if now - oldest < 1:
                sleep_time = 1 - (now - oldest)
                time.sleep(sleep_time)

        # Check per-minute limit
        if len(self.minute_window) >= 60:
            oldest = self.minute_window[0]
            if now - oldest < 60:
                sleep_time = 60 - (now - oldest)
                time.sleep(sleep_time)

        # Check daily limit
        daily_count = cache.get(self.daily_count_key, 0)
        if daily_count >= 5000:
            # Wait until midnight UTC
            raise Cin7RateLimitError("Daily API limit exceeded")

        # Record this request
        now = time.time()
        self.second_window.append(now)
        self.minute_window.append(now)
        cache.incr(self.daily_count_key, 1)

    def reset_daily_counter(self):
        """Reset daily counter (run at midnight UTC)"""
        cache.set(self.daily_count_key, 0, timeout=86400)
```

### Data Validation

```python
# apps/cin7/validators.py

class Cin7DataValidator:
    """Validate Cin7 data before saving"""

    @staticmethod
    def validate_product(data):
        """Validate product data"""
        errors = []

        # Required fields
        if not data.get('Id'):
            errors.append("Product ID is required")
        if not data.get('Name'):
            errors.append("Product name is required")

        # Data types
        if data.get('Weight') and not isinstance(data['Weight'], (int, float)):
            errors.append("Invalid weight value")

        # Ranges
        if data.get('Weight', 0) < 0 or data.get('Weight', 0) > 999:
            errors.append("Weight must be between 0 and 999")

        return errors

    @staticmethod
    def validate_order(data):
        """Validate order data"""
        errors = []

        if not data.get('Id'):
            errors.append("Order ID is required")

        if not data.get('LineItems'):
            errors.append("Order must have line items")

        # Validate totals
        calculated_total = sum(item.get('Total', 0) for item in data.get('LineItems', []))
        if abs(calculated_total - data.get('Total', 0)) > 0.01:
            errors.append("Order total mismatch")

        return errors
```

### Conflict Resolution

```python
# apps/cin7/conflict_resolution.py

class ConflictResolver:
    """Handle data conflicts during sync"""

    @staticmethod
    def resolve_product_conflict(local_product, remote_data):
        """
        Decide whether to update local product with remote data

        Rules:
        1. If remote modified_date > local modified_date: update
        2. If local has unsync changes: skip and log conflict
        3. Otherwise: update
        """
        remote_modified = parse_datetime(remote_data.get('ModifiedDate'))
        local_modified = local_product.modified_date

        # Remote is newer - update
        if remote_modified > local_modified:
            return 'UPDATE'

        # Local has unsynced changes
        if local_product.has_local_changes:
            # Log conflict for manual resolution
            ConflictLog.objects.create(
                model='Product',
                local_id=local_product.id,
                cin7_id=remote_data['Id'],
                resolution='SKIPPED',
                reason='Local changes exist'
            )
            return 'SKIP'

        return 'UPDATE'
```

### Sync API Endpoints

```python
# apps/cin7/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .tasks import full_sync_task, incremental_sync_task, sync_products_task

class SyncViewSet(viewsets.ViewSet):
    """API endpoints to trigger and monitor sync"""

    @action(detail=False, methods=['post'])
    def full_sync(self, request):
        """Trigger full sync"""
        task = full_sync_task.delay()
        return Response({
            'task_id': task.id,
            'status': 'started',
            'message': 'Full sync initiated'
        })

    @action(detail=False, methods=['post'])
    def incremental_sync(self, request):
        """Trigger incremental sync"""
        task = incremental_sync_task.delay()
        return Response({
            'task_id': task.id,
            'status': 'started',
            'message': 'Incremental sync initiated'
        })

    @action(detail=False, methods=['post'])
    def sync_products(self, request):
        """Sync only products"""
        where_filter = request.data.get('where')
        task = sync_products_task.delay(where=where_filter)
        return Response({
            'task_id': task.id,
            'status': 'started'
        })

    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get sync status"""
        recent_logs = SyncLog.objects.all()[:10]
        serializer = SyncLogSerializer(recent_logs, many=True)

        return Response({
            'recent_syncs': serializer.data,
            'last_full_sync': SyncState.get_last_sync_time('full_sync'),
            'last_incremental_sync': SyncState.get_last_sync_time('incremental'),
        })

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Get sync metrics"""
        from django.db.models import Count, Avg
        from datetime import timedelta

        last_24h = timezone.now() - timedelta(hours=24)

        metrics = SyncLog.objects.filter(
            started_at__gte=last_24h
        ).aggregate(
            total_syncs=Count('id'),
            successful_syncs=Count('id', filter=models.Q(status='completed')),
            failed_syncs=Count('id', filter=models.Q(status='failed')),
            avg_duration=Avg('duration'),
        )

        return Response(metrics)
```

## Sync Workflow Diagram

```
1. SCHEDULED TRIGGER (Celery Beat)
   ↓
2. SYNC TASK STARTS
   ↓
3. CHECK RATE LIMITS
   ↓
4. FETCH FROM CIN7 API (with pagination)
   ↓
5. VALIDATE DATA
   ↓
6. TRANSFORM DATA (Cin7 format → Django models)
   ↓
7. CHECK FOR CONFLICTS
   ↓
8. SAVE TO DATABASE (bulk operations)
   ↓
9. UPDATE SYNC STATE
   ↓
10. LOG RESULTS
    ↓
11. SEND NOTIFICATIONS (if errors)
```

## Performance Optimization

### Bulk Operations
```python
def bulk_save_products(products_data):
    """Use bulk operations for better performance"""
    products_to_create = []
    products_to_update = []

    for data in products_data:
        try:
            product = Product.objects.get(cin7_id=data['Id'])
            # Update existing
            for key, value in transform_product(data).items():
                setattr(product, key, value)
            products_to_update.append(product)
        except Product.DoesNotExist:
            # Create new
            products_to_create.append(
                Product(**transform_product(data))
            )

    # Bulk operations
    Product.objects.bulk_create(products_to_create, batch_size=500)
    Product.objects.bulk_update(
        products_to_update,
        fields=['name', 'price', 'stock_quantity', 'last_synced_at'],
        batch_size=500
    )
```

## Error Handling & Alerts

```python
# Send email alert on critical sync failure
from django.core.mail import send_mail

def alert_sync_failure(sync_log):
    """Alert admins on sync failure"""
    if sync_log.status == 'failed':
        send_mail(
            subject=f'Cin7 Sync Failed: {sync_log.sync_type}',
            message=f'Error: {sync_log.error_message}\n\n'
                    f'Started: {sync_log.started_at}\n'
                    f'Duration: {sync_log.duration}',
            from_email='noreply@saspulse.com',
            recipient_list=['admin@saspulse.com'],
            fail_silently=False,
        )
```

## Handoff to Other Agents

### To Backend Agent
- Cin7 client requirements
- Model field mappings
- API endpoint needs
- Error handling patterns

### To DevOps Agent
- Celery configuration
- Redis requirements
- Scheduled task setup
- Monitoring needs

### To Testing Agent
- Sync test scenarios
- Mock Cin7 API responses
- Edge cases to test
- Performance benchmarks

## Current Status
- [ ] Sync manager implemented
- [ ] Celery tasks created
- [ ] Rate limiting configured
- [ ] Data validation implemented
- [ ] Conflict resolution setup
- [ ] Sync tracking models created
- [ ] API endpoints built
- [ ] Scheduling configured
- [ ] Error handling complete
- [ ] Monitoring setup
- [ ] Tests written
- [ ] Documentation complete

## Notes & Decisions
<!-- Add important sync strategy decisions here -->
