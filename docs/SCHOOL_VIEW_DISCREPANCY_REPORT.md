# School-Level vs Shop-Level View Discrepancy Analysis

## Problem Statement

When viewing forecasts for the same date range (2026-03-09 to 2026-04-08):
- **School-level view**: Shows 19 schools
- **Shop-level view**: Shows 23 schools

This discrepancy is confusing and indicates inconsistent data filtering between the two views.

## Root Cause Analysis

### 1. SQL Query Differences

**Location in code**: `/Users/sas/Repos/saspulse/dashboard/views.py`

**SCHOOL VIEW** (lines 2019-2046):
```sql
SELECT DISTINCT sf.id, sf.forecast_id, ...
       p.sub_category as school_name
FROM dashboard_salesforecastbase sf
LEFT JOIN cin7_sync_productoption po ON po.code = sf.entity_name
LEFT JOIN cin7_sync_product p ON p.cin7_id = po.cin7_product_id
WHERE sf.aggregation_level = 'product'
  AND p.category_name LIKE '%Shop'
  AND p.category_name NOT LIKE 'Wholesale%'  -- DIFFERENCE #1
  AND p.sub_category IS NOT NULL
  AND p.sub_category != ''
ORDER BY p.sub_category, p.name, sf.entity_name, sf.forecast_date DESC  -- DIFFERENCE #2
```

**SHOP VIEW** (lines 1963-1993):
```sql
SELECT DISTINCT sf.id, sf.forecast_id, ...
       p.category_name as location_name,
       p.sub_category as school_name
FROM dashboard_salesforecastbase sf
LEFT JOIN cin7_sync_productoption po ON po.code = sf.entity_name
LEFT JOIN cin7_sync_product p ON p.cin7_id = po.cin7_product_id
WHERE sf.aggregation_level = 'product'
  AND p.category_name LIKE '%Shop'
  -- NO Wholesale exclusion!  -- DIFFERENCE #1
  AND p.sub_category IS NOT NULL
  AND p.sub_category != ''
ORDER BY p.category_name, p.sub_category, p.name, sf.entity_name, sf.forecast_date DESC  -- DIFFERENCE #2
```

### 2. Key Differences

#### Difference #1: Wholesale Filter
- **SCHOOL VIEW**: Excludes `category_name NOT LIKE 'Wholesale%'`
- **SHOP VIEW**: Includes all categories matching `'%Shop'`
- **Impact**: Minimal (no Wholesale Shop categories exist in current data)

#### Difference #2: ORDER BY Clause (THE MAIN ISSUE!)
- **SCHOOL VIEW**: `ORDER BY p.sub_category, ...` (school first)
- **SHOP VIEW**: `ORDER BY p.category_name, p.sub_category, ...` (location first)
- **Impact**: CRITICAL - causes different schools to be included/excluded

### 3. The 2000 SKU Limit Problem

Both views limit results to 2000 SKUs:
- **Line 2009** (shop view): `if len(base_forecasts) >= 2000: break`
- **Line 2144** (school view): `if len(base_forecasts) >= 2000: break`

**Total SKUs available**: 4,289
**SKUs loaded**: 2,000 (limit)
**SKUs missing**: 2,289

#### How the different ORDER BY causes discrepancy:

**SCHOOL VIEW** ordering (`school, product, SKU`):
- Loads SKUs alphabetically by school name
- Gets a mix of schools: Alfriston → Ardmore → Birkenhead → ... → Matamata
- Hits 2000 limit around "Matamata College"
- Schools alphabetically after Matamata are excluded

**SHOP VIEW** ordering (`location, school, product, SKU`):
- Loads SKUs alphabetically by location (shop) first
- "Avondale Shop" comes first alphabetically, gets ALL its SKUs
- "Cambridge Shop" comes next, gets ALL its SKUs
- etc.
- Hits 2000 limit somewhere in the middle of locations
- Later locations may be partially or completely excluded

This explains why:
- **Schools in SHOP but not SCHOOL**: Rutherford College, Te Atatu Intermediate, Western Springs College, etc. (all in "Avondale Shop" which loads early)
- **Schools in SCHOOL but not SHOP**: Birkenhead College, Ardmore School, etc. (in locations that load later or not at all)

## Actual Test Results

### Simulation Results

When simulating the exact Python filtering logic:

**SCHOOL view**: 25 schools with shortages
```
1. Alfriston College (80 shortages / 141 products)
2. Ardmore School (20 shortages / 58 products)
3. Birkenhead College (21 shortages / 91 products)
4. Cambridge College (100 shortages / 151 products)
5. Clayton Park (9 shortages / 22 products)
... (20 more schools)
25. Matamata College (13 shortages / 31 products)
```

**SHOP view**: 24 schools with shortages
```
1. Alfriston College @ Manukau Shop (80 shortages / 141 products)
2. Cambridge College @ Cambridge Shop (100 shortages / 151 products)
3. Clayton Park @ Manukau Shop (9 shortages / 22 products)
... (21 more schools)
24. Western Springs College @ Avondale Shop (7 shortages / 17 products)
```

### Schools appearing in SHOP but NOT in SCHOOL (8 schools):
1. **Matauri Bay School** (Kerikeri Shop) - 6 shortages
2. **McAuley High School** (Manukau Shop) - 27 shortages
3. **Oruaiti School** (Kerikeri Shop) - 5 shortages
4. **Papatoetoe East** (Manukau Shop) - 6 shortages
5. **Papatoetoe High** (Manukau Shop) - 26 shortages
6. **Rutherford College** (Avondale Shop) - 90 shortages
7. **Te Atatu Intermediate** (Avondale Shop) - 30 shortages
8. **Western Springs College** (Avondale Shop) - 7 shortages

### Schools appearing in SCHOOL but NOT in SHOP (9 schools):
1. **Ardmore School** - 20 shortages
2. **Birkenhead College** - 21 shortages
3. **Clevedon School** - 6 shortages
4. **Cosgrove School** - 1 shortage
5. **Hingaia Peninsula School** - 8 shortages
6. **Kauri Flats** - 6 shortages
7. **Kelvin Road** - 10 shortages
8. **Kingsgate School** - 25 shortages
9. **Matamata College** - 13 shortages

## Impact

This is a **critical data consistency issue** because:
1. Users see different schools depending on which view they use
2. Important shortages are missed (e.g., Rutherford College has 90 shortages but doesn't appear in school view!)
3. The 2000 SKU limit is arbitrary and creates unpredictable results
4. Different ORDER BY clauses make the views non-comparable

## Recommended Fixes

### Option 1: Make ORDER BY Consistent (Quick Fix)
Change the SCHOOL view ORDER BY to match SHOP view:

**File**: `/Users/sas/Repos/saspulse/dashboard/views.py`
**Line**: 2046

**Current**:
```python
sql += " ORDER BY p.sub_category, p.name, sf.entity_name, sf.forecast_date DESC"
```

**Change to**:
```python
sql += " ORDER BY p.category_name, p.sub_category, p.name, sf.entity_name, sf.forecast_date DESC"
```

**Pros**: Simple one-line change
**Cons**: Doesn't solve the 2000 SKU limit issue

### Option 2: Increase the 2000 SKU Limit (Medium Fix)
Increase the limit from 2000 to 5000 or higher to ensure all schools are included.

**Files**: `/Users/sas/Repos/saspulse/dashboard/views.py`
**Lines**: 2009, 2144

**Current**:
```python
if len(base_forecasts) >= 2000:  # Limit to 2000 unique entities
    break
```

**Change to**:
```python
if len(base_forecasts) >= 5000:  # Increased limit to include all schools
    break
```

**Pros**: Ensures all 4289 SKUs are loaded
**Cons**: May impact performance slightly

### Option 3: Remove the SKU Limit for School/Shop Views (Best Fix)
Since we're grouping by school anyway, we should load ALL SKUs and then apply limits at the school level, not the SKU level.

**Current logic**:
1. Load up to 2000 SKUs (arbitrary cutoff)
2. Group by school
3. Filter by stock gaps
4. Limit to 100 schools

**Better logic**:
1. Load ALL SKUs (no limit at SQL level)
2. Group by school
3. Filter by stock gaps
4. Limit to 100 schools (or whatever is appropriate)

**Change**:
```python
# Remove this condition
if len(base_forecasts) >= 2000:
    break
```

Or set it much higher:
```python
if len(base_forecasts) >= 10000:  # Safety limit only
    break
```

**Pros**:
- Guarantees consistency between views
- All schools are considered
- Limit is applied at the right level (schools, not SKUs)

**Cons**:
- Slightly more data to process
- But with 4289 SKUs, this is still very manageable

### Option 4: Make Wholesale Filter Consistent
Add the Wholesale filter to SHOP view to match SCHOOL view:

**File**: `/Users/sas/Repos/saspulse/dashboard/views.py`
**Line**: 1983

**Current**:
```python
else:
    # Show all shop products
    sql += " AND p.category_name LIKE '%Shop'"
```

**Change to**:
```python
else:
    # Show all shop products (excluding Wholesale)
    sql += " AND p.category_name LIKE '%Shop'"
    sql += " AND p.category_name NOT LIKE 'Wholesale%'"
```

## Recommended Solution

**Implement Options 1, 3, and 4 together**:
1. Make ORDER BY consistent (Option 1)
2. Remove or significantly increase the 2000 SKU limit (Option 3)
3. Add Wholesale filter to shop view (Option 4)

This will ensure:
- Both views use identical filtering logic
- Both views return identical schools
- The limit is applied at the school level, not SKU level
- No important data is arbitrarily excluded

## Additional Observations

1. The user reported 19 vs 23 schools, but simulation showed 25 vs 24. This suggests the production environment may have:
   - Different data (more/fewer products with shortages)
   - Cache affecting results
   - Different date range processing

2. The stock gap filter (`if stock_gap >= 0: continue`) is applied AFTER SQL query and SKU limit, so it's working correctly but on incomplete data.

3. The 2000 SKU limit was likely added for performance, but with only 4289 total SKUs, loading all of them should not cause performance issues.
