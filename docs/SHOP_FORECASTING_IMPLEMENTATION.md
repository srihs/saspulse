# Shop-Level Forecasting: Smart Aggregation Implementation

## Overview

This document explains the new smart aggregation approach for shop-level forecasting. Instead of generating separate shop forecasts, we now dynamically aggregate existing product-level forecasts by shop category.

## Why This Approach?

### The Problem
Previously, the system generated separate shop-level forecasts (16 forecasts in the database). However, this created several issues:
- **Data duplication**: Same information stored twice (products + shops)
- **Potential discrepancies**: Shop totals might not match the sum of products
- **Extra maintenance**: Need to regenerate shop forecasts whenever product forecasts change
- **Redundancy**: Shops are just a grouping of products by `category_name`

### The Solution
**Dynamic Aggregation**: Aggregate product forecasts on-the-fly by their shop category.

### Benefits
1. **No separate generation needed**: Uses existing product forecasts
2. **Always up-to-date**: Reflects latest product forecast data
3. **Mathematically correct**: Shop total = Σ(products in that shop)
4. **No data duplication**: Single source of truth (product forecasts)
5. **Guaranteed consistency**: Eliminates discrepancies

## Technical Implementation

### 1. Database Schema Update

Updated `/Users/sas/Repos/saspulse/cin7/models.py`:

```python
class Product(TimestampedModel):
    # ... existing fields ...

    # Classification
    brand = models.CharField(max_length=250, blank=True, db_index=True)
    category = models.CharField(max_length=250, blank=True, db_index=True)
    category_id = models.BigIntegerField(null=True, blank=True, db_index=True, help_text="Primary category ID")
    category_name = models.CharField(max_length=255, blank=True, db_index=True, help_text="Primary category name (e.g., 'Avondale Shop')")
    # ... other fields ...
```

**Key Addition**: `category_name` field to identify which shop a product belongs to.

### 2. Shop Aggregation Function

Created `get_shop_forecasts_from_products()` helper function in `/Users/sas/Repos/saspulse/dashboard/views.py`:

```python
def get_shop_forecasts_from_products(start_date, end_date, search_query=None):
    """
    Aggregate product-level forecasts by shop category (category_name ending with 'Shop')

    Process:
    1. Query all product forecasts with JOIN to cin7_sync_product
    2. Filter products where category_name LIKE '%Shop'
    3. Group by category_name (shop name)
    4. Sum daily forecast quantities for each shop
    5. Calculate average accuracy metrics
    6. Return aggregated shop forecasts
    """
```

**SQL Query**:
```sql
SELECT
    p.category_name as shop_name,
    sf.daily_forecasts,
    sf.accuracy_score,
    sf.mae,
    sf.mape,
    sf.model_params,
    sf.entity_name as sku_code
FROM dashboard_salesforecastbase sf
JOIN cin7_sync_productoption po ON po.code = sf.entity_name
JOIN cin7_sync_product p ON p.cin7_id = po.cin7_product_id
WHERE sf.aggregation_level = 'product'
  AND p.category_name LIKE %s
ORDER BY p.category_name, sf.entity_name
```

**Aggregation Logic**:
```python
# For each product forecast
for each product in products:
    for each date in forecast_range:
        shop_totals[shop_name][date] += product.quantity
```

### 3. View Integration

Updated `sales_forecasting()` view to handle shop level specially:

```python
# SPECIAL HANDLING FOR SHOP LEVEL
if level == 'shop':
    # Use smart aggregation approach
    forecast_list = get_shop_forecasts_from_products(start_date, end_date, search_query)
    use_legacy = False
    no_forecasts_available = len(forecast_list) == 0

# NORMAL HANDLING FOR OTHER LEVELS (school, product, category)
elif level != 'shop':
    # Original logic for querying base forecasts
    ...
```

## Results

### Test Results (2026-03-07 to 2026-04-06)

**Aggregation Performance**:
- Source: 5,210 product-level forecasts
- Products with shop categories: 4,498 (86% of all products)
- Aggregated into: **15 distinct shops**
- Processing time: ~13 seconds (includes SQL query + aggregation)

**Shop Breakdown**:
| Shop Name | Products | Total Forecast (30 days) |
|-----------|----------|--------------------------|
| Kerikeri Shop | 133 | 537,937 units |
| Shop (uncategorized) | 2 | 400,665 units |
| Wellington Shop | 111 | 254,984 units |
| Pukekohe Shop | 520 | 221,618 units |
| Cambridge Shop | 171 | 167,501 units |
| Papakura Shop | 814 | 111,030 units |
| Manukau Shop | 1,024 | 94,891 units |
| Pakuranga Shop | 196 | 82,172 units |
| North Harbour Shop | 179 | 77,200 units |
| Avondale Shop | 719 | 50,300 units |
| Rotorua Shop | 166 | 20,760 units |
| Long Bay Shop | 233 | 10,197 units |
| Helensville Shop | 92 | 7,613 units |
| Matamata Shop | 97 | 3,930 units |
| Kaitaia Shop | 41 | 363 units |

**Total**: 4,498 products → 2,041,161 units forecasted across 15 shops

## Cleaning Up Redundant Data

### Old Shop Forecasts
The database currently contains **16 redundant shop-level forecasts** that were generated separately:

```sql
SELECT COUNT(*) FROM dashboard_salesforecastbase WHERE aggregation_level = 'shop';
-- Result: 16
```

### Cleanup Script
Use `/Users/sas/Repos/saspulse/cleanup_shop_forecasts.py` to remove them:

```bash
python3 cleanup_shop_forecasts.py
```

This will:
1. Show existing shop forecasts
2. Ask for confirmation
3. Delete them from `dashboard_salesforecastbase`

**Note**: After deletion, shop forecasts will continue to work via dynamic aggregation.

## Testing

### Test Scripts

1. **Test Aggregation Logic**:
   ```bash
   python3 test_shop_aggregation.py
   ```

2. **Test Aggregation Function**:
   ```bash
   python3 test_shop_direct.py
   ```

3. **Test View Integration**:
   ```bash
   python3 test_shop_view.py
   ```

### Browser Testing

Navigate to:
```
http://localhost:8000/forecasting/?level=shop&start_date=2026-03-07&end_date=2026-04-06
```

Expected results:
- 15 shops displayed
- Each shop shows total forecast from aggregated products
- Model column shows "Product Aggregation"
- Product count metadata available

## Search/Filter Support

The aggregation supports search filtering by shop name:

```
/forecasting/?level=shop&start_date=2026-03-07&end_date=2026-04-06&search=Avondale
```

This will show only shops matching "Avondale" (e.g., "Avondale Shop").

## Logging

Comprehensive logging added for debugging:

```
INFO === SHOP-LEVEL FORECAST REQUEST ===
INFO Date range: 2026-03-07 to 2026-04-06
INFO Search query:
INFO Using smart aggregation: summing product forecasts by shop category
INFO === AGGREGATING SHOP FORECASTS FROM PRODUCTS ===
INFO Found 4498 product forecasts belonging to shops
INFO Aggregated into 15 shops
INFO Shop: Avondale Shop - 719 products, Total: 50299.9 units
...
INFO === SHOP AGGREGATION COMPLETE: 15 shops ===
```

## Architecture Comparison

### Old Approach
```
Product Forecasts (5210)
         +
Shop Forecasts (16) ← Generated separately
         ↓
Potential discrepancy issue
```

### New Approach
```
Product Forecasts (5210)
         ↓
    Aggregate by shop category (category_name)
         ↓
Shop Forecasts (15) ← Dynamically computed
         ↓
Always consistent (shop = Σ products)
```

## Edge Cases Handled

1. **Products without category_name**: Excluded from shop aggregation
2. **Empty search results**: Returns empty list gracefully
3. **Missing daily_forecasts data**: Skipped with warning log
4. **Invalid date ranges**: Error handling in date parsing
5. **No shop products**: Returns `no_forecasts_available = True`

## Future Enhancements

1. **Caching**: Add Redis/Memcached for aggregated results (with TTL)
2. **Incremental aggregation**: Update only changed products
3. **Stock data**: Include shop-level stock information
4. **Drill-down**: Click shop → view products in that shop
5. **Comparison**: Compare shop performance over time

## Files Modified

1. `/Users/sas/Repos/saspulse/cin7/models.py` - Added `category_name` and `category_id` fields
2. `/Users/sas/Repos/saspulse/dashboard/views.py` - Added aggregation function and special shop handling

## Files Created

1. `/Users/sas/Repos/saspulse/test_shop_aggregation.py` - Test data availability
2. `/Users/sas/Repos/saspulse/test_shop_direct.py` - Test aggregation function
3. `/Users/sas/Repos/saspulse/test_shop_view.py` - Test view integration
4. `/Users/sas/Repos/saspulse/cleanup_shop_forecasts.py` - Remove redundant forecasts
5. `/Users/sas/Repos/saspulse/SHOP_FORECASTING_IMPLEMENTATION.md` - This document

## Conclusion

The smart aggregation approach provides a robust, maintainable solution for shop-level forecasting. By leveraging existing product forecasts, we eliminate data duplication and ensure mathematical consistency while maintaining real-time accuracy.

**Key Takeaway**: Shops are just a view on products - they should be computed, not stored.
