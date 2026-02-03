# Cin7 Integration

Django app for integrating with Cin7 API to sync inventory, orders, and customer data.

## Features

- **Cin7 API Client** with rate limiting (3/sec, 60/min, 5000/day)
- **Django Models** for all Cin7 entities
- **Management Commands** for data synchronization
- **Admin Interface** for viewing and managing synced data
- **Automatic retry logic** with exponential backoff

## Setup

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
# Cin7 API Configuration
CIN7_API_URL=https://api.cin7.com/api/v1
CIN7_USERNAME=your_username
CIN7_API_KEY=your_api_key
```

### 2. Run Migrations

```bash
python3 manage.py migrate cin7
```

### 3. Test the Connection

```bash
python3 cin7/test_client.py
```

Or in Django shell:

```python
from cin7.test_client import test_cin7_client
test_cin7_client()
```

## Usage

### Sync Data from Cin7

**Sync all entities:**
```bash
python3 manage.py sync_cin7 --entity all
```

**Sync specific entity:**
```bash
python3 manage.py sync_cin7 --entity branches
python3 manage.py sync_cin7 --entity products --limit 100
python3 manage.py sync_cin7 --entity contacts --full-sync
```

**Available entities:**
- `branches` - Warehouses/locations
- `products` - Products/inventory items
- `contacts` - Customers and suppliers
- `stock` - Stock levels per branch (coming soon)
- `sales_orders` - Sales orders (coming soon)
- `purchase_orders` - Purchase orders (coming soon)

### Using the API Client Directly

```python
from cin7.client import Cin7Client

# Initialize client
client = Cin7Client()

# Fetch products with filters
products = client.get_products(
    where="brand='Nike'",
    page=1,
    rows=50
)

# Get single product
product = client.get_product(product_id=123)

# Fetch branches
branches = client.get_branches()

# Fetch stock levels
stock = client.get_stock(
    where="productCode='ABC123'",
    page=1
)

# Close client when done
client.close()
```

## Models

### Product
- Cin7 product data including SKU, name, pricing, stock levels
- Custom managers: `get_active()`, `get_low_stock()`, `get_by_brand()`
- Properties: `is_low_stock`, `profit_margin`

### Branch
- Warehouse/location data
- Custom manager: `get_active()`

### Contact
- Customer and supplier data
- Custom managers: `get_customers()`, `get_suppliers()`

### SalesOrder
- Sales order data with customer reference
- Custom managers: `get_pending()`, `get_completed()`, `get_by_date_range()`

### PurchaseOrder
- Purchase order data with supplier reference
- Custom managers: `get_pending()`, `get_received()`

### Stock
- Stock levels per product per branch
- Custom managers: `get_low_stock()`, `get_by_branch()`

### ProductCategory
- Product categorization with hierarchical support
- Custom manager: `get_active()`

## Rate Limiting

The Cin7 API client automatically handles rate limiting:

- **3 requests per second** - Enforced with sliding window
- **60 requests per minute** - Enforced with sliding window
- **5000 requests per day** - Tracked via Django cache

The client will automatically sleep if rate limits would be exceeded.

## Error Handling

The client includes retry logic with exponential backoff for:

- **429 (Rate Limit)** - Retries with 10s, 20s, 40s delays
- **5xx (Server Errors)** - Retries with 5s, 10s, 20s delays
- **Timeouts** - Retries with exponential backoff

Custom exceptions:

- `Cin7APIError` - Base exception for API errors
- `Cin7RateLimitError` - Daily rate limit exceeded
- `Cin7AuthenticationError` - Invalid credentials

## Admin Interface

All models are registered in Django admin at `/admin/`:

- Filter by status, dates, categories
- Search by name, code, ID
- View sync timestamps
- Organized fieldsets for easy data entry

## Next Steps

1. **Set up Celery** for background sync tasks
2. **Implement webhooks** for real-time updates
3. **Add data validation** before saving to database
4. **Create REST API endpoints** using Django REST Framework
5. **Build dashboard frontend** for visualizing data

## File Structure

```
cin7/
├── __init__.py
├── admin.py              # Django admin configuration
├── apps.py
├── client.py             # Cin7 API client
├── models.py             # Django models
├── test_client.py        # Test script
├── README.md             # This file
├── management/
│   └── commands/
│       └── sync_cin7.py  # Data sync command
└── migrations/
    └── 0001_initial.py   # Database migrations
```

## Documentation

- [Cin7 API Documentation](https://api.cin7.com/api)
- [Backend Agent Specs](../docs/agents/backend-agent.md)
- [Project Roadmap](../docs/agents/PROJECT_ROADMAP.md)
