# Daily Pick List - Complete Code Reference

## 1. View Function Code

**File:** `/Users/sas/Repos/saspulse/dashboard/views.py` (Lines 5835-6043)

```python
@login_required
def store_daily_pick_list(request):
    """
    Generate daily pick list for store replenishment based on previous day's sales

    Features:
    - Shows products sold yesterday
    - Calculates pick quantity based on sales velocity and current stock
    - Prioritizes items by urgency (low stock, high sales)
    - Helps store managers prepare warehouse transfers for shelf replenishment
    """
    from datetime import date, timedelta
    from django.db.models import Sum, F, Q, Count
    from decimal import Decimal
    from cin7.models import SalesOrderLineItem, Stock, Branch

    # Get user's branch
    user = request.user
    is_admin = user.is_superuser or user.is_staff
    assigned_branch = getattr(user, 'assigned_branch', None)

    if not is_admin and not assigned_branch:
        return render(request, 'dashboard/store_daily_pick_list.html', {
            'error': 'You are not assigned to a branch. Please contact your administrator.',
            'pick_list': [],
        })

    # Get target date from request (default: yesterday)
    target_date_str = request.GET.get('date')
    if target_date_str:
        try:
            target_date = date.fromisoformat(target_date_str)
        except ValueError:
            target_date = date.today() - timedelta(days=1)
    else:
        target_date = date.today() - timedelta(days=1)

    # Get category filter (optional)
    category_filter = request.GET.get('category', '')

    # Get minimum quantity threshold (default: 1)
    try:
        min_quantity = int(request.GET.get('min_qty', 1))
    except ValueError:
        min_quantity = 1

    # Query yesterday's sales for the branch
    # Use invoice_date for completed sales
    sales_query = SalesOrderLineItem.objects.filter(
        sales_order__invoice_date__date=target_date,
        sales_order__is_void=False
    )

    # Filter by branch if not admin
    if not is_admin and assigned_branch:
        # Need to filter by branch - sales orders don't have direct branch relationship
        # We'll use the stock table to infer which products are in this branch
        branch_product_ids = Stock.objects.filter(
            branch=assigned_branch,
            stock_on_hand__gt=0
        ).values_list('cin7_product_id', flat=True)

        sales_query = sales_query.filter(cin7_product_id__in=branch_product_ids)

    # Filter by category if specified
    if category_filter:
        sales_query = sales_query.filter(product__category_name__icontains=category_filter)

    # Aggregate sales by product
    sales_data = sales_query.values(
        'cin7_product_id',
        'code',
        'name',
        product_category=F('product__category_name')
    ).annotate(
        quantity_sold=Sum('qty'),
        order_count=Count('cin7_sales_order_id', distinct=True)
    ).filter(
        quantity_sold__gte=min_quantity
    ).order_by('-quantity_sold')

    # Build pick list with stock information
    pick_list = []
    total_items = 0
    total_pick_quantity = 0
    categories = set()

    for sale in sales_data:
        product_id = sale['cin7_product_id']
        sku = sale['code']
        product_name = sale['name']
        category = sale['product_category'] or 'Uncategorized'
        qty_sold = float(sale['quantity_sold'])
        order_count = sale['order_count']

        # Get current stock for this product at the branch
        stock_query = Stock.objects.filter(cin7_product_id=product_id)

        if not is_admin and assigned_branch:
            stock_query = stock_query.filter(branch=assigned_branch)

        stock_record = stock_query.first()

        if stock_record:
            current_stock = float(stock_record.stock_on_hand or 0)
            incoming_stock = float(stock_record.incoming or 0)
            branch_name = stock_record.branch_name
        else:
            # Product not in stock table for this branch
            current_stock = 0
            incoming_stock = 0
            branch_name = assigned_branch.name if assigned_branch else 'Unknown'

        # Calculate pick quantity
        # Strategy: Maintain 2-3 days of stock based on yesterday's sales
        # Pick Quantity = (Yesterday's Sales * 2.5) - Current Stock
        daily_demand = qty_sold
        target_stock = daily_demand * 2.5  # 2.5 days buffer
        available_stock = current_stock + incoming_stock

        pick_qty = max(0, target_stock - available_stock)

        # Round up to nearest whole number
        pick_qty = int(pick_qty) if pick_qty > 0 else 0

        # Determine priority based on stock situation
        # Critical: Less than 1 day of stock
        # High: 1-2 days of stock
        # Medium: 2-3 days of stock
        # Low: More than 3 days of stock

        if daily_demand > 0:
            days_of_stock = current_stock / daily_demand
        else:
            days_of_stock = 999

        if days_of_stock < 1:
            priority = 'CRITICAL'
            priority_score = 1
        elif days_of_stock < 2:
            priority = 'HIGH'
            priority_score = 2
        elif days_of_stock < 3:
            priority = 'MEDIUM'
            priority_score = 3
        else:
            priority = 'LOW'
            priority_score = 4

        # Only include items that need picking OR have very low stock
        if pick_qty > 0 or days_of_stock < 1:
            pick_list.append({
                'sku': sku,
                'product_name': product_name,
                'category': category,
                'qty_sold': int(qty_sold),
                'order_count': order_count,
                'current_stock': int(current_stock),
                'incoming_stock': int(incoming_stock),
                'pick_qty': pick_qty,
                'target_stock': int(target_stock),
                'days_of_stock': round(days_of_stock, 1),
                'priority': priority,
                'priority_score': priority_score,
                'branch_name': branch_name,
            })

            total_items += 1
            total_pick_quantity += pick_qty
            categories.add(category)

    # Sort by priority (critical first), then by quantity sold (high to low)
    pick_list.sort(key=lambda x: (x['priority_score'], -x['qty_sold']))

    # Group by priority for display
    critical_items = [item for item in pick_list if item['priority'] == 'CRITICAL']
    high_items = [item for item in pick_list if item['priority'] == 'HIGH']
    medium_items = [item for item in pick_list if item['priority'] == 'MEDIUM']
    low_items = [item for item in pick_list if item['priority'] == 'LOW']

    # Get unique categories for filter dropdown
    all_categories = []
    if is_admin:
        from cin7.models import Product
        all_categories = Product.objects.values_list('category_name', flat=True).distinct().order_by('category_name')
    elif assigned_branch:
        branch_products = Stock.objects.filter(branch=assigned_branch).values_list('cin7_product_id', flat=True)
        from cin7.models import Product
        all_categories = Product.objects.filter(cin7_id__in=branch_products).values_list('category_name', flat=True).distinct().order_by('category_name')

    context = {
        'target_date': target_date,
        'pick_list': pick_list,
        'critical_items': critical_items,
        'high_items': high_items,
        'medium_items': medium_items,
        'low_items': low_items,
        'total_items': total_items,
        'total_pick_quantity': total_pick_quantity,
        'category_count': len(categories),
        'branch_name': assigned_branch.name if assigned_branch else 'All Branches',
        'is_admin': is_admin,
        'all_categories': all_categories,
        'selected_category': category_filter,
        'min_quantity': min_quantity,
        'today': date.today(),
    }

    return render(request, 'dashboard/store_daily_pick_list.html', context)
```

## 2. URL Configuration

**File:** `/Users/sas/Repos/saspulse/dashboard/urls.py` (Line 35)

```python
urlpatterns = [
    # ... existing patterns ...

    # Store Replenishment Request System (New - Batch Based)
    path('replenishment/store/submit/', views.submit_store_replenishment_request, name='submit_store_replenishment_request'),
    path('replenishment/store/requests/', views.store_replenishment_requests_list, name='store_replenishment_requests_list'),
    path('replenishment/store/requests/<str:request_number>/', views.store_replenishment_request_detail, name='store_replenishment_request_detail'),
    path('replenishment/store/daily-pick-list/', views.store_daily_pick_list, name='store_daily_pick_list'),  # NEW LINE

    # ... remaining patterns ...
]
```

## 3. Navigation Menu HTML

**File:** `/Users/sas/Repos/saspulse/templates/base.html` (Lines 197-200)

```html
<!-- Under Replenishment → Stores submenu -->
<ul class="nav collapse parent" data-bs-parent="#navbarVerticalCollapse" id="nv-replenishment-stores">
    <li class="collapsed-nav-item-title d-none">Stores</li>

    <li class="nav-item"><a class="nav-link" href="/dashboard/replenishment/store/">
        <div class="d-flex align-items-center"><span class="nav-link-text">Store Manager Review</span></div>
    </a></li>

    <li class="nav-item"><a class="nav-link" href="/dashboard/replenishment/store/requests/">
        <div class="d-flex align-items-center"><span class="nav-link-text">My Requests</span></div>
    </a></li>

    <!-- NEW MENU ITEM -->
    <li class="nav-item"><a class="nav-link" href="/dashboard/replenishment/store/daily-pick-list/">
        <div class="d-flex align-items-center"><span class="nav-link-text">Daily Pick List</span></div>
    </a></li>

</ul>
```

## 4. Template Structure Overview

**File:** `/Users/sas/Repos/saspulse/dashboard/templates/dashboard/store_daily_pick_list.html`

### Key Template Sections:

#### A. Header Section
```django
<div class="mb-4">
    <h2 class="mb-2">Daily Pick List</h2>
    <h5 class="text-body-tertiary fw-semibold">
        Warehouse replenishment based on {{ target_date|date:"l, F d, Y" }} sales
    </h5>
</div>
```

#### B. Filters Form
```django
<form method="GET" id="filterForm">
    <div class="row g-3">
        <div class="col-md-3">
            <label class="form-label">Sales Date</label>
            <input type="date" name="date" class="form-control"
                   value="{{ target_date|date:'Y-m-d' }}"
                   max="{{ today|date:'Y-m-d' }}">
        </div>

        <div class="col-md-3">
            <label class="form-label">Category Filter</label>
            <select name="category" class="form-select">
                <option value="">All Categories</option>
                {% for cat in all_categories %}
                    <option value="{{ cat }}"
                            {% if cat == selected_category %}selected{% endif %}>
                        {{ cat }}
                    </option>
                {% endfor %}
            </select>
        </div>

        <div class="col-md-3">
            <label class="form-label">Min. Qty Sold</label>
            <input type="number" name="min_qty" class="form-control"
                   value="{{ min_quantity }}" min="1">
        </div>

        <div class="col-md-3">
            <button type="submit" class="btn btn-primary">
                <i class="fas fa-sync-alt me-2"></i>Refresh List
            </button>
            <button type="button" class="btn btn-outline-secondary"
                    onclick="window.print()">
                <i class="fas fa-print me-2"></i>Print Pick List
            </button>
        </div>
    </div>
</form>
```

#### C. Summary Cards
```django
<div class="row mb-4">
    <div class="col-md-3">
        <div class="card border-primary">
            <div class="card-body text-center">
                <h6 class="text-muted mb-2">Total Items</h6>
                <h2 class="text-primary mb-0">{{ total_items }}</h2>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card border-success">
            <div class="card-body text-center">
                <h6 class="text-muted mb-2">Total Pick Quantity</h6>
                <h2 class="text-success mb-0">{{ total_pick_quantity }}</h2>
            </div>
        </div>
    </div>
    <!-- Similar cards for Categories and Critical Items -->
</div>
```

#### D. Priority Table (Critical Items Example)
```django
{% if critical_items %}
<div class="card mb-4 priority-critical">
    <div class="card-header bg-danger text-white">
        <h5 class="mb-0">
            <i class="fas fa-exclamation-triangle me-2"></i>
            CRITICAL Priority ({{ critical_items|length }} items)
            <small class="ms-3">Less than 1 day of stock remaining</small>
        </h5>
    </div>
    <div class="card-body p-0">
        <div class="table-responsive">
            <table class="table table-sm table-hover mb-0 pick-list-table">
                <thead>
                    <tr>
                        <th class="no-print"><input type="checkbox" class="form-check-input"></th>
                        <th>SKU</th>
                        <th>Product</th>
                        <th>Category</th>
                        <th class="text-center">Qty Sold</th>
                        <th class="text-center">Current Stock</th>
                        <th class="text-center">Days Left</th>
                        <th class="text-center">Pick Qty</th>
                        <th class="text-center">Target Stock</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in critical_items %}
                    <tr>
                        <td class="no-print">
                            <input type="checkbox" class="form-check-input">
                        </td>
                        <td><code>{{ item.sku }}</code></td>
                        <td><strong>{{ item.product_name }}</strong></td>
                        <td><small class="text-muted">{{ item.category }}</small></td>
                        <td class="text-center">
                            <span class="badge bg-primary">{{ item.qty_sold }}</span>
                        </td>
                        <td class="text-center">{{ item.current_stock }}</td>
                        <td class="text-center days-critical">{{ item.days_of_stock }}</td>
                        <td class="text-center">
                            <strong class="text-danger">{{ item.pick_qty }}</strong>
                        </td>
                        <td class="text-center text-muted">{{ item.target_stock }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endif %}
```

#### E. Custom CSS
```css
.priority-critical {
    background-color: #fee;
    border-left: 4px solid #dc3545;
}

.priority-high {
    background-color: #fff3cd;
    border-left: 4px solid #ffc107;
}

.priority-medium {
    background-color: #d1ecf1;
    border-left: 4px solid #17a2b8;
}

.priority-low {
    background-color: #d4edda;
    border-left: 4px solid #28a745;
}

.days-critical { color: #dc3545; font-weight: bold; }
.days-high { color: #ffc107; font-weight: bold; }
.days-medium { color: #17a2b8; }
.days-low { color: #28a745; }

@media print {
    .no-print { display: none; }
    .card { border: 1px solid #dee2e6 !important; }
}
```

#### F. JavaScript for Auto-Refresh
```javascript
$(document).ready(function() {
    // Auto-submit form when date or category changes
    $('#filterForm input[type="date"], #filterForm select[name="category"]').on('change', function() {
        $('#filterForm').submit();
    });
});

// Print event handlers
window.addEventListener('beforeprint', function() {
    document.querySelector('.print-signature').style.display = 'block';
});

window.addEventListener('afterprint', function() {
    document.querySelector('.print-signature').style.display = 'none';
});
```

## 5. Database Models Used

### SalesOrderLineItem (cin7.models)
```python
class SalesOrderLineItem(TimestampedModel):
    # Relations
    sales_order = models.ForeignKey(SalesOrder, ...)
    product = models.ForeignKey(Product, ...)

    # Product Identifiers
    cin7_product_id = models.IntegerField(...)
    code = models.CharField(...)  # SKU
    name = models.CharField(...)  # Product name

    # Quantities
    qty = models.DecimalField(...)  # Quantity sold

    # Fields used in query:
    # - sales_order__invoice_date (date filter)
    # - sales_order__is_void (exclude cancelled)
    # - cin7_product_id (product grouping)
    # - product__category_name (category filter)
```

### Stock (cin7.models)
```python
class Stock(TimestampedModel):
    # Relations
    product = models.ForeignKey(Product, ...)
    branch = models.ForeignKey(Branch, ...)

    # Identifiers
    cin7_product_id = models.IntegerField(...)
    branch_name = models.CharField(...)
    code = models.CharField(...)  # SKU

    # Stock Quantities
    stock_on_hand = models.DecimalField(...)  # Current stock
    incoming = models.DecimalField(...)       # Incoming PO

    # Fields used in query:
    # - branch (branch filter)
    # - cin7_product_id (join with sales)
    # - stock_on_hand (availability)
    # - incoming (future stock)
```

### CustomUser (users.models)
```python
class CustomUser(AbstractUser):
    # Branch Assignment (for shop managers)
    assigned_branch = models.ForeignKey(
        'cin7.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_managers',
        help_text='Assigned branch/shop for store managers'
    )

    # Fields used:
    # - assigned_branch (branch filtering)
    # - is_superuser (admin check)
    # - is_staff (admin check)
```

## 6. Testing Examples

### Test Case 1: Store Manager Access
```python
# Setup
user = CustomUser.objects.get(username='store_manager_1')
user.assigned_branch = Branch.objects.get(name='Avondale Shop')
user.save()

# Login and navigate
client.login(username='store_manager_1', password='password')
response = client.get('/dashboard/replenishment/store/daily-pick-list/')

# Assertions
assert response.status_code == 200
assert 'Avondale Shop' in response.content.decode()
assert len(response.context['pick_list']) > 0
```

### Test Case 2: Date Filtering
```python
# Test with specific date
from datetime import date
target_date = date(2026, 3, 15)
response = client.get(
    '/dashboard/replenishment/store/daily-pick-list/',
    {'date': target_date.isoformat()}
)

assert response.context['target_date'] == target_date
```

### Test Case 3: Category Filtering
```python
# Test category filter
response = client.get(
    '/dashboard/replenishment/store/daily-pick-list/',
    {'category': 'School Uniforms'}
)

# All items should be from selected category
for item in response.context['pick_list']:
    assert 'School Uniforms' in item['category']
```

## 7. Performance Benchmarks

### Expected Query Count:
```
1. Sales aggregation query: 1 query
2. Stock data per product: 1 query per unique product
3. Category list query: 1 query
Total: ~3-103 queries depending on number of products
```

### Optimization:
Could be reduced to 3 queries total by prefetching stock data:
```python
# Optimized version (future enhancement)
product_ids = [sale['cin7_product_id'] for sale in sales_data]
stock_map = {
    s.cin7_product_id: s
    for s in Stock.objects.filter(
        cin7_product_id__in=product_ids,
        branch=assigned_branch
    ).select_related('branch')
}

# Then use stock_map[product_id] instead of querying each time
```

## 8. URL Examples

```
# Default (yesterday's sales)
/dashboard/replenishment/store/daily-pick-list/

# Specific date
/dashboard/replenishment/store/daily-pick-list/?date=2026-03-15

# Category filter
/dashboard/replenishment/store/daily-pick-list/?category=School%20Uniforms

# Minimum quantity
/dashboard/replenishment/store/daily-pick-list/?min_qty=5

# Combined filters
/dashboard/replenishment/store/daily-pick-list/?date=2026-03-15&category=School%20Uniforms&min_qty=5
```

## 9. Context Variables Reference

| Variable | Type | Description |
|----------|------|-------------|
| `target_date` | date | Date for which sales are analyzed |
| `pick_list` | list[dict] | All items needing replenishment |
| `critical_items` | list[dict] | Items with < 1 day stock |
| `high_items` | list[dict] | Items with 1-2 days stock |
| `medium_items` | list[dict] | Items with 2-3 days stock |
| `low_items` | list[dict] | Items with > 3 days stock |
| `total_items` | int | Count of total items |
| `total_pick_quantity` | int | Sum of all pick quantities |
| `category_count` | int | Number of distinct categories |
| `branch_name` | str | Name of user's branch |
| `is_admin` | bool | Whether user is admin |
| `all_categories` | list[str] | Available categories for filter |
| `selected_category` | str | Currently selected category |
| `min_quantity` | int | Minimum quantity threshold |
| `today` | date | Today's date (for max date validation) |

## 10. Pick List Item Dictionary Structure

```python
{
    'sku': 'UNI-SH-12',                    # Product SKU code
    'product_name': 'School Shirt Size 12', # Full product name
    'category': 'School Uniforms',          # Product category
    'qty_sold': 25,                         # Units sold on target date
    'order_count': 8,                       # Number of orders
    'current_stock': 10,                    # Stock on hand now
    'incoming_stock': 0,                    # Stock on order
    'pick_qty': 38,                         # Quantity to pick
    'target_stock': 63,                     # Desired stock level
    'days_of_stock': 0.4,                   # Days until stockout
    'priority': 'CRITICAL',                 # Priority level
    'priority_score': 1,                    # Score for sorting (1-4)
    'branch_name': 'Avondale Shop',         # Branch name
}
```
