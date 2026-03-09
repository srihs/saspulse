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

    # Simple Monthly Forecast Fields (NEW - Simple Approach)
    monthly_breakdown = models.JSONField(
        default=dict,
        help_text="Monthly forecast breakdown: {'2027-01': {'quantity': 59, 'avg_last_3_years': 51.7, 'min': 45, 'max': 58, 'confidence': 'high', 'is_peak_month': True, 'historical_sales': [45, 52, 58]}}"
    )
    seasonal_profile = models.JSONField(
        default=dict,
        help_text="Seasonal pattern analysis: {'peak_months': [1, 2, 11, 12], 'medium_months': [3, 10], 'low_months': [4, 5, 9], 'zero_months': [6, 7, 8], 'peak_season_label': 'Back-to-School (Jan-Feb)', 'annual_forecast': 450}"
    )
    growth_metrics = models.JSONField(
        default=dict,
        help_text="Growth trend analysis: {'direction': 'growth', 'annual_rate': 14.5, 'trend_strength': 'moderate', 'last_year_total': 420, 'forecast_year_total': 480}"
    )

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

    def calculate_safety_stock(self, month_key, lead_time_days=14):
        """
        Calculate intelligent safety stock for a specific month

        Uses season-based multipliers + lead time buffer

        Args:
            month_key (str): Month in format 'YYYY-MM' (e.g., '2027-01')
            lead_time_days (int): Supplier lead time in days (default: 14)

        Returns:
            dict: {
                'recommended_stock': Total units needed,
                'base_forecast': Monthly forecast quantity,
                'safety_buffer': Extra buffer for seasonality,
                'lead_time_buffer': Buffer for supplier lead time,
                'season_multiplier': Multiplier used (1.1, 1.3, or 1.8),
                'urgency': 'CRITICAL' | 'MODERATE' | 'LOW' | 'NONE',
                'reason': Human-readable explanation
            }
        """
        from datetime import datetime

        # Get monthly breakdown and seasonal profile
        if not self.monthly_breakdown or month_key not in self.monthly_breakdown:
            return {
                'recommended_stock': 0,
                'base_forecast': 0,
                'safety_buffer': 0,
                'lead_time_buffer': 0,
                'season_multiplier': 0,
                'urgency': 'NONE',
                'reason': 'No forecast data for this month'
            }

        monthly_data = self.monthly_breakdown[month_key]
        monthly_forecast = monthly_data.get('quantity', 0)

        # Extract month number
        month = int(month_key.split('-')[1])

        # Determine season multiplier based on seasonal profile
        seasonal_profile = self.seasonal_profile or {}
        peak_months = seasonal_profile.get('peak_months', [])
        medium_months = seasonal_profile.get('medium_months', [])
        zero_months = seasonal_profile.get('zero_months', [])

        if monthly_forecast == 0 or month in zero_months:
            # Off-season - no stock needed
            return {
                'recommended_stock': 0,
                'base_forecast': 0,
                'safety_buffer': 0,
                'lead_time_buffer': 0,
                'season_multiplier': 0,
                'urgency': 'NONE',
                'reason': 'Off-season - no sales expected'
            }

        if month in peak_months:
            season_multiplier = 1.8  # Peak: 80% buffer
            urgency = 'CRITICAL'
            season_label = 'Peak season'
        elif month in medium_months:
            season_multiplier = 1.3  # Medium: 30% buffer
            urgency = 'MODERATE'
            season_label = 'Medium season'
        else:
            season_multiplier = 1.1  # Low: 10% buffer
            urgency = 'LOW'
            season_label = 'Low season'

        # Calculate safety buffer
        safety_buffer = monthly_forecast * (season_multiplier - 1)

        # Calculate lead time buffer
        daily_forecast = monthly_forecast / 30
        lead_time_buffer = daily_forecast * lead_time_days

        # Total recommended stock
        recommended_stock = (monthly_forecast * season_multiplier) + lead_time_buffer

        # Build human-readable reason
        reason = f'{season_label} - {int((season_multiplier-1)*100)}% safety buffer + {lead_time_days}-day lead time'

        return {
            'recommended_stock': round(recommended_stock, 1),
            'base_forecast': round(monthly_forecast, 1),
            'safety_buffer': round(safety_buffer, 1),
            'lead_time_buffer': round(lead_time_buffer, 1),
            'season_multiplier': season_multiplier,
            'urgency': urgency,
            'reason': reason
        }

    def generate_recommendations(self, current_stock=0, supplier_lead_time_days=14, order_preparation_days=7):
        """
        Generate actionable business recommendations based on forecasts and safety stock

        Args:
            current_stock: Current inventory level (default 0)
            supplier_lead_time_days: Days for supplier to deliver (default 14)
            order_preparation_days: Days needed to prepare order (default 7)

        Returns:
            dict with inventory, marketing, and staffing recommendations
        """
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta

        if not self.monthly_breakdown or not self.seasonal_profile:
            return {
                'inventory': [],
                'marketing': [],
                'staffing': [],
                'summary': 'Insufficient data for recommendations'
            }

        recommendations = {
            'inventory': [],
            'marketing': [],
            'staffing': [],
            'summary': ''
        }

        # Get seasonal profile data
        seasonal_profile = self.seasonal_profile
        peak_months = seasonal_profile.get('peak_months', [])
        low_months = seasonal_profile.get('low_months', [])
        zero_months = seasonal_profile.get('zero_months', [])

        # Analyze next 12 months
        today = datetime.now().date()
        total_preparation_days = supplier_lead_time_days + order_preparation_days

        for i in range(12):
            target_date = today + relativedelta(months=i+1)
            month_key = target_date.strftime('%Y-%m')
            month_num = target_date.month
            month_name = target_date.strftime('%B %Y')

            if month_key not in self.monthly_breakdown:
                continue

            month_data = self.monthly_breakdown[month_key]
            forecast_qty = month_data.get('quantity', 0)

            # Calculate safety stock for this month
            safety_stock = self.calculate_safety_stock(month_key, supplier_lead_time_days)
            recommended_stock = safety_stock['recommended_stock']
            urgency = safety_stock['urgency']

            # === INVENTORY RECOMMENDATIONS ===
            if forecast_qty > 0:
                # Calculate order deadline
                order_by_date = target_date - timedelta(days=total_preparation_days)
                days_until_order = (order_by_date - today).days

                # Only recommend if order date is in the future
                if days_until_order > 0:
                    # Determine if urgent
                    if month_num in peak_months:
                        priority = 'CRITICAL'
                        reason = f"Peak season ({seasonal_profile.get('peak_season_label', 'High demand period')})"
                    elif month_num in low_months:
                        priority = 'LOW'
                        reason = "Low season - maintain minimum stock"
                    else:
                        priority = 'MEDIUM'
                        reason = "Regular season"

                    # Calculate order quantity based on current stock
                    order_qty = max(0, recommended_stock - current_stock)

                    if order_qty > 0 or priority == 'CRITICAL':
                        recommendations['inventory'].append({
                            'type': 'ORDER',
                            'priority': priority,
                            'month': month_name,
                            'action': f"Order {int(order_qty)} units by {order_by_date.strftime('%b %d, %Y')}",
                            'details': {
                                'forecast': int(forecast_qty),
                                'recommended_stock': int(recommended_stock),
                                'current_stock': int(current_stock),
                                'order_quantity': int(order_qty),
                                'order_deadline': order_by_date.strftime('%Y-%m-%d'),
                                'days_until_order': days_until_order
                            },
                            'reason': reason
                        })

            # === MARKETING RECOMMENDATIONS ===
            # Suggest clearance sales for low/zero months
            if month_num in low_months or month_num in zero_months:
                if i >= 1 and i <= 6:  # Only recommend for next 6 months
                    recommendations['marketing'].append({
                        'type': 'CLEARANCE_SALE',
                        'priority': 'MEDIUM',
                        'month': month_name,
                        'action': f"Run clearance sale to move excess inventory",
                        'details': {
                            'forecast': int(forecast_qty),
                            'season': 'Off-season' if month_num in zero_months else 'Low season',
                            'suggested_discount': '15-25%'
                        },
                        'reason': f"{'No' if month_num in zero_months else 'Low'} demand expected - clear old stock"
                    })

            # Suggest promotional campaigns 1 month before peak
            if i > 0 and i <= 3:  # Next 3 months
                prev_month = (month_num - 1) if month_num > 1 else 12
                if prev_month in peak_months:
                    recommendations['marketing'].append({
                        'type': 'PROMOTIONAL_CAMPAIGN',
                        'priority': 'HIGH',
                        'month': today.strftime('%B %Y'),  # This month
                        'action': f"Launch promotional campaign before {month_name} peak",
                        'details': {
                            'peak_forecast': int(forecast_qty),
                            'campaign_start': today.strftime('%Y-%m-%d'),
                            'channels': ['Email', 'Social Media', 'Website Banner']
                        },
                        'reason': f"Peak season approaching - build awareness"
                    })

            # === STAFFING RECOMMENDATIONS ===
            # Suggest hiring for peak months
            if month_num in peak_months and i <= 3:  # Next 3 months
                peak_percentage = seasonal_profile.get('peak_percentage', 0)

                # Estimate staff based on forecast volume
                # Assume 1 staff can handle 500 units/month
                base_staff = 1
                additional_staff_needed = max(0, int(forecast_qty / 500))

                if additional_staff_needed > 0:
                    hire_by_date = target_date - timedelta(days=30)  # Hire 1 month before

                    recommendations['staffing'].append({
                        'type': 'HIRE_TEMPORARY',
                        'priority': 'HIGH',
                        'month': month_name,
                        'action': f"Hire {additional_staff_needed} temporary staff by {hire_by_date.strftime('%b %d, %Y')}",
                        'details': {
                            'forecast': int(forecast_qty),
                            'peak_percentage': peak_percentage,
                            'staff_needed': additional_staff_needed,
                            'hire_deadline': hire_by_date.strftime('%Y-%m-%d'),
                            'duration': '2-3 months'
                        },
                        'reason': f"Peak season - {peak_percentage}% of annual demand"
                    })

        # Sort recommendations by priority and date
        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        for category in ['inventory', 'marketing', 'staffing']:
            recommendations[category].sort(key=lambda x: priority_order.get(x['priority'], 99))

        # Generate summary
        total_recommendations = sum(len(v) for v in recommendations.values() if isinstance(v, list))
        critical_count = sum(1 for cat in ['inventory', 'marketing', 'staffing']
                           for rec in recommendations[cat]
                           if rec['priority'] == 'CRITICAL')

        recommendations['summary'] = f"{total_recommendations} recommendations generated " \
                                    f"({critical_count} critical, " \
                                    f"{len(recommendations['inventory'])} inventory, " \
                                    f"{len(recommendations['marketing'])} marketing, " \
                                    f"{len(recommendations['staffing'])} staffing)"

        return recommendations


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
