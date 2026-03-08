"""
Dashboard Models

Additional models for dashboard analytics and caching
"""

from django.db import models
from django.utils import timezone


class DashboardCache(models.Model):
    """
    Cache computed dashboard metrics to improve performance
    """
    cache_key = models.CharField(max_length=255, unique=True, db_index=True)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['cache_key']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.cache_key} (expires: {self.expires_at})"

    @property
    def is_expired(self):
        """Check if cache has expired"""
        return timezone.now() > self.expires_at

    @classmethod
    def get_or_none(cls, cache_key):
        """Get cached data if not expired"""
        try:
            cache = cls.objects.get(cache_key=cache_key)
            if cache.is_expired:
                cache.delete()
                return None
            return cache.data
        except cls.DoesNotExist:
            return None

    @classmethod
    def set_cache(cls, cache_key, data, ttl_minutes=60):
        """Set cache data with TTL"""
        expires_at = timezone.now() + timezone.timedelta(minutes=ttl_minutes)
        cache, created = cls.objects.update_or_create(
            cache_key=cache_key,
            defaults={
                'data': data,
                'expires_at': expires_at
            }
        )
        return cache


class SalesForecastBase(models.Model):
    """
    Store base 365-day sales forecasts with flexible date range extraction
    Generates once per day and allows querying any date range within the 365-day window
    """
    AGGREGATION_LEVELS = [
        ('school', 'By School'),
        ('product', 'By Product'),
        ('shop', 'By Shop Location'),
        ('category', 'By Category'),
    ]

    MODEL_TYPES = [
        ('statistical', 'Statistical Model'),
        ('ml', 'Machine Learning'),
        ('hybrid', 'Hybrid (Statistical + ML)'),
    ]

    # Forecast identifiers
    forecast_id = models.CharField(max_length=100, unique=True, db_index=True)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES, default='statistical')
    aggregation_level = models.CharField(max_length=20, choices=AGGREGATION_LEVELS)

    # What is being forecasted
    entity_name = models.CharField(max_length=255, db_index=True)  # School name, product name, etc.
    entity_id = models.CharField(max_length=100, null=True, blank=True)  # Product ID, category ID, etc.

    # Base 365-day forecast data (JSON)
    # Structure: {"2026-03-05": {"quantity": 0.6, "confidence_lower": 0.5, "confidence_upper": 0.7}, ...}
    daily_forecasts = models.JSONField(default=dict)

    # Metadata
    forecast_date = models.DateField(db_index=True)  # Date forecast was generated
    training_data_start = models.DateField()
    training_data_end = models.DateField()

    # Accuracy metrics
    mae = models.FloatField(null=True, blank=True)  # Mean Absolute Error
    mape = models.FloatField(null=True, blank=True)  # Mean Absolute Percentage Error
    rmse = models.FloatField(null=True, blank=True)  # Root Mean Square Error
    accuracy_score = models.FloatField(null=True, blank=True)  # Overall accuracy (0-100)

    # Pre-calculated monthly demands (for performance optimization)
    monthly_demand_30 = models.FloatField(null=True, blank=True, help_text="Sum of next 30 days demand (30-60 days from forecast_date)")
    monthly_demand_60 = models.FloatField(null=True, blank=True, help_text="Sum of next 60 days demand (0-60 days from forecast_date)")

    # Model configuration
    model_params = models.JSONField(default=dict)  # Model hyperparameters

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-forecast_date', 'entity_name']
        indexes = [
            models.Index(fields=['forecast_id']),
            models.Index(fields=['aggregation_level']),
            models.Index(fields=['entity_name', 'forecast_date']),
            models.Index(fields=['forecast_date']),
        ]
        unique_together = [['entity_name', 'aggregation_level', 'forecast_date']]

    def __str__(self):
        return f"{self.entity_name} - 365d Base ({self.forecast_date})"

    def get_date_range_forecast(self, start_date, end_date):
        """
        Extract forecast data for a specific date range

        Args:
            start_date: datetime.date or string 'YYYY-MM-DD'
            end_date: datetime.date or string 'YYYY-MM-DD'

        Returns:
            dict: {date: {quantity, confidence_lower, confidence_upper}, ...}
        """
        from datetime import datetime, date

        # Convert to date objects if strings
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # Filter daily_forecasts for the date range
        result = {}
        for date_str, forecast_data in self.daily_forecasts.items():
            forecast_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if start_date <= forecast_date <= end_date:
                result[date_str] = forecast_data

        return result

    def get_total_quantity(self, start_date, end_date):
        """
        Calculate total forecasted quantity for a date range

        Args:
            start_date: datetime.date or string 'YYYY-MM-DD'
            end_date: datetime.date or string 'YYYY-MM-DD'

        Returns:
            float: Total quantity forecasted
        """
        date_range_data = self.get_date_range_forecast(start_date, end_date)
        return sum(day_data.get('quantity', 0) for day_data in date_range_data.values())

    def get_date_stats(self, start_date, end_date):
        """
        Get comprehensive statistics for a date range

        Args:
            start_date: datetime.date or string 'YYYY-MM-DD'
            end_date: datetime.date or string 'YYYY-MM-DD'

        Returns:
            dict: {
                'total': float,
                'average': float,
                'min': float,
                'max': float,
                'days': int,
                'daily_data': dict
            }
        """
        date_range_data = self.get_date_range_forecast(start_date, end_date)

        if not date_range_data:
            return {
                'total': 0,
                'average': 0,
                'min': 0,
                'max': 0,
                'days': 0,
                'daily_data': {}
            }

        quantities = [day_data.get('quantity', 0) for day_data in date_range_data.values()]

        return {
            'total': sum(quantities),
            'average': sum(quantities) / len(quantities) if quantities else 0,
            'min': min(quantities) if quantities else 0,
            'max': max(quantities) if quantities else 0,
            'days': len(date_range_data),
            'daily_data': date_range_data
        }


class ForecastSchedule(models.Model):
    """
    Track when forecasts were last generated and when they need regeneration
    Enables scheduled maintenance and freshness monitoring of base forecasts
    """

    STATUS_CHOICES = [
        ('current', 'Current'),
        ('due', 'Due for Regeneration'),
        ('overdue', 'Overdue'),
    ]

    # Entity identification (matches SalesForecastBase)
    entity_name = models.CharField(max_length=255, db_index=True)
    aggregation_level = models.CharField(max_length=20, db_index=True)

    # Schedule tracking
    last_generated = models.DateTimeField()
    next_generation_due = models.DateTimeField(db_index=True)
    generation_frequency_days = models.IntegerField(default=30)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='current', db_index=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_generation_due', 'entity_name']
        indexes = [
            models.Index(fields=['entity_name', 'aggregation_level']),
            models.Index(fields=['status', 'next_generation_due']),
            models.Index(fields=['aggregation_level', 'status']),
        ]
        unique_together = [['entity_name', 'aggregation_level']]

    def __str__(self):
        return f"{self.entity_name} ({self.aggregation_level}) - {self.get_status_display()}"

    @property
    def is_due(self):
        """Check if forecast is due for regeneration"""
        return timezone.now() >= self.next_generation_due

    @property
    def days_until_due(self):
        """Calculate days until regeneration is due"""
        delta = self.next_generation_due - timezone.now()
        return delta.days

    @property
    def days_since_generated(self):
        """Calculate days since last generation"""
        delta = timezone.now() - self.last_generated
        return delta.days

    def update_status(self):
        """Update status based on current date"""
        now = timezone.now()
        if now >= self.next_generation_due + timezone.timedelta(days=7):
            self.status = 'overdue'
        elif now >= self.next_generation_due:
            self.status = 'due'
        else:
            self.status = 'current'
        self.save()


class SalesForecast(models.Model):
    """
    Store sales forecast results for different time periods
    DEPRECATED: Use SalesForecastBase for new implementations
    Kept for backward compatibility
    """
    FORECAST_HORIZONS = [
        ('30d', '30 Days'),
        ('90d', '90 Days'),
        ('180d', '180 Days'),
        ('365d', '365 Days'),
    ]

    AGGREGATION_LEVELS = [
        ('school', 'By School'),
        ('product', 'By Product'),
        ('shop', 'By Shop Location'),
        ('category', 'By Category'),
    ]

    MODEL_TYPES = [
        ('statistical', 'Statistical Model'),
        ('ml', 'Machine Learning'),
        ('hybrid', 'Hybrid (Statistical + ML)'),
    ]

    # Forecast identifiers
    forecast_id = models.CharField(max_length=100, unique=True, db_index=True)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES, default='statistical')
    horizon = models.CharField(max_length=10, choices=FORECAST_HORIZONS)
    aggregation_level = models.CharField(max_length=20, choices=AGGREGATION_LEVELS)

    # What is being forecasted
    entity_name = models.CharField(max_length=255, db_index=True)  # School name, product name, etc.
    entity_id = models.CharField(max_length=100, null=True, blank=True)  # Product ID, category ID, etc.

    # Forecast results (JSON)
    forecast_data = models.JSONField(default=dict)  # {date: {quantity, revenue, confidence_interval}}

    # Metadata
    forecast_date = models.DateField(db_index=True)  # Date forecast was generated
    training_data_start = models.DateField()
    training_data_end = models.DateField()

    # Accuracy metrics
    mae = models.FloatField(null=True, blank=True)  # Mean Absolute Error
    mape = models.FloatField(null=True, blank=True)  # Mean Absolute Percentage Error
    rmse = models.FloatField(null=True, blank=True)  # Root Mean Square Error
    accuracy_score = models.FloatField(null=True, blank=True)  # Overall accuracy (0-100)

    # Model configuration
    model_params = models.JSONField(default=dict)  # Model hyperparameters

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-forecast_date', 'entity_name']
        indexes = [
            models.Index(fields=['forecast_id']),
            models.Index(fields=['horizon', 'aggregation_level']),
            models.Index(fields=['entity_name', 'forecast_date']),
            models.Index(fields=['forecast_date']),
        ]
        unique_together = [['entity_name', 'horizon', 'aggregation_level', 'forecast_date']]

    def __str__(self):
        return f"{self.entity_name} - {self.get_horizon_display()} ({self.forecast_date})"


class ForecastAccuracy(models.Model):
    """
    Track forecast accuracy over time by comparing predictions to actual sales
    """
    forecast = models.ForeignKey(SalesForecast, on_delete=models.CASCADE, related_name='accuracy_records')

    # Date being evaluated
    prediction_date = models.DateField(db_index=True)  # The date that was predicted
    evaluation_date = models.DateField()  # When we checked accuracy

    # Predicted vs Actual
    predicted_quantity = models.FloatField()
    actual_quantity = models.FloatField()
    predicted_revenue = models.FloatField(null=True, blank=True)
    actual_revenue = models.FloatField(null=True, blank=True)

    # Error metrics
    absolute_error = models.FloatField()
    percentage_error = models.FloatField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-prediction_date']
        indexes = [
            models.Index(fields=['forecast', 'prediction_date']),
            models.Index(fields=['evaluation_date']),
        ]
        unique_together = [['forecast', 'prediction_date']]

    def __str__(self):
        return f"{self.forecast.entity_name} - {self.prediction_date} (Error: {self.percentage_error:.1f}%)"


class ReplenishmentRequest(models.Model):
    """
    AI-generated replenishment requests based on forecast vs stock gap
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Store Manager Review'),
        ('approved', 'Approved by Store Manager'),
        ('modified', 'Modified by Store Manager'),
        ('rejected', 'Rejected by Store Manager'),
        ('dp_review', 'Under DP Team Review'),
        ('dp_approved', 'Approved by DP Team'),
        ('dp_rejected', 'Rejected by DP Team'),
        ('po_created', 'PO Created'),
        ('completed', 'Completed'),
    ]

    URGENCY_LEVELS = [
        ('low', 'Low - 30+ days stock'),
        ('medium', 'Medium - 15-30 days stock'),
        ('high', 'High - 7-15 days stock'),
        ('critical', 'Critical - <7 days stock'),
    ]

    # Request identifiers
    request_id = models.CharField(max_length=100, unique=True, db_index=True)
    week_number = models.IntegerField(db_index=True)  # Year-week when generated
    year = models.IntegerField(db_index=True)

    # Product and location
    product = models.ForeignKey('cin7.Product', on_delete=models.CASCADE, related_name='replenishment_requests')
    branch = models.ForeignKey('cin7.Branch', on_delete=models.CASCADE, related_name='replenishment_requests')
    school_name = models.CharField(max_length=255, db_index=True, null=True, blank=True)

    # Stock analysis
    current_stock = models.FloatField()
    forecasted_demand_30d = models.FloatField()  # From SalesForecast
    stock_gap = models.FloatField()  # forecasted_demand - current_stock

    # AI suggestions
    suggested_quantity = models.FloatField()
    urgency = models.CharField(max_length=20, choices=URGENCY_LEVELS, default='medium')
    ai_confidence = models.FloatField(default=0.0)  # 0-100, based on forecast accuracy

    # Store Manager decisions
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    store_approved_quantity = models.FloatField(null=True, blank=True)
    store_manager_comment = models.TextField(blank=True)
    store_manager = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='store_approvals')
    store_approved_at = models.DateTimeField(null=True, blank=True)

    # DP Team decisions
    dp_approved_quantity = models.FloatField(null=True, blank=True)
    dp_team_comment = models.TextField(blank=True)
    dp_approver = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='dp_approvals')
    dp_approved_at = models.DateTimeField(null=True, blank=True)

    # Linked forecast
    forecast = models.ForeignKey(SalesForecast, on_delete=models.SET_NULL, null=True, blank=True, related_name='replenishment_requests')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-urgency']
        indexes = [
            models.Index(fields=['request_id']),
            models.Index(fields=['status', 'branch']),
            models.Index(fields=['week_number', 'year']),
            models.Index(fields=['urgency', 'status']),
            models.Index(fields=['school_name']),
        ]

    def __str__(self):
        return f"{self.request_id} - {self.product.name} @ {self.branch.name}"

    @property
    def final_quantity(self):
        """Get the final approved quantity"""
        if self.dp_approved_quantity is not None:
            return self.dp_approved_quantity
        elif self.store_approved_quantity is not None:
            return self.store_approved_quantity
        else:
            return self.suggested_quantity

    @property
    def days_of_stock(self):
        """Calculate how many days of stock remain"""
        if self.forecasted_demand_30d <= 0:
            return 999
        daily_demand = self.forecasted_demand_30d / 30
        if daily_demand <= 0:
            return 999
        return self.current_stock / daily_demand


class PurchaseOrder(models.Model):
    """
    Purchase orders generated from approved replenishment requests
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('sent_to_supplier', 'Sent to Supplier'),
        ('partially_received', 'Partially Received'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # PO identifiers
    po_number = models.CharField(max_length=100, unique=True, db_index=True)
    supplier_name = models.CharField(max_length=255, db_index=True)
    supplier_contact = models.CharField(max_length=255, blank=True)

    # PO details
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft', db_index=True)
    total_items = models.IntegerField(default=0)
    total_quantity = models.FloatField(default=0)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Linked replenishment requests
    replenishment_requests = models.ManyToManyField(ReplenishmentRequest, related_name='purchase_orders')

    # Approval and tracking
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, related_name='created_pos')
    approved_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_pos')
    approved_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    expected_delivery_date = models.DateField(null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['po_number']),
            models.Index(fields=['status']),
            models.Index(fields=['supplier_name']),
        ]

    def __str__(self):
        return f"PO-{self.po_number} - {self.supplier_name} ({self.status})"


class ReplenishmentNotification(models.Model):
    """
    Track email notifications sent to store managers and DP team
    """
    NOTIFICATION_TYPES = [
        ('store_new_request', 'New Replenishment Request (Store Manager)'),
        ('store_reminder', 'Reminder to Review (Store Manager)'),
        ('dp_new_batch', 'New Batch for Review (DP Team)'),
        ('dp_urgent', 'Urgent Stock Alert (DP Team)'),
        ('po_created', 'PO Created Notification'),
    ]

    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    recipient = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='replenishment_notifications')
    subject = models.CharField(max_length=255)
    body = models.TextField()

    # Related objects
    replenishment_request = models.ForeignKey(ReplenishmentRequest, on_delete=models.CASCADE, null=True, blank=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, null=True, blank=True)

    # Email status
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    is_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notification_type_display()} to {self.recipient.username}"
