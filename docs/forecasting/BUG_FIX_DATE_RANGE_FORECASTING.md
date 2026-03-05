# Bug Fix: Date Range Forecasting Not Updating

## Issue Summary
When users changed the date range in the Sales Forecasting UI (e.g., from March 1-31 to March 1 - May 31), the forecast values displayed did not update to reflect the new date range. The system continued showing the old cached forecast data.

## Root Cause Analysis

### The Bug
The issue occurred when the system fell back to using legacy `SalesForecast` model (when no `SalesForecastBase` records were available). There were **two critical bugs**:

1. **Bug #1: Fixed Horizon Selection** (Line 1612)
   - The legacy fallback was hardcoded to always fetch the `'30d'` horizon, regardless of the user's selected date range
   - This was because `horizon = request.GET.get('horizon', '30d')` defaulted to '30d' when the user submitted `start_date` and `end_date` instead of `horizon`
   - Result: System always queried 30-day forecasts even when user requested 91 days

2. **Bug #2: No Date Range Filtering** (Lines 1643 and 1722)
   - The legacy code path used `date_range_data = f.forecast_data` which took the ENTIRE forecast data without filtering
   - This meant even if a 90-day horizon was loaded, it would show all 90 days instead of the user's selected range
   - Result: Date range selections had no effect on displayed values

## The Fix

### Changes Made to `/Users/sas/Repos/saspulse/dashboard/views.py`

#### 1. Auto-Select Best Horizon (Lines 1611-1623)
```python
# OLD CODE:
all_forecasts = SalesForecast.objects.filter(
    horizon=horizon,  # Always '30d'
    aggregation_level=level
)

# NEW CODE:
# Auto-select the best horizon that covers the requested date range
if num_days <= 30:
    best_horizon = '30d'
elif num_days <= 90:
    best_horizon = '90d'
elif num_days <= 180:
    best_horizon = '180d'
else:
    best_horizon = '365d'

all_forecasts = SalesForecast.objects.filter(
    horizon=best_horizon,  # Dynamically selected
    aggregation_level=level
)
```

#### 2. Filter Legacy Data by Date Range (Lines 1652-1658 and 1724-1730)
```python
# OLD CODE:
if use_legacy:
    date_range_data = f.forecast_data  # Uses entire dataset

# NEW CODE:
if use_legacy:
    # Filter forecast_data by date range
    date_range_data = {}
    for date_str, forecast_data in f.forecast_data.items():
        forecast_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if start_date <= forecast_date <= end_date:
            date_range_data[date_str] = forecast_data
```

## Impact

### Before the Fix:
- User selects March 1-31 (30 days) → Shows 90 units
- User changes to March 1 - May 31 (91 days) → **Still shows 90 units** (BUG!)

### After the Fix:
- User selects March 1-31 (30 days) → Shows 90 units
- User changes to March 1 - May 31 (91 days) → **Shows 270+ units** (CORRECT!)

## Test Scenario

Using example product "POLO 105J WHHS":
- Daily average forecast: ~3 units/day
- 30-day range: 30 × 3 = 90 units ✓
- 91-day range: 91 × 3 = 273 units ✓

## Files Modified
- `/Users/sas/Repos/saspulse/dashboard/views.py`

## Lines Changed
1. Lines 1611-1623: Auto-select best horizon based on date range
2. Lines 1652-1658: Filter legacy forecast data by date range (product view)
3. Lines 1724-1730: Filter legacy forecast data by date range (school/shop/category views)

## Cache Behavior
The cache logic was already correct:
- Cache key includes both `start_date` and `end_date`: `f'forecast_{level}_{start_date_str}_{end_date_str}'`
- Different date ranges create different cache keys
- The bug was in the data generation, not cache invalidation

## Notes
- The fix applies to the legacy `SalesForecast` fallback path
- When `SalesForecastBase` records are available, the system already works correctly via `get_date_range_forecast()`
- The background process generating forecasts should eventually populate `SalesForecastBase` records, which will use the more efficient date range extraction

## Date: 2026-03-05
## Status: FIXED
