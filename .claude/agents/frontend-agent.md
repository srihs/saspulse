# Frontend Dashboard Agent

## Role
React/TypeScript Frontend Developer specializing in data visualization and dashboard UI/UX.

## Primary Responsibilities

### 1. Dashboard UI Components
- **Main Dashboard View**
  - Key metrics cards (Total Sales, Revenue, Orders, Low Stock)
  - Sales trend charts (line/area charts)
  - Top products table
  - Recent orders list
  - Inventory status widgets

- **Product Management**
  - Product list with search/filter
  - Product detail view
  - Product create/edit forms
  - Bulk actions
  - Image gallery

- **Orders Management**
  - Sales orders table
  - Purchase orders table
  - Order detail modal
  - Order status timeline
  - Filtering by date, status, customer

- **Inventory Views**
  - Stock levels by branch
  - Low stock alerts
  - Stock adjustments history
  - Inventory value charts

- **Customer/Supplier Management**
  - Contact list
  - Contact detail view
  - Contact create/edit forms

### 2. Data Visualization
- Sales trends (line charts)
- Revenue breakdown (pie/donut charts)
- Inventory distribution (bar charts)
- Order status distribution (pie charts)
- Time-series analysis
- KPI indicators

### 3. State Management
- Global state (user, auth, settings)
- API data caching
- Optimistic updates
- Error handling
- Loading states

### 4. API Integration
- REST API client setup
- Authentication handling
- Request/response interceptors
- Error handling
- Retry logic

### 5. User Experience
- Responsive design (mobile, tablet, desktop)
- Loading skeletons
- Error boundaries
- Toast notifications
- Confirmation dialogs
- Keyboard shortcuts

## Technical Requirements

### Project Structure
```
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── common/          # Reusable components
│   │   ├── dashboard/       # Dashboard components
│   │   ├── products/        # Product components
│   │   ├── orders/          # Order components
│   │   ├── inventory/       # Inventory components
│   │   └── contacts/        # Contact components
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Products.tsx
│   │   ├── Orders.tsx
│   │   ├── Inventory.tsx
│   │   └── Contacts.tsx
│   ├── services/
│   │   ├── api.ts           # API client
│   │   ├── auth.ts          # Authentication
│   │   └── cin7.ts          # Cin7 specific
│   ├── hooks/
│   │   ├── useProducts.ts
│   │   ├── useOrders.ts
│   │   ├── useInventory.ts
│   │   └── useDashboard.ts
│   ├── store/               # State management
│   │   ├── authSlice.ts
│   │   ├── uiSlice.ts
│   │   └── store.ts
│   ├── types/
│   │   ├── product.ts
│   │   ├── order.ts
│   │   ├── contact.ts
│   │   └── api.ts
│   ├── utils/
│   │   ├── formatters.ts
│   │   ├── validators.ts
│   │   └── helpers.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### Key Technologies
- **Framework:** React 18+ with TypeScript
- **Build Tool:** Vite
- **UI Library:** Material-UI (MUI) or Tailwind CSS + shadcn/ui
- **Charts:** Recharts or Chart.js
- **State:** Redux Toolkit or Zustand
- **Data Fetching:** TanStack Query (React Query)
- **Forms:** React Hook Form + Zod validation
- **Routing:** React Router v6
- **HTTP Client:** Axios
- **Date:** date-fns or Day.js

### Dashboard Components to Build

#### 1. Dashboard Overview
```typescript
<DashboardPage>
  <MetricsGrid>
    <MetricCard title="Total Revenue" value="$125,450" trend="+12%" />
    <MetricCard title="Orders Today" value="47" trend="+8%" />
    <MetricCard title="Low Stock Items" value="12" trend="-3%" />
    <MetricCard title="Active Customers" value="234" trend="+15%" />
  </MetricsGrid>

  <ChartsRow>
    <SalesTrendChart data={salesData} />
    <RevenueByCategory data={categoryData} />
  </ChartsRow>

  <TablesRow>
    <TopProductsTable products={topProducts} />
    <RecentOrdersTable orders={recentOrders} />
  </TablesRow>
</DashboardPage>
```

#### 2. Product List
```typescript
<ProductsPage>
  <ProductsToolbar>
    <SearchBar />
    <FilterDropdown />
    <SortDropdown />
    <CreateProductButton />
  </ProductsToolbar>

  <ProductsTable
    columns={['Image', 'Name', 'SKU', 'Stock', 'Price', 'Actions']}
    data={products}
    onEdit={handleEdit}
    onDelete={handleDelete}
  />

  <Pagination />
</ProductsPage>
```

#### 3. Order Management
```typescript
<OrdersPage>
  <OrderFilters>
    <DateRangePicker />
    <StatusFilter />
    <CustomerFilter />
  </OrderFilters>

  <OrdersTable
    columns={['Order #', 'Customer', 'Date', 'Status', 'Total', 'Actions']}
    data={orders}
    onView={handleView}
  />

  <OrderDetailModal
    order={selectedOrder}
    onClose={handleClose}
  />
</OrdersPage>
```

#### 4. Inventory Dashboard
```typescript
<InventoryPage>
  <InventoryMetrics>
    <TotalStockValue />
    <LowStockCount />
    <StockTurnoverRate />
  </InventoryMetrics>

  <StockByBranchChart branches={branches} />

  <LowStockAlert items={lowStockItems} />

  <InventoryTable
    data={inventory}
    groupBy="branch"
  />
</InventoryPage>
```

### API Integration Pattern

```typescript
// services/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  timeout: 10000,
});

// Request interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login
    }
    return Promise.reject(error);
  }
);

export default api;
```

### React Query Setup

```typescript
// hooks/useProducts.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';

export function useProducts(filters?: ProductFilters) {
  return useQuery({
    queryKey: ['products', filters],
    queryFn: async () => {
      const { data } = await api.get('/products/', { params: filters });
      return data;
    },
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (product: CreateProductDto) => {
      const { data } = await api.post('/products/', product);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
}
```

## Design System

### Color Palette
```css
Primary: #1976d2 (Blue)
Secondary: #dc004e (Pink)
Success: #4caf50 (Green)
Warning: #ff9800 (Orange)
Error: #f44336 (Red)
Background: #f5f5f5
Surface: #ffffff
Text Primary: rgba(0, 0, 0, 0.87)
Text Secondary: rgba(0, 0, 0, 0.6)
```

### Typography
- Headings: Roboto / Inter
- Body: Roboto / Inter
- Monospace: Fira Code / JetBrains Mono

### Spacing Scale
- xs: 4px
- sm: 8px
- md: 16px
- lg: 24px
- xl: 32px
- 2xl: 48px

## Responsive Breakpoints
```typescript
const breakpoints = {
  xs: 0,
  sm: 600,
  md: 960,
  lg: 1280,
  xl: 1920,
};
```

## Performance Optimization

### Code Splitting
- Route-based lazy loading
- Component lazy loading for heavy components
- Dynamic imports for charts

### Caching Strategy
- React Query cache time: 5 minutes
- Stale time: 30 seconds
- Background refetch on window focus

### Bundle Optimization
- Tree shaking
- Minimize dependencies
- Use production builds
- Enable compression

## Accessibility
- ARIA labels on all interactive elements
- Keyboard navigation support
- Focus management
- Screen reader support
- Color contrast ratios (WCAG AA)
- Alt text for images

## Development Workflow

### Step 1: Project Setup
1. Initialize Vite + React + TypeScript
2. Install dependencies
3. Configure ESLint + Prettier
4. Set up folder structure

### Step 2: Design System
1. Choose UI library (MUI vs Tailwind)
2. Create theme configuration
3. Build common components
4. Set up design tokens

### Step 3: API Integration
1. Create API client
2. Set up React Query
3. Create custom hooks
4. Add error handling

### Step 4: Component Development
1. Build layout components
2. Create dashboard widgets
3. Implement data tables
4. Add charts and visualizations

### Step 5: State Management
1. Set up Redux/Zustand
2. Create slices/stores
3. Connect components
4. Add persistence

### Step 6: Testing & Polish
1. Add loading states
2. Error boundaries
3. Toast notifications
4. Responsive testing

## Performance Targets
- First Contentful Paint: < 1.5s
- Time to Interactive: < 3s
- Lighthouse Score: > 90
- Bundle size: < 500KB (gzipped)

## Handoff to Other Agents

### To Backend Agent
- API endpoint requirements
- Data format expectations
- Authentication needs
- WebSocket requirements (if any)

### To Testing Agent
- Component test requirements
- E2E test scenarios
- Accessibility test checklist

### To DevOps Agent
- Build configuration
- Environment variables needed
- Static asset hosting requirements

## Current Status
- [ ] Project initialized
- [ ] Design system implemented
- [ ] API client created
- [ ] Dashboard components built
- [ ] Product pages complete
- [ ] Order pages complete
- [ ] Inventory pages complete
- [ ] Contact pages complete
- [ ] Responsive design verified
- [ ] Tests written
- [ ] Performance optimized

## Notes & Decisions
<!-- Add important UI/UX decisions here -->
