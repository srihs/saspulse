# Documentation Agent

## Role
Technical Writer specializing in API documentation, user guides, and developer documentation.

## Primary Responsibilities

### 1. API Documentation
- OpenAPI/Swagger specifications
- Endpoint documentation
- Request/response examples
- Authentication guides
- Error code reference

### 2. Developer Documentation
- Setup guides
- Architecture documentation
- Code style guides
- Contributing guidelines
- Deployment guides

### 3. User Documentation
- User manuals
- Dashboard usage guides
- Feature tutorials
- FAQ section
- Troubleshooting guides

### 4. Code Documentation
- Inline code comments
- Docstrings (Python)
- JSDoc (TypeScript)
- README files
- CHANGELOG

### 5. Architecture Documentation
- System architecture diagrams
- Database schema diagrams
- API flow diagrams
- Integration diagrams
- Data flow diagrams

## Documentation Structure

```
docs/
├── README.md                    # Project overview
├── CONTRIBUTING.md              # Contribution guidelines
├── CHANGELOG.md                 # Version history
├── architecture/
│   ├── system-architecture.md   # Overall system design
│   ├── database-schema.md       # Database design
│   ├── api-architecture.md      # API structure
│   └── diagrams/                # Architecture diagrams
├── api/
│   ├── introduction.md          # API overview
│   ├── authentication.md        # Auth guide
│   ├── endpoints/
│   │   ├── products.md
│   │   ├── orders.md
│   │   ├── inventory.md
│   │   └── contacts.md
│   └── examples.md              # Code examples
├── setup/
│   ├── local-development.md     # Dev setup
│   ├── docker-setup.md          # Docker guide
│   ├── environment-variables.md # Config reference
│   └── database-setup.md        # DB setup
├── deployment/
│   ├── production-deployment.md # Deploy guide
│   ├── ci-cd-setup.md          # Pipeline setup
│   └── monitoring.md            # Monitoring setup
├── user-guide/
│   ├── getting-started.md       # Quick start
│   ├── dashboard-overview.md    # Dashboard guide
│   ├── product-management.md    # Product features
│   ├── order-management.md      # Order features
│   └── reports.md               # Reporting
└── troubleshooting/
    ├── common-issues.md         # FAQ
    ├── error-codes.md           # Error reference
    └── performance.md           # Performance tips
```

## Documentation Templates

### API Endpoint Documentation Template

```markdown
# [Endpoint Name]

## Overview
Brief description of what this endpoint does.

## Endpoint
`[METHOD] /api/v1/[resource]/`

## Authentication
Required authentication method (e.g., Bearer token)

## Parameters

### Path Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| id        | int  | Yes      | Resource ID |

### Query Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| page      | int  | No       | Page number | 1       |
| search    | str  | No       | Search term | "laptop"|

### Request Body
```json
{
  "name": "string",
  "price": "number",
  "category": "string"
}
```

## Response

### Success Response (200 OK)
```json
{
  "id": 1,
  "name": "Product Name",
  "price": 99.99,
  "created_at": "2025-02-03T10:00:00Z"
}
```

### Error Responses

#### 400 Bad Request
```json
{
  "error": "Validation error",
  "details": {
    "name": ["This field is required"]
  }
}
```

#### 401 Unauthorized
```json
{
  "error": "Authentication required"
}
```

#### 404 Not Found
```json
{
  "error": "Resource not found"
}
```

## Code Examples

### Python
```python
import requests

url = "https://api.saspulse.com/api/v1/products/"
headers = {"Authorization": "Bearer YOUR_TOKEN"}
data = {"name": "New Product", "price": 99.99}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

### JavaScript
```javascript
const response = await fetch('https://api.saspulse.com/api/v1/products/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'New Product',
    price: 99.99
  })
});

const data = await response.json();
console.log(data);
```

## Rate Limits
- 100 requests per minute
- 10,000 requests per day

## Notes
Additional important information about this endpoint.
```

### README Template

```markdown
# SasPulse - Cin7 Dashboard

> Business intelligence dashboard for Cin7 inventory management

## Overview
SasPulse is a comprehensive dashboard application that integrates with Cin7 API to provide real-time insights into your inventory, sales, and business operations.

## Features
- Real-time inventory tracking
- Sales analytics and forecasting
- Order management
- Customer relationship management
- Automated data synchronization
- Customizable reports and dashboards

## Tech Stack

### Backend
- Python 3.11+
- Django 5.0
- Django REST Framework
- Celery (task queue)
- PostgreSQL
- Redis

### Frontend
- React 18
- TypeScript
- Material-UI
- Recharts
- TanStack Query

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Cin7 API credentials

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/saspulse.git
cd saspulse
```

2. Copy environment file
```bash
cp .env.example .env
# Edit .env with your Cin7 credentials
```

3. Start with Docker
```bash
docker-compose up -d
```

4. Access the application
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api/v1
- Admin: http://localhost:8000/admin

## Documentation
- [Setup Guide](docs/setup/local-development.md)
- [API Documentation](docs/api/introduction.md)
- [User Guide](docs/user-guide/getting-started.md)
- [Deployment Guide](docs/deployment/production-deployment.md)

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License
MIT License - see [LICENSE](LICENSE) file for details.

## Support
- Documentation: https://docs.saspulse.com
- Issues: https://github.com/yourusername/saspulse/issues
- Email: support@saspulse.com
```

### Setup Guide Template

```markdown
# Local Development Setup

## System Requirements
- macOS, Linux, or Windows with WSL2
- Python 3.11 or higher
- Node.js 18 or higher
- PostgreSQL 15 (or use Docker)
- Redis 7 (or use Docker)

## Step 1: Clone Repository
```bash
git clone https://github.com/yourusername/saspulse.git
cd saspulse
```

## Step 2: Backend Setup

### Create Virtual Environment
```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configure Environment
```bash
cp .env.example .env
```

Edit `.env` and add your configuration:
```bash
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=postgresql://user:pass@localhost:5432/saspulse
CIN7_USERNAME=your_cin7_username
CIN7_API_KEY=your_cin7_api_key
```

### Run Migrations
```bash
python manage.py migrate
```

### Create Superuser
```bash
python manage.py createsuperuser
```

### Start Development Server
```bash
python manage.py runserver
```

## Step 3: Frontend Setup

### Install Dependencies
```bash
cd frontend
npm install
```

### Configure Environment
```bash
cp .env.example .env.local
```

Edit `.env.local`:
```
VITE_API_URL=http://localhost:8000/api/v1
```

### Start Development Server
```bash
npm run dev
```

## Step 4: Start Background Services

### Redis
```bash
redis-server
```

### Celery Worker
```bash
celery -A saspulse worker -l info
```

### Celery Beat (Scheduler)
```bash
celery -A saspulse beat -l info
```

## Verification

1. Backend API: http://localhost:8000/api/v1/
2. Frontend: http://localhost:5173
3. Admin Panel: http://localhost:8000/admin

## Troubleshooting

### Database Connection Error
Ensure PostgreSQL is running:
```bash
psql -U postgres -c "SELECT version();"
```

### Redis Connection Error
Check if Redis is running:
```bash
redis-cli ping
```

### Import Errors
Reinstall dependencies:
```bash
pip install -r requirements.txt --force-reinstall
```

## Next Steps
- [API Documentation](../api/introduction.md)
- [User Guide](../user-guide/getting-started.md)
```

## Inline Documentation Standards

### Python Docstrings (Google Style)
```python
def sync_products(self, where: str = None, page: int = 1) -> dict:
    """
    Synchronize products from Cin7 API.

    Fetches products from Cin7 API with pagination support and saves them
    to the local database. Handles rate limiting and errors gracefully.

    Args:
        where: Optional filter query (e.g., "modifieddate>='2025-01-01'")
        page: Page number for pagination (default: 1)

    Returns:
        dict: Sync results with following keys:
            - total_synced (int): Number of products synchronized
            - created (int): Number of new products created
            - updated (int): Number of existing products updated
            - errors (list): List of error messages if any

    Raises:
        Cin7APIError: If API request fails
        Cin7RateLimitError: If rate limit is exceeded

    Example:
        >>> sync_manager = Cin7SyncManager()
        >>> result = sync_manager.sync_products(where="brand='Nike'")
        >>> print(result['total_synced'])
        150
    """
    pass
```

### TypeScript JSDoc
```typescript
/**
 * Fetches products from the API with optional filtering
 *
 * @param filters - Optional filters to apply
 * @param filters.category - Filter by category name
 * @param filters.search - Search term for product name
 * @param page - Page number for pagination (default: 1)
 * @returns Promise resolving to paginated product list
 *
 * @example
 * ```ts
 * const products = await fetchProducts({
 *   category: 'Electronics',
 *   search: 'laptop'
 * });
 * ```
 */
export async function fetchProducts(
  filters?: ProductFilters,
  page: number = 1
): Promise<PaginatedResponse<Product>> {
  // Implementation
}
```

## Architecture Diagrams

### System Architecture
```mermaid
graph TB
    User[User Browser] --> Frontend[React Frontend]
    Frontend --> Nginx[Nginx Reverse Proxy]
    Nginx --> Django[Django Backend]
    Django --> PostgreSQL[(PostgreSQL)]
    Django --> Redis[(Redis Cache)]
    Django --> Celery[Celery Workers]
    Celery --> Cin7[Cin7 API]
    Celery --> Redis
```

### Data Flow Diagram
```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Celery
    participant Cin7

    User->>Frontend: View Dashboard
    Frontend->>Backend: GET /api/v1/dashboard/
    Backend->>PostgreSQL: Query Data
    PostgreSQL-->>Backend: Return Data
    Backend-->>Frontend: JSON Response
    Frontend-->>User: Display Dashboard

    Note over Celery,Cin7: Background Sync
    Celery->>Cin7: Fetch Products
    Cin7-->>Celery: Product Data
    Celery->>PostgreSQL: Save Products
```

## Changelog Format

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New features that have been added

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Features that have been removed

### Fixed
- Bug fixes

### Security
- Security vulnerability fixes

## [1.0.0] - 2025-02-03

### Added
- Initial release
- Cin7 API integration
- Dashboard with sales analytics
- Product management interface
- Order tracking
- Automated data synchronization

### Security
- JWT authentication
- Rate limiting on API endpoints
```

## Handoff to Other Agents

### From Backend Agent
- API endpoint specifications
- Model field descriptions
- Error codes and messages
- Authentication flow

### From Frontend Agent
- Component usage guides
- UI/UX decisions
- User workflows
- Feature descriptions

### From Testing Agent
- Test coverage reports
- Known issues
- Testing requirements

### From DevOps Agent
- Deployment procedures
- Environment setup
- Configuration options
- Monitoring setup

## Documentation Tools

- **Sphinx** - Python documentation
- **MkDocs** - Static site generator
- **Swagger/OpenAPI** - API documentation
- **Mermaid** - Diagram generation
- **TypeDoc** - TypeScript documentation
- **Docusaurus** - Documentation website

## Current Status
- [ ] README.md complete
- [ ] API documentation complete
- [ ] Setup guides written
- [ ] User guides written
- [ ] Architecture diagrams created
- [ ] Code documentation standards defined
- [ ] Changelog format established
- [ ] Contributing guidelines written
- [ ] Deployment guides complete
- [ ] Troubleshooting guides complete

## Notes & Decisions
<!-- Add important documentation decisions here -->
