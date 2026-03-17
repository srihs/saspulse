# Daily Pick List Feature - Implementation Documentation

## Overview

The Daily Pick List feature helps small store managers prepare warehouse replenishment based on the previous day's sales. This feature automatically calculates which products need to be picked from the warehouse to restock shelves, prioritizing items based on urgency.

## Feature Location

**URL:** `/dashboard/replenishment/store/daily-pick-list/`

**Menu Location:** Replenishment → Stores → Daily Pick List

## Files Modified/Created

### 1. View Function
**File:** `/Users/sas/Repos/saspulse/dashboard/views.py`
- **Function:** `store_daily_pick_list()`
- **Line:** 5835-6043

### 2. URL Configuration
**File:** `/Users/sas/Repos/saspulse/dashboard/urls.py`
- **Line:** 35
- **Pattern:** `path('replenishment/store/daily-pick-list/', views.store_daily_pick_list, name='store_daily_pick_list')`

### 3. Navigation Menu
**File:** `/Users/sas/Repos/saspulse/templates/base.html`
- **Lines:** 197-200
- **Added:** Daily Pick List menu item under Replenishment → Stores

### 4. Template
**File:** `/Users/sas/Repos/saspulse/dashboard/templates/dashboard/store_daily_pick_list.html`
- **New file:** Complete HTML template with responsive design and print functionality

## Feature Functionality

### Core Logic

#### 1. Data Sources
The feature queries sales data from:
- **Model:** `SalesOrderLineItem` (from `cin7.models`)
- **Date Field:** `sales_order__invoice_date` (completed sales)
- **Stock Data:** `Stock` model for current inventory levels

#### 2. Pick Quantity Calculation

```python
# Strategy: Maintain 2.5 days of stock based on yesterday's sales
daily_demand = quantity_sold_yesterday
target_stock = daily_demand * 2.5  # 2.5 days buffer
available_stock = current_stock + incoming_stock
pick_qty = max(0, target_stock - available_stock)
```

**Example:**
- Product sold 10 units yesterday
- Target stock = 10 × 2.5 = 25 units
- Current stock = 8 units
- Incoming stock = 5 units
- Pick quantity = 25 - (8 + 5) = **12 units**

#### 3. Priority Determination

Items are prioritized based on "days of stock remaining":

```python
days_of_stock = current_stock / daily_demand
```

| Priority | Days of Stock | Meaning |
|----------|--------------|---------|
| **CRITICAL** (Red) | < 1 day | Stock will run out today |
| **HIGH** (Yellow) | 1-2 days | Stock will run out tomorrow |
| **MEDIUM** (Blue) | 2-3 days | Stock adequate for 2-3 days |
| **LOW** (Green) | > 3 days | Stock adequate, low urgency |

### User Permissions & Branch Filtering

#### Store Managers
- Can only see products from their assigned branch
- Branch assigned via `user.assigned_branch` field
- Pick list filtered to products in their branch's stock

#### Administrators
- Can see all branches
- No branch filtering applied
- View marked as "Admin View"

### Filter Options

1. **Sales Date**
   - Default: Yesterday
   - Max: Today
   - Use case: Generate pick lists for any past date

2. **Category Filter**
   - Dropdown populated with categories available in user's branch
   - Allows focusing on specific product categories

3. **Minimum Quantity Threshold**
   - Default: 1
   - Only shows items with at least this quantity sold
   - Helps filter out very low-volume items

## UI Components

### Summary Cards
- **Total Items:** Count of products needing replenishment
- **Total Pick Quantity:** Sum of all quantities to pick
- **Categories:** Number of distinct product categories
- **Critical Items:** Count of items with less than 1 day of stock

### Pick List Tables
Items grouped by priority level, each showing:
- **Checkbox:** For warehouse staff to mark as picked
- **SKU:** Product code
- **Product Name:** Full product description
- **Category:** Product category
- **Qty Sold:** Units sold on target date
- **Current Stock:** Stock on hand today
- **Days Left:** Calculated days of stock remaining
- **Pick Qty:** Quantity to pick from warehouse
- **Target Stock:** Desired stock level (2.5 days buffer)

### Print Functionality
- **Print Button:** Generates clean print layout
- **Hides:** Filters, buttons, and non-essential UI
- **Shows:** All pick list items with checkboxes
- **Includes:** Signature section for warehouse staff

## Business Rules

### 1. Stock Velocity-Based Replenishment
- Uses yesterday's sales as proxy for daily demand
- Assumes consistent daily demand patterns
- Buffer of 2.5 days prevents stockouts

### 2. Smart Filtering
- Only includes items that:
  - Were sold on the target date, AND
  - Need replenishment (pick_qty > 0) OR have critical stock (< 1 day)
- Prevents unnecessary picks for overstocked items

### 3. Real-Time Stock Integration
- Shows current stock levels (not historical)
- Includes incoming stock in calculations
- Helps avoid over-ordering

## Sample Calculation Examples

### Example 1: Fast-Moving Item (Critical)
```
Product: School Uniform Shirt - Size 10
Yesterday's Sales: 8 units
Current Stock: 3 units
Incoming Stock: 0 units

Calculation:
- Target Stock = 8 × 2.5 = 20 units
- Pick Quantity = 20 - (3 + 0) = 17 units
- Days of Stock = 3 / 8 = 0.375 days

Priority: CRITICAL (less than 1 day)
```

### Example 2: Medium-Moving Item (High)
```
Product: Exercise Book A4
Yesterday's Sales: 12 units
Current Stock: 15 units
Incoming Stock: 5 units

Calculation:
- Target Stock = 12 × 2.5 = 30 units
- Pick Quantity = 30 - (15 + 5) = 10 units
- Days of Stock = 15 / 12 = 1.25 days

Priority: HIGH (1-2 days)
```

### Example 3: Slow-Moving Item (Low)
```
Product: Specialty Item
Yesterday's Sales: 2 units
Current Stock: 8 units
Incoming Stock: 2 units

Calculation:
- Target Stock = 2 × 2.5 = 5 units
- Pick Quantity = 5 - (8 + 2) = 0 units (already overstocked)
- Days of Stock = 8 / 2 = 4 days

Priority: LOW (more than 3 days)
Note: Won't appear on pick list unless stock drops
```

## Performance Optimizations

### 1. Database Query Optimization
```python
# Single aggregated query instead of individual product queries
sales_data = sales_query.values(
    'cin7_product_id',
    'code',
    'name',
    product_category=F('product__category_name')
).annotate(
    quantity_sold=Sum('qty'),
    order_count=Count('cin7_sales_order_id', distinct=True)
)
```

### 2. Branch Filtering at Database Level
- Pre-filters products by branch before sales query
- Reduces memory usage for large datasets

### 3. Lazy Evaluation
- Categories dropdown only populated when needed
- Stock queries only for products with sales

## Use Cases

### Daily Morning Routine
1. Store manager arrives in morning
2. Opens Daily Pick List (defaults to yesterday)
3. Reviews critical/high priority items
4. Prints pick list for warehouse staff
5. Warehouse staff pick items and check off
6. Items restocked on shelves throughout the day

### After Busy Sales Day
1. Manager checks yesterday's pick list after a busy weekend
2. Sees multiple critical items
3. Filters to specific category (e.g., "School Uniforms")
4. Generates targeted pick list
5. Prioritizes urgent replenishment

### Historical Analysis
1. Manager selects date from last week
2. Reviews which items sold well
3. Compares to current stock levels
4. Identifies trends in product velocity

## Error Handling

### No Branch Assignment
```python
if not is_admin and not assigned_branch:
    return render(request, 'dashboard/store_daily_pick_list.html', {
        'error': 'You are not assigned to a branch. Please contact your administrator.',
        'pick_list': [],
    })
```

### Invalid Date Format
- Uses try/except to handle invalid date inputs
- Falls back to yesterday if date parsing fails

### No Sales Data
- Shows friendly message: "No items to pick for [date]"
- Explains possible reasons (no sales or sufficient stock)

## Future Enhancements

### Potential Additions:
1. **7-Day Average:** Use rolling average instead of single day
2. **Day-of-Week Patterns:** Monday vs. Saturday might have different demand
3. **Seasonal Adjustments:** Back-to-school periods need higher buffers
4. **Pack Size Rounding:** Round up to nearest case/pack for supplier ordering
5. **Warehouse Location Grouping:** Group by aisle/bin for efficient picking
6. **CSV Export:** Download pick list for warehouse management systems
7. **Historical Tracking:** Save pick lists for audit and accuracy analysis
8. **Pick Accuracy Metrics:** Track what was picked vs. what was needed

## Testing Recommendations

### Test Cases:
1. **Store manager with branch assignment**
   - Should see only their branch products
   - Should see branch name in banner

2. **Admin user**
   - Should see all branches
   - Should see "Admin View" indicator

3. **User without branch assignment**
   - Should see error message
   - Should not crash

4. **Date filtering**
   - Yesterday (default): Should work
   - Last week: Should work
   - Future date: Should not allow (max=today)

5. **Category filtering**
   - All categories: Shows all items
   - Specific category: Shows filtered items
   - Categories list matches branch's products

6. **No sales data**
   - Should show friendly message
   - Should not show empty tables

7. **Print functionality**
   - Should hide filters and buttons
   - Should show checkboxes
   - Should include signature section

## Integration Points

### Models Used:
- `cin7.models.SalesOrderLineItem` - Sales data
- `cin7.models.Stock` - Inventory levels
- `cin7.models.Branch` - Store/branch information
- `cin7.models.Product` - Product details
- `users.models.CustomUser` - User branch assignment

### Template Extends:
- `base.html` - Main site template
- Uses existing Bootstrap 5 styling
- Compatible with existing Phoenix theme

### URL Namespace:
- `dashboard:store_daily_pick_list` - Named URL pattern
- Consistent with existing dashboard URL naming

## Conclusion

The Daily Pick List feature provides a data-driven, automated way for store managers to maintain optimal shelf stock levels. By analyzing yesterday's sales and current stock, it generates prioritized picking instructions that help prevent stockouts while avoiding overstocking. The feature integrates seamlessly with existing inventory and sales data, requires no manual data entry, and provides both on-screen and print-friendly formats for warehouse operations.
