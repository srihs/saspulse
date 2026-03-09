# SQL Query Comparison: School vs Shop Views

## Side-by-Side SQL Comparison

### SCHOOL VIEW (lines 2019-2046)

```python
# Query product-level forecasts, optionally filtered by school (sub_category)
sql = """
    SELECT DISTINCT sf.id, sf.forecast_id, sf.model_type, sf.aggregation_level,
           sf.entity_name, sf.entity_id, sf.daily_forecasts, sf.forecast_date,
           sf.training_data_start, sf.training_data_end, sf.mae, sf.mape, sf.rmse,
           sf.accuracy_score, sf.model_params, sf.created_at, sf.updated_at,
           p.sub_category as school_name
    FROM dashboard_salesforecastbase sf
    LEFT JOIN cin7_sync_productoption po ON po.code = sf.entity_name
    LEFT JOIN cin7_sync_product p ON p.cin7_id = po.cin7_product_id
    WHERE sf.aggregation_level = 'product'
      AND p.category_name LIKE '%Shop'
      AND p.category_name NOT LIKE 'Wholesale%'  ◄── EXTRA FILTER!
      AND p.sub_category IS NOT NULL
      AND p.sub_category != ''
"""
params = []

# Add school filter if provided
if school_filter:
    sql += " AND p.sub_category = %s"
    params.append(school_filter)

# Add search query if provided
if search_query:
    sql += " AND (sf.entity_name LIKE %s OR p.name LIKE %s OR p.sub_category LIKE %s)"
    params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])

sql += " ORDER BY p.sub_category, p.name, sf.entity_name, sf.forecast_date DESC"
#                  ^^^^^^^^^^^^^^  ◄── Orders by SCHOOL first
```

### SHOP VIEW (lines 1963-1993)

```python
# Query product-level forecasts, optionally filtered by shop (category_name)
sql = """
    SELECT DISTINCT sf.id, sf.forecast_id, sf.model_type, sf.aggregation_level,
           sf.entity_name, sf.entity_id, sf.daily_forecasts, sf.forecast_date,
           sf.training_data_start, sf.training_data_end, sf.mae, sf.mape, sf.rmse,
           sf.accuracy_score, sf.model_params, sf.created_at, sf.updated_at,
           p.category_name as location_name,  ◄── EXTRA COLUMN!
           p.sub_category as school_name
    FROM dashboard_salesforecastbase sf
    LEFT JOIN cin7_sync_productoption po ON po.code = sf.entity_name
    LEFT JOIN cin7_sync_product p ON p.cin7_id = po.cin7_product_id
    WHERE sf.aggregation_level = 'product'
      AND p.category_name LIKE '%Shop'
      -- NO Wholesale exclusion!  ◄── MISSING FILTER!
      AND p.sub_category IS NOT NULL
      AND p.sub_category != ''
"""
params = []

# Add shop filter if provided
if shop_filter:
    sql += " AND p.category_name = %s"
    params.append(shop_filter)
else:
    # Show all shop products
    sql += " AND p.category_name LIKE '%Shop'"

# Filter out products without school assignment
sql += " AND p.sub_category IS NOT NULL AND p.sub_category != ''"

# Add search query if provided
if search_query:
    sql += " AND (sf.entity_name LIKE %s OR p.name LIKE %s OR p.sub_category LIKE %s OR p.category_name LIKE %s)"
    params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])

sql += " ORDER BY p.category_name, p.sub_category, p.name, sf.entity_name, sf.forecast_date DESC"
#                  ^^^^^^^^^^^^^^^^  ◄── Orders by LOCATION first
```

## Key Differences Table

| Aspect | SCHOOL VIEW | SHOP VIEW | Impact |
|--------|-------------|-----------|--------|
| **SELECT columns** | `p.sub_category as school_name` | `p.category_name as location_name, p.sub_category as school_name` | Shop view gets location info |
| **Wholesale filter** | `AND p.category_name NOT LIKE 'Wholesale%'` | *(missing)* | School view excludes Wholesale shops |
| **ORDER BY** | `p.sub_category, p.name, ...` | `p.category_name, p.sub_category, p.name, ...` | **CRITICAL**: Different ordering |
| **SKU limit** | `if len(base_forecasts) >= 2000: break` (line 2144) | `if len(base_forecasts) >= 2000: break` (line 2009) | Same limit, different results due to ORDER BY |
| **School limit** | `[:100]` (line 2698) | `[:100]` (line 2426) | Same limit |

## How ORDER BY Causes Different Results

### SCHOOL VIEW Ordering
```
ORDER BY p.sub_category, p.name, sf.entity_name, sf.forecast_date DESC
         ^^^^^^^^^^^^^^
         School name first
```

**Result**: SKUs are returned grouped by school alphabetically:
```
1. Alfriston College - Product A - SKU1
2. Alfriston College - Product A - SKU2
3. Alfriston College - Product B - SKU1
...
141. Alfriston College - (last SKU)
142. Ardmore School - Product A - SKU1
143. Ardmore School - Product A - SKU2
...
(continues until 2000 SKUs reached, somewhere around "M" schools)
```

### SHOP VIEW Ordering
```
ORDER BY p.category_name, p.sub_category, p.name, sf.entity_name, sf.forecast_date DESC
         ^^^^^^^^^^^^^^^^
         Location (shop) first
```

**Result**: SKUs are returned grouped by location first:
```
1. Avondale Shop - Kelston Boys High School - Product A - SKU1
2. Avondale Shop - Kelston Boys High School - Product A - SKU2
...
350. Avondale Shop - (all SKUs from Avondale Shop)
351. Cambridge Shop - Cambridge College - Product A - SKU1
352. Cambridge Shop - Cambridge College - Product A - SKU2
...
800. Cambridge Shop - (all SKUs from Cambridge Shop)
801. Helensville Shop - Kaipara College - Product A - SKU1
...
(continues until 2000 SKUs reached)
```

## Why This Creates Discrepancy

With 4,289 total SKUs and a 2,000 SKU limit:

**SCHOOL VIEW**:
- Gets a **representative sample** of schools alphabetically (A through M)
- Later alphabet schools (N-Z) are excluded or partially included
- Example: Matamata College (M) is included, but Rutherford College (R) is excluded

**SHOP VIEW**:
- Gets **ALL SKUs from early alphabet locations**
- "Avondale Shop" loads completely (includes Rutherford College, Te Atatu, Western Springs)
- Later alphabet locations may be excluded
- Example: Rutherford College is in "Avondale Shop" which loads early, so it's included

## Example Discrepancy

**Rutherford College**:
- **90 product shortages** (one of the highest!)
- **Location**: Avondale Shop (alphabetically early)
- **School name**: Rutherford College (alphabetically late)
- **Appears in SHOP view**: YES (Avondale Shop loads all its SKUs)
- **Appears in SCHOOL view**: NO (2000 limit hit before reaching "R" schools)

This is a critical issue because Rutherford College has significant shortages but is invisible in the school view!

## Python Filtering Logic (After SQL)

Both views apply the same filtering logic after the SQL query:

```python
# Group forecasts by school
school_groups = defaultdict(list)
for f in forecasts:
    school_name = sku_to_school.get(f.entity_name)
    if school_name:
        school_groups[school_name].append(f)

# Process each school group
forecast_list = []
for school_name, school_forecasts in sorted(school_groups.items()):
    school_variations = []
    school_total_quantity = 0

    for f in school_forecasts:
        # Calculate stock gap
        stock_gap = (stock_on_hand + incoming_stock) - forecasted_stock

        # Filter: Only show products with negative stock gap (shortages)
        if stock_gap >= 0:
            continue  # ◄── KEY FILTER

        school_variations.append(variation_data)
        school_total_quantity += forecasted_stock

    # Only add school if it has variations after filtering
    if school_variations:
        forecast_list.append({...})
```

The stock gap filter is identical in both views, so the discrepancy is purely due to the SQL query differences.
