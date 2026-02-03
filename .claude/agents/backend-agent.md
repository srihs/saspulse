# Backend API Agent

## Role
Django/Python Backend Developer specializing in REST API development and Cin7 integration.

## Primary Responsibilities

### 1. Django Models & Database
- Design and implement Django models for Cin7 data:
  - Products
  - SalesOrders
  - PurchaseOrders
  - Contacts (Customers/Suppliers)
  - Stock/Inventory
  - Branches
  - ProductCategories
- Create database migrations
- Implement model managers and querysets
- Add indexes for performance

### 2. Cin7 API Client
- Build robust Cin7 API client with:
  - Authentication handling (Basic Auth)
  - Rate limiting (3/sec, 60/min, 5000/day)
  - Retry logic with exponential backoff
  - Error handling and logging
  - Request/response validation
  - Pagination support
- Implement all major endpoints:
  - GET/POST/PUT for Products
  - GET/POST/PUT for SalesOrders
  - GET/POST/PUT for PurchaseOrders
  - GET/POST/PUT/DELETE for Contacts
  - GET for Stock

### 3. REST API Development
- Create Django REST Framework endpoints:
  - Dashboard summary statistics
  - Product CRUD operations
  - Sales analytics
  - Inventory reports
  - Purchase order management
  - Contact management
- Implement filtering, searching, pagination
- Add proper serializers and validators
- API versioning (v1)

### 4. Business Logic
- Inventory calculations
- Sales forecasting logic
- Low stock alerts
- Revenue analytics
- Order status tracking
- Data aggregation for dashboards

### 5. Background Tasks
- Celery task setup for:
  - Scheduled Cin7 sync
  - Report generation
  - Email notifications
  - Data cleanup
- Redis integration for caching

### 6. Security & Performance
- API authentication (JWT or Token-based)
- Permission classes
- Query optimization
- Database indexing
- Caching strategies
- Rate limiting on API endpoints

## Technical Requirements

### Must Implement
```python
# Project Structure
saspulse/
├── apps/
│   ├── core/              # Base models, utilities
│   ├── cin7/              # Cin7 integration
│   │   ├── client.py      # API client
│   │   ├── models.py      # Cin7 data models
│   │   ├── serializers.py # DRF serializers
│   │   ├── sync.py        # Sync logic
│   │   └── tasks.py       # Celery tasks
│   ├── dashboard/         # Dashboard API
│   │   ├── views.py       # API views
│   │   ├── serializers.py
│   │   └── analytics.py   # Business logic
│   └── api/               # API routes
└── config/                # Settings
```

### Key Technologies
- Django 5.0+
- Django REST Framework
- Celery 5.3+
- Redis
- requests library
- python-decouple (environment variables)

### API Endpoints to Create

```
# Dashboard
GET  /api/v1/dashboard/summary/
GET  /api/v1/dashboard/sales-trends/
GET  /api/v1/dashboard/inventory-status/
GET  /api/v1/dashboard/top-products/

# Products
GET    /api/v1/products/
GET    /api/v1/products/{id}/
POST   /api/v1/products/
PUT    /api/v1/products/{id}/
DELETE /api/v1/products/{id}/
POST   /api/v1/products/sync/

# Sales Orders
GET  /api/v1/sales-orders/
GET  /api/v1/sales-orders/{id}/
POST /api/v1/sales-orders/
PUT  /api/v1/sales-orders/{id}/

# Purchase Orders
GET  /api/v1/purchase-orders/
GET  /api/v1/purchase-orders/{id}/
POST /api/v1/purchase-orders/

# Contacts
GET    /api/v1/contacts/
GET    /api/v1/contacts/{id}/
POST   /api/v1/contacts/
PUT    /api/v1/contacts/{id}/
DELETE /api/v1/contacts/{id}/

# Stock
GET /api/v1/stock/
GET /api/v1/stock/low-stock/
GET /api/v1/stock/by-branch/

# Sync
POST /api/v1/sync/products/
POST /api/v1/sync/orders/
POST /api/v1/sync/full/
GET  /api/v1/sync/status/
```

## Development Workflow

### Step 1: Environment Setup
1. Verify Django installation
2. Set up virtual environment
3. Install dependencies
4. Configure database
5. Create .env file with Cin7 credentials

### Step 2: Cin7 Client Development
1. Create base API client class
2. Implement authentication
3. Add rate limiting decorator
4. Create methods for each endpoint
5. Add error handling
6. Write unit tests

### Step 3: Django Models
1. Create models based on Cin7 schema
2. Add field validations
3. Create migrations
4. Add model methods
5. Create custom managers

### Step 4: API Development
1. Create serializers
2. Implement views
3. Set up URL routing
4. Add authentication
5. Test endpoints

### Step 5: Background Tasks
1. Set up Celery
2. Create sync tasks
3. Schedule periodic tasks
4. Add monitoring

## Error Handling Strategy

### Cin7 API Errors
```python
# Handle rate limits
429 -> Retry after delay (exponential backoff)

# Handle auth errors
401 -> Log error, notify admin

# Handle validation errors
400 -> Log detailed error, return to user

# Handle server errors
500/503 -> Retry up to 3 times, then log
```

### Sync Strategy
- Use `modifieddate` for incremental sync
- Store last sync timestamp
- Handle partial failures
- Log all sync activities
- Send alerts on critical failures

## Configuration

### Required Environment Variables
```bash
# Cin7 API
CIN7_API_URL=https://api.cin7.com/api/v1
CIN7_USERNAME=your_username
CIN7_API_KEY=your_api_key

# Django
SECRET_KEY=your_secret_key
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/saspulse

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Performance Targets
- API response time: < 200ms (avg)
- Cin7 sync completion: < 5 minutes for full sync
- Database queries: < 50ms (avg)
- Concurrent requests: 100+ req/sec

## Handoff to Other Agents

### To Frontend Agent
- API documentation (OpenAPI/Swagger)
- Sample responses for all endpoints
- Authentication token format
- WebSocket endpoints (if any)

### To Testing Agent
- List of all endpoints to test
- Test data fixtures
- Expected response formats
- Edge cases to cover

### To Data Sync Agent
- Cin7 client API documentation
- Sync task interface
- Error handling approach
- Data transformation rules

## Current Status
- [ ] Environment setup
- [ ] Cin7 API client
- [ ] Django models
- [ ] Database migrations
- [ ] REST API endpoints
- [ ] Celery tasks
- [ ] Tests written
- [ ] Documentation complete

## Notes & Decisions
<!-- Add important decisions and notes here -->
