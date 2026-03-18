# 2-Year Rolling Forecast - Quick Start Guide

## Quick Commands

### Generate 24-Month Simple Forecasts (Monthly)
```bash
# For all products
python3 manage.py generate_simple_forecasts --level product

# For all schools
python3 manage.py generate_simple_forecasts --level school

# Force regeneration
python3 manage.py generate_simple_forecasts --level product --force
```

### Generate 2-Year Daily Forecasts (730 days)
```bash
# For all products (2 years)
python3 manage.py generate_365d_forecasts --level product --horizon-days 730

# For all schools (2 years)
python3 manage.py generate_365d_forecasts --level school --horizon-days 730

# Test with limited products
python3 manage.py generate_365d_forecasts --level product --horizon-days 730 --limit 10
```

## What Changed?

### Before (12-month forecasts)
- Forecasted **12 months** ahead
- Used only **historical actual sales**
- Forecast horizon: Current month → +12 months

### After (24-month forecasts)
- Forecasts **24 months** ahead
- Uses **forecasted values** when actual sales don't exist
- Forecast horizon: Current month → +24 months
- Tracks expiration date (`forecast_valid_until`)

## How It Works

### Example Scenario (March 2026)

**Forecasting April 2027:**
```
1. Check for actual sales in April 2027 → None (hasn't happened yet)
2. Use April 2026 forecast as baseline → 115 units
3. Apply seasonal factor (April is 20% above average) → 138 units
4. Apply growth trend (10.5% annual growth) → 152.5 units
5. Set confidence to "medium" (forecast-based, 1 year ahead)
```

**Result:**
```json
{
    "2027-04": {
        "quantity": 152.5,
        "baseline": 115,
        "baseline_source": "forecast",
        "seasonal_factor": 1.2,
        "growth_rate": 0.105,
        "confidence": "medium"
    }
}
```

## Checking Forecast Validity

### In Django Shell
```python
from dashboard.models import SalesForecastBase

# Get a forecast
forecast = SalesForecastBase.objects.filter(
    entity_name='SHIRT-001',
    aggregation_level='product'
).first()

# Check if valid
if forecast.is_forecast_valid():
    print(f"Valid until: {forecast.forecast_valid_until}")
else:
    print("Forecast expired - regeneration needed")

# Get specific month
april_2027 = forecast.get_monthly_forecast(2027, 4)
print(f"April 2027: {april_2027['quantity']} units")
```

### Using SQL
```sql
-- Check all forecasts
SELECT
    entity_name,
    forecast_date,
    forecast_valid_until,
    DATEDIFF(forecast_valid_until, CURDATE()) as days_remaining
FROM dashboard_salesforecastbase
WHERE aggregation_level = 'product'
ORDER BY days_remaining;

-- Find expired forecasts
SELECT COUNT(*)
FROM dashboard_salesforecastbase
WHERE forecast_valid_until < CURDATE();
```

## Common Issues

### Issue: "Skipped: Insufficient data"
**Solution:** Product needs at least 6 months of sales history
```bash
# Lower threshold for testing
python3 manage.py generate_simple_forecasts --level product --years 2
```

### Issue: All forecasts show 0 quantity
**Solution:** Run forecast generation twice
```bash
# First run establishes baseline
python3 manage.py generate_simple_forecasts --level product

# Second run uses first run's forecasts as baseline
python3 manage.py generate_simple_forecasts --level product --force
```

### Issue: Forecast shows as expired
**Solution:** Regenerate forecasts
```bash
python3 manage.py generate_simple_forecasts --level product --force
```

## Monitoring

### Check Forecast Coverage
```sql
SELECT
    aggregation_level,
    COUNT(*) as total,
    AVG(JSON_LENGTH(monthly_breakdown)) as avg_months
FROM dashboard_salesforecastbase
GROUP BY aggregation_level;
```

**Expected:** `avg_months` should be 24

### Check Validity Status
```sql
SELECT
    CASE
        WHEN forecast_valid_until >= CURDATE() THEN 'Valid'
        ELSE 'Expired'
    END as status,
    COUNT(*) as count
FROM dashboard_salesforecastbase
GROUP BY status;
```

## Best Practices

1. **Run monthly on the 1st** to keep forecasts fresh
2. **Use --force flag** sparingly (overwrites all existing forecasts)
3. **Monitor expiration** - regenerate when `forecast_valid_until` < 90 days from now
4. **Check confidence levels** - low confidence forecasts may need manual review

## Confidence Levels Explained

- **High**: Based on actual sales, 1-12 months ahead
- **Medium**: Based on forecasts, 1-12 months ahead OR actuals 13-18 months ahead
- **Low**: Based on forecasts 13+ months ahead OR historical averages

## Quick Stats

- **Products**: 2,268 Store SKUs
- **Forecast Horizon**: 24 months (730 days)
- **Historical Data**: Last 3 years
- **Update Frequency**: Monthly (recommended)
- **Database Field**: `forecast_valid_until` (tracks expiration)

## Need More Info?

See detailed documentation: `FORECAST_2YEAR_IMPLEMENTATION.md`
