# Forecast Data Investigation Report

## Issue Summary
User reports that **NO forecast data is showing at ANY level** (product, school, shop) on the forecasting page.

## Database Investigation Results

### Key Findings

1. **Total Records**: 11,418 SalesForecastBase records exist
2. **Forecast Date Range**: 2026-03-09 to 2026-03-17 (latest)
3. **Daily Forecasts Population**:
   - Product level: 3,126/11,243 records (27.8%) have daily_forecasts data
   - School level: 153/159 records (96.2%) have daily_forecasts data
   - Shop level: 16/16 records (100%) have daily_forecasts data
4. **Daily Forecasts Coverage**: Each record with data contains 365 days of predictions
   - Example: Record with forecast_date=2026-03-17 contains predictions from 2026-03-17 to 2027-03-16

### Critical Discovery

**The data EXISTS and is ACCESSIBLE!**

- Latest forecast was generated on **2026-03-17**
- User is querying for dates **2026-03-18 to 2026-04-17**
- The `get_date_range_forecast()` method successfully extracts data for this range from the daily_forecasts JSON field
- Test extraction yielded **31 days of data** with valid quantities

## Root Cause Analysis

### What's Working Correctly

1. ✅ **Forecast Model**: SalesForecastBase model structure is correct
2. ✅ **Date Extraction Method**: `get_date_range_forecast()` works perfectly
3. ✅ **SQL Queries**: Not filtering by forecast_date in WHERE clause (correct)
4. ✅ **Deduplication Logic**: Keeps latest forecast for each entity (correct)

### Potential Issues Identified

1. **JOIN Failures**: The SQL joins with cin7_sync_productoption and cin7_sync_product tables:
   - If product doesn't exist in these tables, LEFT JOIN returns NULL values
   - Filters checking `p.category_name` and `p.sub_category` may exclude records with NULL values
   - This could explain why 72% of product forecasts have empty daily_forecasts

2. **User School Filter**: If `user_school_subcategories` is empty or doesn't match any products:
   - The query: `AND p.sub_category IN (...)` would return no results
   - This would affect Sales Team users with restricted access

3. **Category Filters**: Multiple category filters in shop-level query:
   ```sql
   AND (p.category_name LIKE '%Shop' OR p.category_name LIKE '%Store')
   AND p.category_name NOT IN ('Shop', 'Store')
   AND p.category_name NOT LIKE 'Wholesale%'
   AND p.sub_category IS NOT NULL AND p.sub_category != ''
   ```
   - If products don't meet these criteria, they're excluded
   - NULL values from LEFT JOIN would fail these checks

## Implemented Fixes

### 1. Comprehensive Debug Logging

Added extensive logging at multiple points in `/Users/sas/Repos/saspulse/dashboard/views.py`:

#### Shop Level (3-level view without shop_filter)
- Line 2066-2093: Log raw SQL results, sample forecast, and daily_forecasts structure
- Line 2607-2653: Log mapping process and location group creation
- Line 2674-2686: Log first product's date extraction details
- Line 2781-2787: Log processing summary and final counts

#### Shop Level (2-level view with shop_filter)
- Line 2482-2525: Log school groups and first product date extraction
- Line 2597-2603: Log processing summary

#### Product Level
- Line 2342-2345: Initialize counters
- Line 2361-2373: Log first product's date extraction details
- Line 2435-2468: Log processing summary and final counts

#### School Level
- Line 2855-2863: Log school groups being processed
- Line 2877-2889: Log first product's date extraction details
- Line 2972-2980: Log processing summary and final counts

### 2. Enhanced Logging Information

Each log section now tracks:
- Total forecast records retrieved from database
- Sample record details (entity_name, forecast_date, daily_forecasts structure)
- Date extraction process (requested range vs. available range)
- Number of products processed vs. skipped (zero quantity, already requested)
- Final counts after filtering and limiting

### 3. SQL Query Logging

Added logging to show:
- Exact SQL query being executed
- Parameter values
- User school subcategories (for debugging access control)

## Next Steps for User

### 1. Test the Forecasting Page
Access the forecasting page and check the server logs. The new debug logging will show:

```
=== SHOP-LEVEL FORECAST REQUEST ===
Date range: 2026-03-18 to 2026-04-17
Search query: None
Shop filter: None
User school subcategories: [list of schools]

DEBUG: Executing SQL query with N parameters
DEBUG: SQL query: [full SQL]
DEBUG: Parameters: [parameter values]

DEBUG: Raw SQL returned X total forecast records
DEBUG: Sample forecast: entity_name=..., forecast_date=...
DEBUG: Sample daily_forecasts type: <class 'dict'>
DEBUG: Sample has 365 dates in daily_forecasts
DEBUG: First 3 dates: ['2026-03-17', '2026-03-18', '2026-03-19']
DEBUG: Last 3 dates: ['2027-03-14', '2027-03-15', '2027-03-16']

DEBUG: After deduplication, X unique entities

DEBUG: Starting with X forecast records
DEBUG: Mapped X SKUs to locations, X failures
DEBUG: Created X location groups

DEBUG: First product date extraction:
  - Entity: 50125
  - Forecast date: 2026-03-17
  - Requested range: 2026-03-18 to 2026-04-17
  - Daily forecasts date range: 2026-03-17 to 2027-03-16 (365 days)
  - Extracted dates: 31 days
  - Extracted range: 2026-03-18 to 2026-04-17

DEBUG: Processed X products, skipped X with zero quantity
DEBUG: Final forecast_list has X locations after limit
```

### 2. Identify Where Data Is Lost

Based on the logs, you'll see:
- If SQL returns 0 records → JOIN or filter issue
- If SQL returns records but deduplication yields 0 → Duplicate entity_names
- If records pass deduplication but date extraction yields 0 days → Date range issue
- If date extraction works but total_qty is 0 → Forecast predictions are all zero
- If everything works but final list is empty → Filters are too restrictive

### 3. Common Scenarios & Solutions

#### Scenario A: SQL Returns 0 Records
**Cause**: JOIN failures or overly restrictive filters

**Solution**:
- Check if products exist in cin7_sync_productoption table
- Verify category_name and sub_category values
- Check user_school_subcategories for Sales Team users
- May need to adjust filters or fix product data

#### Scenario B: Daily Forecasts Are Empty
**Cause**: 72% of product forecasts have empty daily_forecasts

**Solution**:
- Run forecast generation command: `python manage.py generate_365d_forecasts`
- This should populate daily_forecasts for all products
- Check which command was used (generate_simple_forecasts vs generate_365d_forecasts)

#### Scenario C: All Quantities Are Zero
**Cause**: Forecast model predicting zero sales

**Solution**:
- Review forecast model parameters
- Check training data quality
- May need to retrain forecasts with better historical data

#### Scenario D: User Access Restriction
**Cause**: Sales Team user has no assigned schools

**Solution**:
- Verify user has schools assigned in `user_school_subcategories`
- Admin users should see all data (bypass restriction)
- Check UserProfile or Group assignments

## Files Modified

1. `/Users/sas/Repos/saspulse/dashboard/views.py`
   - Added comprehensive debug logging throughout get_sales_forecasting_data()
   - No logic changes, only observability improvements

2. `/Users/sas/Repos/saspulse/test_forecast_data.py` (NEW)
   - Standalone script to verify database data and date extraction
   - Run with: `python3 test_forecast_data.py`

3. `/Users/sas/Repos/saspulse/FORECAST_DEBUG_REPORT.md` (THIS FILE)
   - Complete investigation report and findings

## Test Script Results

```bash
$ python3 test_forecast_data.py
```

Output shows:
- ✅ 11,418 forecast records exist
- ✅ Date extraction method works correctly
- ✅ Data is available for requested date range (2026-03-18 to 2026-04-17)
- ⚠️  Latest forecast_date is 2026-03-17 (data IS available in daily_forecasts)
- ⚠️  72% of product forecasts have empty daily_forecasts (may need regeneration)

## Recommendations

### Immediate Actions
1. ✅ Check server logs after accessing forecasting page
2. ✅ Look for the DEBUG messages to identify where data is being filtered out
3. ✅ Share the relevant log section for further analysis

### Short-term Fixes
1. If JOIN failures: Fix product data or adjust SQL to INNER JOIN
2. If empty daily_forecasts: Run `generate_365d_forecasts` command
3. If user access: Verify Sales Team users have assigned schools
4. If filters too restrictive: Review and adjust category/school filters

### Long-term Improvements
1. Monitor daily_forecasts population rate (should be >90%)
2. Set up automated forecast generation (daily/weekly)
3. Add data quality checks before generating forecasts
4. Consider caching forecast data for better performance
5. Add user-facing error messages when no data is available

## Status

**Investigation Complete** ✅
**Debug Logging Implemented** ✅
**Test Script Created** ✅
**Awaiting User Testing** ⏳

The extensive logging will now show exactly where and why data is being filtered out. Once we see the actual logs, we can implement the specific fix needed.

---

**Generated**: 2026-03-18
**Engineer**: Claude (Anthropic)
**Files Changed**: 2 modified, 2 created
**Status**: Ready for testing
