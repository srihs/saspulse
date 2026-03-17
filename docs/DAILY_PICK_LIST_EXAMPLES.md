# Daily Pick List - Calculation Examples

## Visual Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    DAILY PICK LIST LOGIC                     │
└─────────────────────────────────────────────────────────────┘

Step 1: GET YESTERDAY'S SALES DATA
┌──────────────────────────────────────┐
│ SalesOrderLineItem                    │
│ invoice_date = yesterday              │
│ branch = user's branch                │
│ is_void = False                       │
└──────────────────────────────────────┘
           ↓
        GROUP BY product
           ↓
┌──────────────────────────────────────┐
│ Product A: 10 units sold              │
│ Product B: 5 units sold               │
│ Product C: 20 units sold              │
└──────────────────────────────────────┘

Step 2: GET CURRENT STOCK LEVELS
┌──────────────────────────────────────┐
│ Stock table                           │
│ product_id = sold products            │
│ branch = user's branch                │
└──────────────────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│ Product A: 3 in stock, 0 incoming     │
│ Product B: 8 in stock, 2 incoming     │
│ Product C: 2 in stock, 5 incoming     │
└──────────────────────────────────────┘

Step 3: CALCULATE PICK QUANTITIES
┌──────────────────────────────────────┐
│ For each product:                     │
│                                       │
│ daily_demand = qty_sold               │
│ target_stock = daily_demand × 2.5     │
│ available = current + incoming        │
│ pick_qty = target - available         │
│ days_left = current / daily_demand    │
└──────────────────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│ PRODUCT A                             │
│ ├─ Sold: 10 units                     │
│ ├─ Target: 10 × 2.5 = 25              │
│ ├─ Available: 3 + 0 = 3               │
│ ├─ Pick: 25 - 3 = 22 units            │
│ ├─ Days left: 3 ÷ 10 = 0.3 days       │
│ └─ Priority: CRITICAL                 │
│                                       │
│ PRODUCT B                             │
│ ├─ Sold: 5 units                      │
│ ├─ Target: 5 × 2.5 = 12.5 ≈ 13        │
│ ├─ Available: 8 + 2 = 10              │
│ ├─ Pick: 13 - 10 = 3 units            │
│ ├─ Days left: 8 ÷ 5 = 1.6 days        │
│ └─ Priority: HIGH                     │
│                                       │
│ PRODUCT C                             │
│ ├─ Sold: 20 units                     │
│ ├─ Target: 20 × 2.5 = 50              │
│ ├─ Available: 2 + 5 = 7               │
│ ├─ Pick: 50 - 7 = 43 units            │
│ ├─ Days left: 2 ÷ 20 = 0.1 days       │
│ └─ Priority: CRITICAL                 │
└──────────────────────────────────────┘

Step 4: PRIORITIZE & GROUP
┌──────────────────────────────────────┐
│ CRITICAL (< 1 day):                   │
│   - Product A: Pick 22                │
│   - Product C: Pick 43                │
│                                       │
│ HIGH (1-2 days):                      │
│   - Product B: Pick 3                 │
│                                       │
│ MEDIUM (2-3 days):                    │
│   - (none)                            │
│                                       │
│ LOW (> 3 days):                       │
│   - (none)                            │
└──────────────────────────────────────┘
```

## Real-World Scenarios

### Scenario 1: Back-to-School Season (High Volume)

**Product:** School Uniform Shirt - Size 12

| Metric | Value | Calculation |
|--------|-------|-------------|
| Yesterday's Sales | 25 units | From sales data |
| Current Stock | 10 units | From stock table |
| Incoming Stock | 15 units | PO in transit |
| Target Stock | 63 units | 25 × 2.5 |
| Available Stock | 25 units | 10 + 15 |
| **Pick Quantity** | **38 units** | 63 - 25 |
| Days of Stock | 0.4 days | 10 ÷ 25 |
| **Priority** | **CRITICAL** | < 1 day |

**Interpretation:** This is a fast-moving item during peak season. Despite incoming stock, we still need to pick 38 units immediately to maintain buffer.

---

### Scenario 2: Regular Item (Steady Sales)

**Product:** Exercise Book A4 48 Page

| Metric | Value | Calculation |
|--------|-------|-------------|
| Yesterday's Sales | 8 units | From sales data |
| Current Stock | 12 units | From stock table |
| Incoming Stock | 0 units | No PO |
| Target Stock | 20 units | 8 × 2.5 |
| Available Stock | 12 units | 12 + 0 |
| **Pick Quantity** | **8 units** | 20 - 12 |
| Days of Stock | 1.5 days | 12 ÷ 8 |
| **Priority** | **HIGH** | 1-2 days |

**Interpretation:** Steady seller. Current stock will last 1.5 days. Pick 8 units today to maintain buffer.

---

### Scenario 3: Slow-Moving Item (Low Volume)

**Product:** Specialty Calculator

| Metric | Value | Calculation |
|--------|-------|-------------|
| Yesterday's Sales | 2 units | From sales data |
| Current Stock | 8 units | From stock table |
| Incoming Stock | 0 units | No PO |
| Target Stock | 5 units | 2 × 2.5 |
| Available Stock | 8 units | 8 + 0 |
| **Pick Quantity** | **0 units** | Already overstocked |
| Days of Stock | 4.0 days | 8 ÷ 2 |
| **Priority** | **LOW** | > 3 days |

**Interpretation:** Item won't appear on pick list - already has 4 days of stock. No action needed.

---

### Scenario 4: Stockout Risk (Very Low Stock)

**Product:** PE Shorts - Size 10

| Metric | Value | Calculation |
|--------|-------|-------------|
| Yesterday's Sales | 15 units | From sales data |
| Current Stock | 2 units | From stock table |
| Incoming Stock | 0 units | No PO |
| Target Stock | 38 units | 15 × 2.5 |
| Available Stock | 2 units | 2 + 0 |
| **Pick Quantity** | **36 units** | 38 - 2 |
| Days of Stock | 0.13 days | 2 ÷ 15 |
| **Priority** | **CRITICAL** | < 1 day (3 hours!) |

**Interpretation:** Urgent! Only 2 units left with daily demand of 15. Will stock out in next few hours. Pick 36 units immediately.

---

### Scenario 5: Incoming Stock Covers Demand

**Product:** Blue Pen - Single

| Metric | Value | Calculation |
|--------|-------|-------------|
| Yesterday's Sales | 12 units | From sales data |
| Current Stock | 5 units | From stock table |
| Incoming Stock | 40 units | PO arriving today |
| Target Stock | 30 units | 12 × 2.5 |
| Available Stock | 45 units | 5 + 40 |
| **Pick Quantity** | **0 units** | Already covered |
| Days of Stock | 0.42 days | 5 ÷ 12 (without incoming) |
| **Priority** | **N/A** | Won't show on list |

**Interpretation:** Even though current stock is low (0.42 days), incoming PO of 40 units covers demand. No pick needed. Item won't appear on pick list.

---

## Edge Cases

### Edge Case 1: Zero Sales Yesterday

**Product:** Seasonal Item (off-season)

| Metric | Value | Note |
|--------|-------|------|
| Yesterday's Sales | 0 units | No sales |
| Current Stock | 20 units | Left from last season |

**Result:** Item doesn't appear on pick list. Logic only includes products that were sold on target date.

---

### Edge Case 2: New Product Launch

**Product:** New Style Uniform

| Metric | Value | Note |
|--------|-------|------|
| Yesterday's Sales | 50 units | First day launch |
| Current Stock | 5 units | Nearly sold out |
| Incoming Stock | 100 units | Supplier order |

| Calculation | Value |
|------------|-------|
| Target Stock | 125 units (50 × 2.5) |
| Available | 105 units (5 + 100) |
| **Pick Quantity** | **20 units** |
| **Priority** | **CRITICAL** (0.1 days current) |

**Result:** Even with large incoming order, we still need 20 more units. First-day sales of 50 sets high baseline.

---

### Edge Case 3: Weekend vs Weekday

**Product:** Hot Lunch Voucher

**Monday (after weekend):**
| Day | Sales |
|-----|-------|
| Friday | 100 units |
| Saturday | 5 units (school closed) |
| Sunday | 0 units (school closed) |
| **Monday Pick List** | Based on Sunday (0 units) |

**Problem:** Monday pick list sees 0 sales (Sunday) and recommends 0 pick quantity, but Monday demand will be ~100 units!

**Recommendation for Enhancement:** Use 7-day rolling average instead of single day for more accurate demand prediction.

---

## Priority Decision Tree

```
Is product in stock?
    │
    ├─ NO → Don't show on pick list
    │
    └─ YES → Calculate days_of_stock
            │
            ├─ < 1 day? → CRITICAL (Red)
            │                │
            │                └─ Pick immediately!
            │
            ├─ 1-2 days? → HIGH (Yellow)
            │                │
            │                └─ Pick today
            │
            ├─ 2-3 days? → MEDIUM (Blue)
            │                │
            │                └─ Pick soon
            │
            └─ > 3 days? → LOW (Green)
                             │
                             └─ Pick if needed
                                  │
                                  └─ If pick_qty = 0,
                                     don't show on list
```

## Summary Statistics Example

For a typical small store on a Monday morning:

```
┌────────────────────────────────────────────┐
│         DAILY PICK LIST SUMMARY            │
├────────────────────────────────────────────┤
│ Date: Sunday, March 15, 2026               │
│ Branch: Avondale Shop                      │
│                                            │
│ Total Items:           47                  │
│ Total Pick Quantity:   234 units           │
│ Categories:            8                   │
│                                            │
│ ┌─ CRITICAL Items:    12 (pick now!)       │
│ ├─ HIGH Items:        18 (pick today)      │
│ ├─ MEDIUM Items:      11 (pick soon)       │
│ └─ LOW Items:         6  (optional)        │
└────────────────────────────────────────────┘
```

## Print Layout Example

```
═══════════════════════════════════════════════════════════════
                    DAILY PICK LIST
═══════════════════════════════════════════════════════════════
Date: March 15, 2026
Branch: Avondale Shop
Generated: March 16, 2026 08:30 AM

───────────────────────────────────────────────────────────────
CRITICAL PRIORITY (12 items) - Less than 1 day of stock
───────────────────────────────────────────────────────────────

☐  SKU: UNI-SH-12    Product: School Shirt Size 12
   Sold: 25  |  Current: 10  |  Pick: 38 units

☐  SKU: UNI-SH-10    Product: School Shirt Size 10
   Sold: 20  |  Current: 5   |  Pick: 45 units

☐  SKU: EXB-A4-48    Product: Exercise Book A4
   Sold: 30  |  Current: 8   |  Pick: 67 units

[... 9 more items ...]

───────────────────────────────────────────────────────────────
HIGH PRIORITY (18 items) - 1-2 days of stock
───────────────────────────────────────────────────────────────

☐  SKU: PEN-BLUE     Product: Blue Pen
   Sold: 12  |  Current: 15  |  Pick: 15 units

[... 17 more items ...]

───────────────────────────────────────────────────────────────
COMPLETION
───────────────────────────────────────────────────────────────

Total Items: 47  |  Total Quantity: 234 units

Picked By: _____________________  Date: ___________

Verified By: ___________________  Date: ___________

═══════════════════════════════════════════════════════════════
```

## Performance Considerations

### Query Optimization

**Bad (N+1 queries):**
```python
for product in products:
    sales = SalesOrderLineItem.objects.filter(product=product).aggregate(Sum('qty'))
    stock = Stock.objects.get(product=product)
    # ... calculate
```
**Result:** 1 + (N × 2) queries = 201 queries for 100 products

**Good (Aggregated):**
```python
sales = SalesOrderLineItem.objects.values('product').annotate(qty_sold=Sum('qty'))
stock_map = {s.product_id: s for s in Stock.objects.filter(product__in=products)}
# ... calculate
```
**Result:** 2 queries total

### Memory Usage

For 1000 products in pick list:
- Each item: ~500 bytes (dict with 10 fields)
- Total: ~500 KB in memory
- Plus overhead: ~1 MB total

**Conclusion:** Very efficient, even for large stores.
