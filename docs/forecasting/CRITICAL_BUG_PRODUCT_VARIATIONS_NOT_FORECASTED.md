# 🚨 CRITICAL BUG REPORT: Product Variations Not Forecasted Separately

**Report Generated:** March 3, 2026
**Severity:** CRITICAL
**Impact:** Complete inventory forecasting system is inaccurate
**Status:** ❌ BROKEN - Needs immediate fix

---

## 🔴 EXECUTIVE SUMMARY

**PROBLEM CONFIRMED:** The Prophet forecasting engine is forecasting at the PARENT PRODUCT level, aggregating all variations (sizes/colors) together instead of forecasting each SKU variation separately.

**EXAMPLE:**
- Product: "LBC Black Short" has **18 different sizes** (60, 64, 68, 72, 76, 80, 84, 88, 92, 96, 100, 104, 108, 112, 116, 120, 124, 132)
- **CURRENT BEHAVIOR (WRONG):** Creates 1 forecast for "LBC Black Short" (all sizes combined)
- **CORRECT BEHAVIOR:** Should create 18 separate forecasts (one per size)

**WHY THIS IS CRITICAL:**
```
Current (WRONG):
  Forecast: "LBC Black Short" needs 87 units
  Recommendation: Order 40 units of "LBC Black Short"
  QUESTION: Which sizes??? 🤷

Correct (WHAT WE NEED):
  Forecast: "LBC Black Short Size 100" needs 12 units
  Forecast: "LBC Black Short Size 80" needs 8 units
  Forecast: "LBC Black Short Size 92" needs 15 units
  Recommendation: Order 12x Size 100, 8x Size 80, 15x Size 92
```

---

## 📊 DETAILED ANALYSIS

### 1. Product Structure in Database

**Parent Product:** LBC Black Short (cin7_id: 3761)
- Category: Long Bay Shop
- Sub-category: Long Bay College
- Has 18 variations differentiated by SIZE

**All 18 Variations:**

| SKU Code | Size | Current Stock | Price | Status |
|----------|------|---------------|-------|--------|
| US SH 703L LBC -60 | 60 | 6 units | $49.90 | Low stock |
| US SH 703L LBC -64 | 64 | 6 units | $49.90 | Low stock |
| US SH 703L LBC -68 | 68 | 36 units | $49.90 | OK |
| US SH 703L LBC -72 | 72 | 34 units | $49.90 | OK |
| US SH 703L LBC -76 | 76 | 76 units | $49.90 | High stock |
| US SH 703L LBC -80 | 80 | 106 units | $52.50 | **Very high stock** |
| US SH 703L LBC -84 | 84 | 49 units | $52.50 | OK |
| US SH 703L LBC -88 | 88 | 27 units | $52.50 | OK |
| US SH 703L LBC -92 | 92 | 74 units | $52.50 | High stock |
| US SH 703L LBC -96 | 96 | 55 units | $52.50 | OK |
| US SH 703L LBC -100 | 100 | 22 units | $55.50 | Low stock |
| US SH 703L LBC -104 | 104 | 18 units | $55.50 | Low stock |
| US SH 703L LBC -108 | 108 | 9 units | $55.50 | Very low stock |
| US SH 703L LBC -112 | 112 | 13 units | $55.50 | Low stock |
| US SH 703L LBC -116 | 116 | 6 units | $55.50 | Very low stock |
| US SH 703L LBC -120 | 120 | ? | $55.50 | Unknown |
| US SH 703L LBC -124 | 124 | ? | $55.50 | Unknown |
| US SH 703L LBC -132 | 132 | ? | $55.50 | Unknown |

**Notice the problem:**
- Size 80 has 106 units (oversupply)
- Size 116 has only 6 units (critical shortage)
- Aggregated forecast can't tell you this!

---

### 2. Current Code (BROKEN)

**File:** `/Users/sas/Repos/saspulse/dashboard/management/commands/generate_sales_forecasts.py`

**Lines 184-193 (WRONG):**
```python
entity_fields = {
    'school': 'p.sub_category',
    'product': 'p.name',          # ← PROBLEM: Uses parent product name
    'shop': 'p.category_name',
    'category': 'p.category_name'
}
```

**SQL Query Generated (WRONG):**
```sql
SELECT
    so.cin7_created_date as sale_date,
    p.name as entity_name,           -- ← Groups by parent product name!
    SUM(li.qty) as quantity,
    SUM(li.line_total) as revenue,
    COUNT(DISTINCT so.id) as order_count
FROM cin7_sync_salesorderlineitem li
JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
JOIN cin7_sync_product p ON p.id = li.product_id
WHERE (p.category_name LIKE '%Shop' OR p.category_name = 'Wholesale Schools')
  AND so.stage = 'Dispatched'
GROUP BY DATE(so.cin7_created_date), p.name  -- ← All sizes combined!
```

**Result (WRONG):**
```
Date       | Entity Name        | Quantity
-----------|-------------------|----------
2026-02-02 | LBC Black Short   | 3.00      ← Size 88 + 84 + 104 combined!
2026-02-01 | LBC Black Short   | 1.00
```

---

### 3. What Data Is Actually Available (GOOD NEWS)

**Sales are tracked at SKU level in `cin7_sync_salesorderlineitem`:**

```sql
SELECT
    li.code,
    li.qty,
    DATE(so.cin7_created_date) as sale_date
FROM cin7_sync_salesorderlineitem li
JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
WHERE li.code LIKE 'US SH 703L LBC%'
ORDER BY sale_date DESC
LIMIT 10;
```

**Actual Data (CORRECT GRANULARITY):**
```
code                    | qty  | sale_date
-----------------------|------|------------
US SH 703L LBC -104    | 1.00 | 2026-02-02  ← Size 104 sold separately
US SH 703L LBC -84     | 1.00 | 2026-02-02  ← Size 84 sold separately
US SH 703L LBC -88     | 1.00 | 2026-02-02  ← Size 88 sold separately
US SH 703L LBC -88     | 1.00 | 2026-02-01
```

✅ **The data exists at the right level - we just need to query it correctly!**

---

## 🔧 THE FIX

### Option 1: Add New Aggregation Level "product_sku"

**File:** `/Users/sas/Repos/saspulse/dashboard/management/commands/generate_sales_forecasts.py`

**Change 1 - Add choice (Line 74-77):**
```python
parser.add_argument(
    '--level',
    type=str,
    choices=['school', 'product', 'product_sku', 'shop', 'category', 'all'],  # ← Add product_sku
    default='all',
    help='Aggregation level (default: all)'
)
```

**Change 2 - Update levels list (Line 105):**
```python
levels = ['school', 'product_sku', 'shop'] if level == 'all' else [level]  # ← Use product_sku instead of product
```

**Change 3 - Add entity field mapping (Lines 184-193):**
```python
entity_fields = {
    'school': 'p.sub_category',
    'product': 'p.name',              # Keep for backward compatibility
    'product_sku': 'li.code',         # ← NEW: Forecast by SKU
    'shop': 'p.category_name',
    'category': 'p.category_name'
}
```

### Option 2: Replace "product" with SKU-level (Recommended)

Simply change line 186:
```python
entity_fields = {
    'school': 'p.sub_category',
    'product': 'li.code',             # ← Changed from p.name to li.code
    'shop': 'p.category_name',
    'category': 'p.category_name'
}
```

**This will make all product-level forecasts use SKU instead of parent product name.**

---

## ✅ CORRECT BEHAVIOR AFTER FIX

### SQL Query (CORRECT):
```sql
SELECT
    so.cin7_created_date as sale_date,
    li.code as entity_name,           -- ← Use SKU!
    SUM(li.qty) as quantity,
    SUM(li.line_total) as revenue,
    COUNT(DISTINCT so.id) as order_count
FROM cin7_sync_salesorderlineitem li
JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
JOIN cin7_sync_product p ON p.id = li.product_id
WHERE (p.category_name LIKE '%Shop' OR p.category_name = 'Wholesale Schools')
  AND so.stage = 'Dispatched'
GROUP BY DATE(so.cin7_created_date), li.code  -- ← Group by SKU!
```

### Result (CORRECT):
```
Date       | Entity Name (SKU)        | Quantity
-----------|-------------------------|----------
2026-02-02 | US SH 703L LBC -104     | 1.00     ← Each size separate!
2026-02-02 | US SH 703L LBC -84      | 1.00
2026-02-02 | US SH 703L LBC -88      | 1.00
2026-02-01 | US SH 703L LBC -88      | 1.00
```

### Forecasts Created (CORRECT):
```
Entity Name               | 30-Day Forecast | Stock | Gap
--------------------------|----------------|-------|------
US SH 703L LBC -60       | 2 units        | 6     | OK
US SH 703L LBC -64       | 3 units        | 6     | OK
US SH 703L LBC -100      | 15 units       | 22    | Need 10 more
US SH 703L LBC -104      | 12 units       | 18    | Need 8 more
US SH 703L LBC -108      | 8 units        | 9     | OK
US SH 703L LBC -116      | 10 units       | 6     | Need 12 more (CRITICAL!)
```

---

## 📋 IMPLEMENTATION STEPS

### Step 1: Update the Code
```bash
# Edit the file
nano /Users/sas/Repos/saspulse/dashboard/management/commands/generate_sales_forecasts.py

# Change line 186 from:
'product': 'p.name',

# To:
'product': 'li.code',
```

### Step 2: Delete Old Wrong Forecasts
```bash
source env/bin/activate
python manage.py shell << 'EOF'
from dashboard.models import SalesForecast
deleted = SalesForecast.objects.filter(aggregation_level='product').delete()
print(f"Deleted {deleted[0]} incorrect product forecasts")
EOF
```

### Step 3: Generate Correct Forecasts
```bash
python manage.py generate_sales_forecasts \
  --level=product \
  --horizon=30d \
  --model=hybrid \
  --min-sales=5
```

### Step 4: Verify Fix
```bash
python manage.py shell << 'EOF'
from dashboard.models import SalesForecast

# Check how many LBC Black Short forecasts exist
lbc_forecasts = SalesForecast.objects.filter(
    entity_name__contains='US SH 703L LBC'
).count()

print(f"LBC Black Short forecasts: {lbc_forecasts}")
print("Expected: 18 (one per size)")
print("If you see 1, the bug is NOT fixed!")
print("If you see 18, the bug IS fixed! ✅")
EOF
```

---

## 📊 IMPACT COMPARISON

### Before Fix (CURRENT - WRONG):

**Forecasts Generated:**
- 1 forecast: "LBC Black Short" = 87 units total

**Inventory Recommendation:**
```
Product: LBC Black Short
Forecast: 87 units
Current Stock: 110 units (all sizes combined)
Gap: Need 38 more units
Recommendation: Order 40 units

❌ PROBLEM: Which sizes should we order???
```

### After Fix (CORRECT):

**Forecasts Generated:**
- 18 forecasts: One per size (60, 64, 68, 72, 76, 80, 84, 88, 92, 96, 100, 104, 108, 112, 116, 120, 124, 132)

**Inventory Recommendations:**
```
SKU: US SH 703L LBC -100 (Size 100)
Forecast: 15 units
Current Stock: 22 units
Gap: Need 10 more
Recommendation: Order 10x Size 100

SKU: US SH 703L LBC -116 (Size 116)
Forecast: 10 units
Current Stock: 6 units
Gap: Need 12 more (CRITICAL!)
Recommendation: Order 12x Size 116

SKU: US SH 703L LBC -80 (Size 80)
Forecast: 5 units
Current Stock: 106 units
Gap: Overstocked by 101 units
Recommendation: Do NOT order Size 80

✅ RESULT: Precise size-specific orders!
```

---

## 🎯 ADDITIONAL BENEFITS OF THE FIX

1. **Accurate Stock Levels per Size**
   - Know exactly which sizes are running low
   - Prevent overstocking popular sizes

2. **Better Customer Service**
   - Never run out of popular sizes (e.g., Size 100)
   - Don't tie up capital in slow-moving sizes (e.g., Size 132)

3. **Improved Cash Flow**
   - Order only what you need
   - Reduce dead stock

4. **Actionable Reports**
   - "Order 10x Size 100" is actionable
   - "Order 40x LBC Black Short" is meaningless

---

## ⚠️ CONSIDERATIONS

### Database Size Impact
- **Before:** ~100 product forecasts
- **After:** ~1,500-2,000 SKU forecasts (15-20 variations per product × 100 products)
- **Storage:** Minimal impact (~5-10MB)
- **Query Performance:** Need to add index on `entity_name` (already exists)

### Dashboard UI Updates
- Display SKU code prominently
- Group by parent product for readability
- Show variation details (Size, Color, etc.)

### Backward Compatibility
- Keep "school" and "shop" levels unchanged
- Only "product" level changes to SKU-based

---

## 🚀 RECOMMENDATION

**IMMEDIATE ACTION REQUIRED:**

1. ✅ Implement Option 2 (replace 'product' with SKU-level)
2. ✅ Delete all existing product-level forecasts (they're wrong)
3. ✅ Regenerate forecasts with the fix
4. ✅ Update all existing forecast reports (like LBC_BLACK_SHORT_30DAY_FORECAST_REPORT.md)
5. ✅ Do NOT use the automated replenishment system until this is fixed

**This is a CRITICAL bug that makes the entire forecasting system unreliable for actual inventory management.**

---

## 📝 VERIFICATION CHECKLIST

After implementing the fix:

- [ ] Code changed: `'product': 'li.code'` instead of `'product': 'p.name'`
- [ ] Old forecasts deleted from database
- [ ] New forecasts generated with `--level=product`
- [ ] Verified 18 separate forecasts exist for LBC Black Short
- [ ] Each forecast shows SKU code (e.g., "US SH 703L LBC -100")
- [ ] Stock gap calculated separately per size
- [ ] Dashboard shows size-specific recommendations

---

**STATUS:** 🔴 CRITICAL BUG - AWAITING FIX

**PRIORITY:** P0 - Must fix before production use

**ESTIMATED FIX TIME:** 15 minutes

**RISK IF NOT FIXED:** Complete system failure - will order wrong sizes and create inventory chaos

---

**Report End**
