# SasPulse Development Agents

## Project Overview
SasPulse is a Django-based dashboard application that integrates with Cin7 API to provide inventory, sales, and business intelligence insights.

## Agent Team Structure

### 1. Backend API Agent (Django/Python Specialist)
**Role:** Backend Development & Cin7 Integration
**File:** `backend-agent.md`
**Responsibilities:**
- Django REST API development
- Cin7 API integration and client
- Database models and migrations
- Business logic implementation
- Rate limiting and caching strategies
- API authentication and security

### 2. Frontend Dashboard Agent (React/UI Specialist)
**Role:** Dashboard UI/UX Development
**File:** `frontend-agent.md`
**Responsibilities:**
- React dashboard components
- Data visualization (charts, graphs, tables)
- Responsive UI design
- State management (Redux/Context)
- API integration from frontend
- User experience optimization

### 3. QA/Testing Agent (Quality Assurance)
**Role:** Testing & Quality Assurance
**File:** `testing-agent.md`
**Responsibilities:**
- Unit tests (Python/Django)
- Integration tests
- Frontend tests (Jest/React Testing Library)
- API endpoint testing
- End-to-end testing
- Test coverage reporting

### 4. DevOps Agent (Deployment & Infrastructure)
**Role:** Deployment, CI/CD, Infrastructure
**File:** `devops-agent.md`
**Responsibilities:**
- Docker containerization
- CI/CD pipeline setup
- Environment configuration
- Database migrations management
- Monitoring and logging setup
- Performance optimization

### 5. Data Sync Agent (ETL Specialist)
**Role:** Data Synchronization & ETL
**File:** `data-sync-agent.md`
**Responsibilities:**
- Cin7 data synchronization
- ETL pipeline development
- Data transformation logic
- Incremental sync strategies
- Data validation and cleaning
- Scheduling and automation

### 6. Documentation Agent (Technical Writer)
**Role:** Documentation & Knowledge Management
**File:** `documentation-agent.md`
**Responsibilities:**
- API documentation
- Code documentation
- User guides and tutorials
- Architecture diagrams
- Deployment guides
- README and setup instructions

## Communication Protocol

### Agent Handoff Process
1. Each agent documents their work in their respective files
2. Agents create TODO lists for next agent in pipeline
3. Critical decisions are logged in this overview file
4. Code reviews happen via testing agent

### File Structure
```
.claude/agents/
├── AGENTS_OVERVIEW.md          # This file
├── backend-agent.md            # Backend agent context
├── frontend-agent.md           # Frontend agent context
├── testing-agent.md            # Testing agent context
├── devops-agent.md             # DevOps agent context
├── data-sync-agent.md          # Data sync agent context
└── documentation-agent.md      # Documentation agent context
```

## Project Phases

### Phase 1: Foundation (Week 1-2)
- **Backend Agent:** Set up Django models, Cin7 client
- **DevOps Agent:** Docker setup, local environment
- **Data Sync Agent:** Basic Cin7 API connection

### Phase 2: Core Development (Week 3-5)
- **Backend Agent:** REST API endpoints
- **Frontend Agent:** Dashboard UI components
- **Data Sync Agent:** Full sync implementation
- **Testing Agent:** Unit tests

### Phase 3: Integration (Week 6-7)
- **Frontend Agent:** Connect to backend APIs
- **Testing Agent:** Integration tests
- **Backend Agent:** API optimization

### Phase 4: Polish & Deploy (Week 8)
- **Testing Agent:** E2E tests, load testing
- **DevOps Agent:** Production deployment
- **Documentation Agent:** Complete documentation
- **All Agents:** Bug fixes and optimization

## Technology Stack

### Backend
- Python 3.11+
- Django 5.0+
- Django REST Framework
- Celery (async tasks)
- Redis (caching, task queue)
- PostgreSQL (production database)

### Frontend
- React 18+
- TypeScript
- Material-UI or Tailwind CSS
- Recharts/Chart.js (data visualization)
- React Query (data fetching)
- Vite (build tool)

### DevOps
- Docker & Docker Compose
- GitHub Actions (CI/CD)
- Nginx (reverse proxy)
- Gunicorn (WSGI server)

### Testing
- pytest (Python)
- Jest (JavaScript)
- React Testing Library
- Playwright (E2E)

## Success Metrics
- API response time < 200ms
- Dashboard load time < 2s
- Test coverage > 80%
- Zero critical security vulnerabilities
- Successful Cin7 sync every 5 minutes
- Handle rate limits gracefully (3/sec, 60/min, 5000/day)
