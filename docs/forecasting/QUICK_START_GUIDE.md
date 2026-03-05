# 365-Day Base Forecast System - Quick Start Guide

## Overview

The 365-Day Base Forecast System generates ONE comprehensive 365-day forecast per entity, which can be queried for any custom date range. This replaces the legacy approach of storing multiple fixed horizons (30d, 90d, 180d, 365d).

## Benefits

- **75% Storage Reduction** - One forecast instead of four
- **Infinite Flexibility** - Extract any date range (7d, 45d, 91d, 200d)
- **Fast Queries** - No AI computation needed for custom ranges
- **Automated Maintenance** - Scheduled regeneration keeps data fresh

## Quick Start (5 Steps)

### Step 1: Apply Database Migrations

```bash
cd /Users/sas/Repos/saspulse
python manage.py migrate dashboard
```

**Creates:**
- `SalesForecastBase` table - stores 365-day forecasts
- `ForecastSchedule` table - tracks regeneration schedule

### Step 2: Generate Initial Forecasts

```bash
# Using the automated script (recommended)
bash scripts/initial_365d_forecast_generation.sh

# Or manually
python manage.py generate_365d_forecasts --level school --min-sales 10
python manage.py generate_365d_forecasts --level product --min-sales 10
python manage.py generate_365d_forecasts --level shop --min-sales 10
```

**Runtime:** 30-120 minutes depending on data size

### Step 3: Verify Forecasts

```bash
# Check forecast health
python manage.py check_forecast_schedule

# View in database
python manage.py shell
>>> from dashboard.models import SalesForecastBase
>>> SalesForecastBase.objects.count()
```

### Step 4: Set Up Automated Regeneration (Optional)

```bash
# View recommended cron schedule
bash scripts/setup_forecast_cron.sh --show

# Test commands
bash scripts/setup_forecast_cron.sh --test

# Install cron jobs
bash scripts/setup_forecast_cron.sh --install
```

**Recommended Schedule:**
- Daily health check (2 AM)
- Weekly notifications (Monday 8 AM)
- Monthly full regeneration (1st of month, 3 AM)

### Step 5: Access Forecasts

**Web Dashboard:**
- Forecasts: http://localhost:8000/dashboard/forecasting/
- Health Monitor: http://localhost:8000/dashboard/forecasting/health/

**Python API:**
```python
from dashboard.models import SalesForecastBase
from datetime import date, timedelta

# Get forecast
forecast = SalesForecastBase.objects.get(
    entity_name='Lincoln High School',
    aggregation_level='school'
)

# Extract 30-day forecast
today = date.today()
end_date = today + timedelta(days=30)
forecast_30d = forecast.get_date_range_forecast(today, end_date)

# Get total quantity
total = forecast.get_total_quantity(today, end_date)
```

## Common Tasks

### Regenerate All Forecasts

```bash
# Force regenerate everything
python manage.py generate_365d_forecasts --force
```

### Regenerate Specific Level

```bash
# Only product forecasts
python manage.py generate_365d_forecasts --level product --force
```

### Check Forecast Health

```bash
# View status
python manage.py check_forecast_schedule

# Auto-regenerate due forecasts
python manage.py check_forecast_schedule --regenerate

# Send email notifications
python manage.py check_forecast_schedule --notify
```

### Test with Small Dataset

```bash
# Generate only 10 forecasts (for testing)
python manage.py generate_365d_forecasts --level product --limit 10
```

## Monitoring

### Daily Health Check

```bash
python manage.py check_forecast_schedule
```

**Output:**
```
Total Forecasts:    1,245
Current:            1,180 (94.8%)
Due:                45 (3.6%)
Overdue:            20 (1.6%)
```

### Web Dashboard

Visit: http://localhost:8000/dashboard/forecasting/health/

**Features:**
- Overall statistics
- Forecasts due for regeneration
- Manual regeneration trigger
- Regeneration history

## Troubleshooting

### No Forecasts Found

```bash
# Check if forecasts exist
python manage.py shell
>>> from dashboard.models import SalesForecastBase
>>> SalesForecastBase.objects.count()

# If 0, generate forecasts
python manage.py generate_365d_forecasts
```

### Forecasts Are Stale

```bash
# Check schedule
python manage.py check_forecast_schedule

# Regenerate due forecasts
python manage.py check_forecast_schedule --regenerate
```

### Prophet Model Errors

```bash
# Install Prophet
pip install prophet

# System falls back to Exponential Smoothing if Prophet unavailable
```

## File Locations

### Management Commands
- `/Users/sas/Repos/saspulse/dashboard/management/commands/generate_365d_forecasts.py`
- `/Users/sas/Repos/saspulse/dashboard/management/commands/check_forecast_schedule.py`

### Models
- `/Users/sas/Repos/saspulse/dashboard/models.py`
  - `SalesForecastBase` (lines ~62-206)
  - `ForecastSchedule` (lines ~208-274)

### Views
- `/Users/sas/Repos/saspulse/dashboard/views.py`
  - `sales_forecasting` (lines ~1500-1834)
  - `forecast_health_dashboard` (lines ~2350+)

### Scripts
- `/Users/sas/Repos/saspulse/scripts/initial_365d_forecast_generation.sh`
- `/Users/sas/Repos/saspulse/scripts/setup_forecast_cron.sh`

### Documentation
- `/Users/sas/Repos/saspulse/docs/forecasting/365D_BASE_FORECAST_SYSTEM.md` (Full docs)
- `/Users/sas/Repos/saspulse/docs/forecasting/QUICK_START_GUIDE.md` (This file)

## Next Steps

1. **Monitor Forecasts:**
   ```bash
   python manage.py check_forecast_schedule
   ```

2. **Set Up Automation:**
   ```bash
   bash scripts/setup_forecast_cron.sh --install
   ```

3. **Integrate with Views:**
   - Forecasts automatically used in `/dashboard/forecasting/`
   - Check `using_365d_base` flag in templates

4. **Review Accuracy:**
   - Check `accuracy_score` field in forecasts
   - Compare with actual sales data

## Support

- **Full Documentation:** `/docs/forecasting/365D_BASE_FORECAST_SYSTEM.md`
- **Command Help:** `python manage.py help generate_365d_forecasts`
- **Web Dashboard:** http://localhost:8000/dashboard/forecasting/health/

## Version

System Version: 1.0 (March 5, 2026)
