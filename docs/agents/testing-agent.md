# QA/Testing Agent

## Role
Quality Assurance Engineer specializing in automated testing, test coverage, and quality metrics.

## Primary Responsibilities

### 1. Backend Testing (Python/Django)
- **Unit Tests**
  - Model tests
  - API client tests
  - Serializer tests
  - Business logic tests
  - Utility function tests

- **Integration Tests**
  - API endpoint tests
  - Database integration tests
  - Celery task tests
  - Authentication flow tests

- **API Testing**
  - Test all REST endpoints
  - Validate request/response formats
  - Test error handling
  - Test pagination
  - Test filtering and searching

### 2. Frontend Testing (React/TypeScript)
- **Unit Tests**
  - Component tests
  - Hook tests
  - Utility function tests
  - State management tests

- **Integration Tests**
  - API integration tests
  - Form submission tests
  - Navigation tests

- **Visual Testing**
  - Component snapshots
  - Visual regression testing

### 3. End-to-End Testing
- User workflows
- Cross-browser testing
- Mobile responsive testing
- Performance testing

### 4. Test Coverage & Reporting
- Maintain >80% code coverage
- Generate coverage reports
- Track test metrics
- Identify untested code

### 5. Performance Testing
- API load testing
- Frontend performance testing
- Database query optimization
- Identify bottlenecks

## Technical Requirements

### Backend Testing Stack
- **pytest** - Testing framework
- **pytest-django** - Django integration
- **pytest-cov** - Coverage reporting
- **factory_boy** - Test data factories
- **faker** - Fake data generation
- **responses** - Mock HTTP requests
- **freezegun** - Time mocking

### Frontend Testing Stack
- **Vitest** - Test runner (Vite-native)
- **Jest** - Alternative test runner
- **React Testing Library** - Component testing
- **MSW** (Mock Service Worker) - API mocking
- **Playwright** or **Cypress** - E2E testing
- **@testing-library/user-event** - User interaction simulation

### Test Structure

```
# Backend
tests/
├── unit/
│   ├── test_models.py
│   ├── test_serializers.py
│   ├── test_cin7_client.py
│   └── test_utils.py
├── integration/
│   ├── test_api_products.py
│   ├── test_api_orders.py
│   ├── test_api_inventory.py
│   └── test_sync_tasks.py
├── factories/
│   ├── product_factory.py
│   ├── order_factory.py
│   └── contact_factory.py
└── conftest.py

# Frontend
frontend/src/
├── components/
│   └── __tests__/
│       ├── Dashboard.test.tsx
│       ├── ProductList.test.tsx
│       └── OrderTable.test.tsx
├── hooks/
│   └── __tests__/
│       ├── useProducts.test.ts
│       └── useOrders.test.ts
└── utils/
    └── __tests__/
        └── formatters.test.ts
```

## Backend Test Examples

### 1. Model Tests
```python
# tests/unit/test_models.py
import pytest
from apps.cin7.models import Product
from tests.factories import ProductFactory

@pytest.mark.django_db
class TestProductModel:
    def test_create_product(self):
        product = ProductFactory(
            name="Test Product",
            style_code="TEST-001"
        )
        assert product.id is not None
        assert product.name == "Test Product"
        assert str(product) == "Test Product (TEST-001)"

    def test_product_price_calculation(self):
        product = ProductFactory(base_price=100.00)
        assert product.calculate_final_price() == 100.00

    def test_low_stock_check(self):
        product = ProductFactory(stock_quantity=5, min_stock_level=10)
        assert product.is_low_stock() is True
```

### 2. API Tests
```python
# tests/integration/test_api_products.py
import pytest
from rest_framework.test import APIClient
from tests.factories import ProductFactory, UserFactory

@pytest.mark.django_db
class TestProductAPI:
    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_list_products(self):
        ProductFactory.create_batch(5)
        response = self.client.get('/api/v1/products/')

        assert response.status_code == 200
        assert len(response.data['results']) == 5

    def test_create_product(self):
        data = {
            'name': 'New Product',
            'style_code': 'NEW-001',
            'price': '99.99'
        }
        response = self.client.post('/api/v1/products/', data)

        assert response.status_code == 201
        assert response.data['name'] == 'New Product'

    def test_filter_products_by_category(self):
        ProductFactory(category='Electronics')
        ProductFactory(category='Clothing')

        response = self.client.get('/api/v1/products/?category=Electronics')

        assert response.status_code == 200
        assert len(response.data['results']) == 1
```

### 3. Cin7 Client Tests
```python
# tests/unit/test_cin7_client.py
import pytest
import responses
from apps.cin7.client import Cin7Client
from apps.cin7.exceptions import Cin7RateLimitError

class TestCin7Client:
    def setup_method(self):
        self.client = Cin7Client(
            username='test_user',
            api_key='test_key'
        )

    @responses.activate
    def test_get_products_success(self):
        responses.add(
            responses.GET,
            'https://api.cin7.com/api/v1/Products',
            json=[{'id': 1, 'name': 'Product 1'}],
            status=200
        )

        products = self.client.get_products()
        assert len(products) == 1
        assert products[0]['name'] == 'Product 1'

    @responses.activate
    def test_rate_limit_handling(self):
        responses.add(
            responses.GET,
            'https://api.cin7.com/api/v1/Products',
            status=429
        )

        with pytest.raises(Cin7RateLimitError):
            self.client.get_products()

    @responses.activate
    def test_retry_on_server_error(self):
        # First call fails, second succeeds
        responses.add(
            responses.GET,
            'https://api.cin7.com/api/v1/Products',
            status=500
        )
        responses.add(
            responses.GET,
            'https://api.cin7.com/api/v1/Products',
            json=[{'id': 1, 'name': 'Product 1'}],
            status=200
        )

        products = self.client.get_products()
        assert len(products) == 1
```

## Frontend Test Examples

### 1. Component Tests
```typescript
// components/__tests__/ProductList.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProductList } from '../ProductList';
import { server } from '../../mocks/server';
import { rest } from 'msw';

describe('ProductList', () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });

  const wrapper = ({ children }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );

  it('renders products list', async () => {
    render(<ProductList />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('Product 1')).toBeInTheDocument();
      expect(screen.getByText('Product 2')).toBeInTheDocument();
    });
  });

  it('filters products by search', async () => {
    const user = userEvent.setup();
    render(<ProductList />, { wrapper });

    const searchInput = screen.getByPlaceholderText('Search products...');
    await user.type(searchInput, 'Product 1');

    await waitFor(() => {
      expect(screen.getByText('Product 1')).toBeInTheDocument();
      expect(screen.queryByText('Product 2')).not.toBeInTheDocument();
    });
  });

  it('handles loading state', () => {
    server.use(
      rest.get('/api/v1/products/', (req, res, ctx) => {
        return res(ctx.delay('infinite'));
      })
    );

    render(<ProductList />, { wrapper });
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('handles error state', async () => {
    server.use(
      rest.get('/api/v1/products/', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<ProductList />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/error loading products/i)).toBeInTheDocument();
    });
  });
});
```

### 2. Hook Tests
```typescript
// hooks/__tests__/useProducts.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useProducts } from '../useProducts';
import { server } from '../../mocks/server';

describe('useProducts', () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });

  const wrapper = ({ children }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );

  it('fetches products successfully', async () => {
    const { result } = renderHook(() => useProducts(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(2);
  });

  it('handles filters correctly', async () => {
    const { result } = renderHook(
      () => useProducts({ category: 'Electronics' }),
      { wrapper }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(1);
  });
});
```

### 3. E2E Tests (Playwright)
```typescript
// e2e/dashboard.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/dashboard');
  });

  test('displays key metrics', async ({ page }) => {
    await expect(page.getByText('Total Revenue')).toBeVisible();
    await expect(page.getByText('Orders Today')).toBeVisible();
    await expect(page.getByText('Low Stock Items')).toBeVisible();
  });

  test('sales chart is interactive', async ({ page }) => {
    const chart = page.locator('[data-testid="sales-chart"]');
    await expect(chart).toBeVisible();

    // Hover over data point
    await chart.hover();
    await expect(page.getByRole('tooltip')).toBeVisible();
  });

  test('navigates to products page', async ({ page }) => {
    await page.click('text=Products');
    await expect(page).toHaveURL(/.*products/);
    await expect(page.getByRole('heading', { name: 'Products' })).toBeVisible();
  });
});

test.describe('Product Management', () => {
  test('creates new product', async ({ page }) => {
    await page.goto('http://localhost:5173/products');
    await page.click('button:has-text("Create Product")');

    await page.fill('[name="name"]', 'Test Product');
    await page.fill('[name="styleCode"]', 'TEST-001');
    await page.fill('[name="price"]', '99.99');

    await page.click('button:has-text("Save")');

    await expect(page.getByText('Product created successfully')).toBeVisible();
    await expect(page.getByText('Test Product')).toBeVisible();
  });

  test('filters products', async ({ page }) => {
    await page.goto('http://localhost:5173/products');

    await page.fill('[placeholder="Search products..."]', 'Electronics');

    await expect(page.getByText('Laptop')).toBeVisible();
    await expect(page.getByText('T-Shirt')).not.toBeVisible();
  });
});
```

## Test Coverage Targets

### Backend Coverage
- Overall: >80%
- Models: >90%
- Serializers: >85%
- Views/APIs: >85%
- Cin7 Client: >90%
- Business Logic: >90%

### Frontend Coverage
- Components: >80%
- Hooks: >90%
- Utils: >90%
- Overall: >75%

## CI/CD Integration

### GitHub Actions Workflow
```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=apps --cov-report=xml
      - uses: codecov/codecov-action@v3

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm run test -- --coverage
      - uses: codecov/codecov-action@v3

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npx playwright install
      - run: npm run test:e2e
```

## Performance Testing

### Load Testing (Locust)
```python
# locustfile.py
from locust import HttpUser, task, between

class DashboardUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login
        self.client.post("/api/auth/login/", {
            "username": "test",
            "password": "test123"
        })

    @task(3)
    def view_dashboard(self):
        self.client.get("/api/v1/dashboard/summary/")

    @task(2)
    def list_products(self):
        self.client.get("/api/v1/products/")

    @task(1)
    def view_orders(self):
        self.client.get("/api/v1/sales-orders/")
```

## Test Data Management

### Factories
```python
# tests/factories/product_factory.py
import factory
from apps.cin7.models import Product

class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Faker('word')
    style_code = factory.Sequence(lambda n: f'PROD-{n:04d}')
    description = factory.Faker('text')
    price = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    stock_quantity = factory.Faker('random_int', min=0, max=1000)
    category = factory.Faker('word')
    brand = factory.Faker('company')
```

## Handoff to Other Agents

### To Backend Agent
- Failed test reports
- Coverage gaps
- Performance issues found
- API inconsistencies

### To Frontend Agent
- UI/UX issues found
- Accessibility violations
- Performance bottlenecks
- Browser compatibility issues

### To DevOps Agent
- Test environment requirements
- CI/CD pipeline status
- Test infrastructure needs

## Current Status
- [ ] Backend test setup complete
- [ ] Frontend test setup complete
- [ ] Unit tests written (backend)
- [ ] Unit tests written (frontend)
- [ ] Integration tests written
- [ ] E2E tests written
- [ ] Performance tests written
- [ ] CI/CD integration complete
- [ ] Coverage targets met

## Notes & Decisions
<!-- Add important testing decisions here -->
