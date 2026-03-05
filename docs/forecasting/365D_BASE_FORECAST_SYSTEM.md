# 365-Day Base Forecast System

## Overview

The 365-Day Base Forecast System is a modern approach to sales forecasting that generates **ONE comprehensive 365-day forecast per entity**, which can then be queried for any custom date range dynamically. This replaces the legacy approach of storing multiple fixed-horizon forecasts (30d, 90d, 180d, 365d).

## Key Concepts

### The Problem with Multiple Horizons

The legacy system stored four separate forecasts per entity:
- 30-day forecast
- 90-day forecast
- 180-day forecast
- 365-day forecast

**Issues:**
- **Storage Redundancy:** 4x storage usage (mostly duplicated data)
- **Maintenance Overhead:** Need to regenerate 4 forecasts per entity
- **Inflexibility:** Can't query custom date ranges (e.g., 45 days, 120 days)
- **Inconsistency:** Different horizons might use different models or data

### The 365-Day Base Solution

Generate **one 365-day forecast** per entity, stored as daily predictions in JSON format:

```json
{
  "2026-03-05": {"quantity": 12.5, "confidence_lower": 10.2, "confidence_upper": 14.8},
  "2026-03-06": {"quantity": 8.3, "confidence_lower": 6.7, "confidence_upper": 9.9},
  ...
  "2027-03-04": {"quantity": 15.1, "confidence_lower": 12.3, "confidence_upper": 17.9}
}
```

**Benefits:**
- **75% Storage Reduction:** One forecast instead of four
- **Infinite Flexibility:** Extract ANY date range (7d, 45d, 91d, 200d)
- **Fast Queries:** No AI computation needed for custom ranges
- **Consistency:** Single source of truth for all time horizons
- **Simplified Maintenance:** One regeneration per entity

## Architecture

### Database Models

#### SalesForecastBase
Stores the 365-day base forecasts:

```python
class SalesForecastBase(models.Model):
    forecast_id = CharField(max_length=100, unique=True)
    entity_name = CharField(max_length=255)  # School, Product, etc.
    aggregation_level = CharField(max_length=20)  # 'school', 'product', 'shop'
    daily_forecasts = JSONField()  # 365 days of predictions
    forecast_date = DateField()  # When forecast was generated
    accuracy_score = FloatField()  # Model accuracy (0-100)
    model_params = JSONField()  # Model configuration
```

**Key Methods:**
- `get_date_range_forecast(start_date, end_date)` - Extract any date range
- `get_total_quantity(start_date, end_date)` - Sum quantity for date range
- `get_date_stats(start_date, end_date)` - Get statistics (avg, min, max)

#### ForecastSchedule
Tracks when forecasts need regeneration:

```python
class ForecastSchedule(models.Model):
    entity_name = CharField(max_length=255)
    aggregation_level = CharField(max_length=20)
    last_generated = DateTimeField()
    next_generation_due = DateTimeField()  # Default: 30 days from last_generated
    generation_frequency_days = IntegerField(default=30)
    status = CharField(max_length=20)  # 'current', 'due', 'overdue'
```

**Properties:**
- `is_due` - Check if regeneration is needed
- `days_until_due` - Days remaining until due
- `days_since_generated` - Age of current forecast

### Management Commands

#### 1. generate_365d_forecasts.py

Generate 365-day base forecasts for all entities.

```bash
# Generate for all levels (school, product, shop)
python manage.py generate_365d_forecasts

# Generate for specific level
python manage.py generate_365d_forecasts --level product

# Force regeneration (overwrite existing)
python manage.py generate_365d_forecasts --force

# Test with limited entities
python manage.py generate_365d_forecasts --limit 10

# Minimum sales threshold
python manage.py generate_365d_forecasts --min-sales 50
```

**Features:**
- Progress tracking with ETA
- Parallel processing support
- Automatic schedule tracking
- Error handling and logging
- Validation (ensures 365 days)

#### 2. check_forecast_schedule.py

Monitor forecast health and trigger regeneration.

```bash
# Check status only
python manage.py check_forecast_schedule

# Auto-regenerate forecasts that are due
python manage.py check_forecast_schedule --regenerate

# Send email notifications for overdue
python manage.py check_forecast_schedule --notify

# Both regenerate and notify
python manage.py check_forecast_schedule --all

# Include forecasts due in next 14 days
python manage.py check_forecast_schedule --days-ahead 14
```

**Output Example:**
```
================================================================================
FORECAST SCHEDULE HEALTH CHECK
================================================================================

OVERALL STATISTICS
================================================================================
Total Forecasts:    1,245
Current:            1,180 (94.8%)
Due:                45 (3.6%)
Overdue:            20 (1.6%)

BREAKDOWN BY AGGREGATION LEVEL
================================================================================

SCHOOL:
  Total: 425 | Current: 410 | Due: 10 | Overdue: 5

PRODUCT:
  Total: 780 | Current: 740 | Due: 30 | Overdue: 10

SHOP:
  Total: 40 | Current: 30 | Due: 5 | Overdue: 5
```

### Views

#### forecast_health_dashboard
Web interface to monitor forecast health.

**URL:** `/dashboard/forecasting/health/`

**Features:**
- Overall statistics (total, current, due, overdue)
- Breakdown by aggregation level
- List of forecasts due for regeneration
- Recently generated forecasts
- Manual regeneration trigger

#### trigger_forecast_regeneration
API endpoint to trigger regeneration manually.

**URL:** `/dashboard/forecasting/regenerate/`

**Method:** POST

**Parameters:**
- `level` - Aggregation level ('school', 'product', 'shop', 'all')
- `force` - Force regeneration (true/false)

## Usage Guide

### Initial Setup

1. **Run migrations:**
   ```bash
   python manage.py migrate dashboard
   ```

2. **Generate initial 365-day forecasts:**
   ```bash
   # Use the provided script
   bash scripts/initial_365d_forecast_generation.sh

   # Or run manually
   python manage.py generate_365d_forecasts --level school --min-sales 10
   python manage.py generate_365d_forecasts --level product --min-sales 10
   python manage.py generate_365d_forecasts --level shop --min-sales 10
   ```

3. **Set up scheduled regeneration (cron):**
   ```bash
   # Edit crontab
   crontab -e

   # Add daily check at 2 AM
   0 2 * * * cd /Users/sas/Repos/saspulse && source env/bin/activate && python manage.py check_forecast_schedule --regenerate
   ```

   Or use the provided script:
   ```bash
   bash scripts/setup_forecast_cron.sh
   ```

### Querying Forecasts

#### From Python Code

```python
from dashboard.models import SalesForecastBase
from datetime import date, timedelta

# Get latest forecast for a school
forecast = SalesForecastBase.objects.filter(
    entity_name='Lincoln High School',
    aggregation_level='school'
).order_by('-forecast_date').first()

# Extract next 30 days
today = date.today()
end_date = today + timedelta(days=30)
forecast_30d = forecast.get_date_range_forecast(today, end_date)

# Extract custom range (45 days)
end_date_45d = today + timedelta(days=45)
forecast_45d = forecast.get_date_range_forecast(today, end_date_45d)

# Get total quantity
total_qty = forecast.get_total_quantity(today, end_date_45d)

# Get statistics
stats = forecast.get_date_stats(today, end_date_45d)
print(f"Average daily: {stats['average']:.2f}")
print(f"Total: {stats['total']:.2f}")
print(f"Range: {stats['min']:.2f} - {stats['max']:.2f}")
```

#### From Templates

The sales forecasting view automatically uses SalesForecastBase when available:

```html
<!-- Template: dashboard/sales_forecasting.html -->
{% if using_365d_base %}
  <span class="badge badge-success">Using 365-Day Base Forecasts</span>
{% else %}
  <span class="badge badge-warning">Using Legacy Forecasts</span>
{% endif %}
```

### Monitoring and Maintenance

#### Daily Monitoring

```bash
# Quick health check
python manage.py check_forecast_schedule

# Check with detailed output
python manage.py check_forecast_schedule --days-ahead 7
```

#### Weekly Regeneration

```bash
# Regenerate all forecasts due in next 7 days
python manage.py check_forecast_schedule --regenerate --days-ahead 7
```

#### Monthly Full Regeneration

```bash
# Force regenerate everything (computationally expensive!)
python manage.py generate_365d_forecasts --force
```

#### Web Dashboard

Visit: `http://your-domain/dashboard/forecasting/health/`

**Features:**
- View forecast health status
- See forecasts due for regeneration
- Trigger manual regeneration
- View regeneration history

### Scheduled Automation

#### Recommended Cron Schedule

```bash
# Daily health check with auto-regeneration (2 AM)
0 2 * * * cd /path/to/saspulse && python manage.py check_forecast_schedule --regenerate

# Weekly email notification (Monday 8 AM)
0 8 * * 1 cd /path/to/saspulse && python manage.py check_forecast_schedule --notify

# Monthly full regeneration (1st of month, 3 AM)
0 3 1 * * cd /path/to/saspulse && python manage.py generate_365d_forecasts --force
```

## Performance Considerations

### Storage Efficiency

**Legacy System (4 horizons):**
- 1 entity = 4 forecasts × ~365 days JSON = ~1,460 days stored
- 1,000 entities = 1.46M days stored

**365-Day Base System:**
- 1 entity = 1 forecast × 365 days JSON = 365 days stored
- 1,000 entities = 365K days stored

**Result:** 75% storage reduction

### Query Performance

**Date Range Extraction:**
- O(n) where n = days in range
- No AI computation required
- Typical query: <10ms for 90-day range

**Regeneration Time:**
- School level: ~5-10 seconds per entity (Prophet model)
- Product level: ~2-5 seconds per entity (depends on history)
- 1,000 entities: ~1-2 hours total (parallelizable)

### Optimization Tips

1. **Use caching** for frequently accessed date ranges
2. **Limit queries** to specific aggregation levels
3. **Index entity_name** for fast lookups
4. **Batch regenerate** during low-traffic hours
5. **Monitor** forecast health regularly

## Troubleshooting

### No Forecasts Found

**Symptom:** Views show "No forecasts available"

**Solutions:**
1. Check if forecasts exist:
   ```bash
   python manage.py shell
   >>> from dashboard.models import SalesForecastBase
   >>> SalesForecastBase.objects.count()
   ```

2. Generate forecasts:
   ```bash
   python manage.py generate_365d_forecasts
   ```

3. Check for errors in logs

### Forecasts Are Stale

**Symptom:** Forecasts are outdated (>30 days old)

**Solutions:**
1. Check schedule status:
   ```bash
   python manage.py check_forecast_schedule
   ```

2. Regenerate due forecasts:
   ```bash
   python manage.py check_forecast_schedule --regenerate
   ```

3. Force full regeneration:
   ```bash
   python manage.py generate_365d_forecasts --force
   ```

### Prophet Model Errors

**Symptom:** "Prophet not available" warnings

**Solutions:**
1. Install Prophet:
   ```bash
   pip install prophet
   ```

2. System falls back to Exponential Smoothing or Moving Average

### Forecast Has Wrong Number of Days

**Symptom:** Warning "Expected 365 days, got X"

**Cause:** Model failed to generate complete forecast

**Solutions:**
1. Check entity has sufficient historical data (>30 days)
2. Check for data quality issues
3. Review model parameters
4. Regenerate with `--force` flag

## Migration from Legacy System

### Step 1: Generate 365-Day Forecasts

```bash
# Generate alongside existing forecasts
python manage.py generate_365d_forecasts --level all
```

### Step 2: Test Dual System

Both systems run in parallel. Views automatically prefer SalesForecastBase.

```python
# Check which system is being used
context['using_365d_base']  # True = new system, False = legacy
```

### Step 3: Monitor Performance

Compare forecast accuracy and performance between systems.

### Step 4: Decommission Legacy (Optional)

Once confident in new system:

```python
# Archive legacy forecasts
from dashboard.models import SalesForecast
SalesForecast.objects.filter(forecast_date__lt='2026-03-01').delete()
```

## Best Practices

### Regeneration Frequency

- **Standard:** Every 30 days
- **High-volatility products:** Every 14 days
- **Seasonal products:** Before season starts
- **After major events:** Manual regeneration

### Data Quality

- **Minimum history:** 30 days for stable forecasts
- **Optimal history:** 90-365 days
- **Handle outliers:** Review before regeneration
- **Validate results:** Check accuracy scores

### Monitoring

- **Daily:** Automated health checks
- **Weekly:** Review overdue forecasts
- **Monthly:** Full regeneration
- **Quarterly:** Accuracy analysis

### Error Handling

- **Log all errors** for debugging
- **Continue on failure** (don't stop entire batch)
- **Retry failed** forecasts separately
- **Alert on critical** issues (>50% failure rate)

## API Reference

### SalesForecastBase Methods

#### get_date_range_forecast(start_date, end_date)
Extract forecast data for a specific date range.

**Args:**
- `start_date` (date|str): Start date
- `end_date` (date|str): End date

**Returns:**
- `dict`: {date: {quantity, confidence_lower, confidence_upper}}

#### get_total_quantity(start_date, end_date)
Calculate total forecasted quantity for a date range.

**Returns:**
- `float`: Total quantity

#### get_date_stats(start_date, end_date)
Get comprehensive statistics for a date range.

**Returns:**
- `dict`: {total, average, min, max, days, daily_data}

### ForecastSchedule Methods

#### update_status()
Update status based on current date.

Sets status to 'current', 'due', or 'overdue'.

#### Properties

- `is_due` - Boolean, True if regeneration needed
- `days_until_due` - Integer, days until next regeneration
- `days_since_generated` - Integer, age of forecast

## FAQ

### Q: Can I still use the old horizon-based system?

**A:** Yes! The system maintains backward compatibility. Views automatically use SalesForecastBase if available, otherwise fall back to SalesForecast.

### Q: What happens if a forecast fails to generate?

**A:** The system logs the error and continues with other entities. Failed forecasts can be regenerated individually.

### Q: How do I know if forecasts are being used?

**A:** Check the `using_365d_base` flag in the view context, or check the ForecastSchedule model.

### Q: Can I customize the regeneration frequency?

**A:** Yes! Update `generation_frequency_days` in the ForecastSchedule model.

### Q: What if I need forecasts beyond 365 days?

**A:** The system currently supports 365 days. For longer horizons, consider:
1. Extending the horizon in `generate_365d_forecasts.py`
2. Using statistical extrapolation
3. Chaining forecasts (regenerate after 6 months)

### Q: How do I handle seasonal products?

**A:** Prophet model automatically detects yearly seasonality. For custom seasonality:
1. Adjust Prophet parameters in the command
2. Regenerate before seasonal periods
3. Use custom model configurations

## Support and Resources

- **Documentation:** `/docs/forecasting/`
- **Management Commands:** `python manage.py help generate_365d_forecasts`
- **Web Dashboard:** `/dashboard/forecasting/health/`
- **Model Reference:** `dashboard/models.py`
- **View Reference:** `dashboard/views.py`

## Version History

- **v1.0 (2026-03-05):** Initial 365-day base forecast system
  - SalesForecastBase model
  - ForecastSchedule model
  - generate_365d_forecasts command
  - check_forecast_schedule command
  - Forecast health dashboard
  - Complete documentation

## Future Enhancements

- [ ] Multi-year forecasts (730 days)
- [ ] Automated accuracy tracking
- [ ] A/B testing different models
- [ ] Real-time forecast updates
- [ ] Machine learning model selection
- [ ] Forecast explainability dashboard
- [ ] Integration with inventory planning
- [ ] Mobile app for forecast monitoring
