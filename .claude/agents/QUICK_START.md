# SasPulse Agents - Quick Start Guide

## How to Use These Agents

Each agent file contains detailed specifications, responsibilities, and implementation guidelines for different aspects of the SasPulse project.

## Agent Quick Reference

### When to Use Each Agent

| Task | Use This Agent | File |
|------|---------------|------|
| Build Django models, REST APIs, Cin7 client | **Backend Agent** | `backend-agent.md` |
| Create React dashboard, UI components | **Frontend Agent** | `frontend-agent.md` |
| Write tests, ensure quality | **Testing Agent** | `testing-agent.md` |
| Docker, CI/CD, deployment | **DevOps Agent** | `devops-agent.md` |
| Cin7 data sync, ETL pipelines | **Data Sync Agent** | `data-sync-agent.md` |
| Write docs, guides, API specs | **Documentation Agent** | `documentation-agent.md` |

## Typical Development Workflow

### Phase 1: Foundation Setup
```
1. DevOps Agent: Set up Docker environment
2. Backend Agent: Create Django project structure
3. Backend Agent: Implement Cin7 API client
4. Data Sync Agent: Build sync manager
```

### Phase 2: Core Development
```
1. Backend Agent: Build Django models
2. Backend Agent: Create REST API endpoints
3. Frontend Agent: Set up React project
4. Frontend Agent: Build dashboard components
5. Testing Agent: Write unit tests
```

### Phase 3: Integration
```
1. Data Sync Agent: Implement sync tasks
2. Frontend Agent: Connect to backend APIs
3. Testing Agent: Write integration tests
4. Documentation Agent: Write API docs
```

### Phase 4: Deployment
```
1. Testing Agent: Run E2E tests
2. DevOps Agent: Set up CI/CD pipeline
3. DevOps Agent: Deploy to production
4. Documentation Agent: Write deployment guides
```

## Example: Building a New Feature

Let's say you want to add "Low Stock Alerts" feature:

### Step 1: Backend (Backend Agent)
```python
# apps/inventory/models.py
class LowStockAlert(models.Model):
    product = models.ForeignKey(Product)
    threshold = models.IntegerField()
    is_active = models.BooleanField(default=True)

# apps/inventory/views.py
class LowStockAlertViewSet(viewsets.ModelViewSet):
    queryset = LowStockAlert.objects.filter(is_active=True)
    serializer_class = LowStockAlertSerializer
```

### Step 2: Data Sync (Data Sync Agent)
```python
# apps/cin7/tasks.py
@shared_task
def check_low_stock_alerts():
    """Check for products below threshold"""
    alerts = LowStockAlert.objects.filter(is_active=True)
    for alert in alerts:
        if alert.product.stock_quantity < alert.threshold:
            send_low_stock_notification(alert)
```

### Step 3: Frontend (Frontend Agent)
```typescript
// components/LowStockAlerts.tsx
export function LowStockAlerts() {
  const { data: alerts } = useLowStockAlerts();

  return (
    <Card>
      <CardHeader>Low Stock Alerts</CardHeader>
      <CardContent>
        {alerts?.map(alert => (
          <AlertItem key={alert.id} alert={alert} />
        ))}
      </CardContent>
    </Card>
  );
}
```

### Step 4: Testing (Testing Agent)
```python
# tests/test_low_stock_alerts.py
def test_low_stock_alert_triggered():
    product = ProductFactory(stock_quantity=5)
    alert = LowStockAlertFactory(product=product, threshold=10)

    check_low_stock_alerts()

    assert Notification.objects.filter(
        alert=alert, type='low_stock'
    ).exists()
```

### Step 5: Documentation (Documentation Agent)
```markdown
# Low Stock Alerts

## Overview
Automatically monitor inventory levels and receive notifications when stock falls below defined thresholds.

## Setup
1. Navigate to Settings > Alerts
2. Click "Create Alert"
3. Select product and set threshold
4. Enable notifications

## API
GET /api/v1/alerts/low-stock/
POST /api/v1/alerts/low-stock/
```

## Communication Between Agents

Agents should coordinate through:

1. **Code Comments** - Tag next agent
```python
# TODO(frontend-agent): Add API endpoint for this feature
# TODO(testing-agent): Add tests for edge case where product is deleted
```

2. **Status Updates** - Update agent file's "Current Status" section

3. **Handoff Notes** - Use "Handoff to Other Agents" section

4. **Shared Models** - Keep data models consistent across agents

## Agent Coordination Example

```
Backend Agent creates endpoint:
  ↓
  Updates: backend-agent.md status
  ↓
  Adds: API documentation to handoff section
  ↓
Frontend Agent reads handoff:
  ↓
  Builds UI component using documented API
  ↓
  Updates: frontend-agent.md status
  ↓
  Requests: Testing scenarios in handoff
  ↓
Testing Agent reads handoff:
  ↓
  Writes integration tests
  ↓
  Reports: Coverage metrics back
```

## Best Practices

### For All Agents
1. ✅ Update your agent file's status regularly
2. ✅ Document decisions in "Notes & Decisions" section
3. ✅ Use handoff sections to communicate with other agents
4. ✅ Follow established code standards
5. ✅ Write clear commit messages

### Code Quality Standards
- Backend: Follow PEP 8, use type hints
- Frontend: Follow ESLint rules, use TypeScript
- Testing: Maintain >80% coverage
- Documentation: Keep docs up-to-date

### Version Control
- Feature branches: `feature/low-stock-alerts`
- Bug fixes: `fix/inventory-calculation`
- Hotfixes: `hotfix/critical-security-patch`

## Monitoring Progress

Check these files regularly:
- `AGENTS_OVERVIEW.md` - Overall project status
- Individual agent files - Specific progress
- `CHANGELOG.md` - Version history
- GitHub Issues - Outstanding tasks

## Getting Help

Each agent file contains:
- Detailed responsibilities
- Technical requirements
- Code examples
- Best practices
- Troubleshooting tips

Refer to the specific agent file for detailed guidance on your task.

## Project Success Criteria

- [ ] All APIs documented and working
- [ ] Dashboard responsive and performant
- [ ] Tests passing with >80% coverage
- [ ] Cin7 sync running reliably
- [ ] Docker setup complete
- [ ] CI/CD pipeline functional
- [ ] Production deployed
- [ ] Documentation complete

## Next Steps

1. Read `AGENTS_OVERVIEW.md` for project context
2. Review your assigned agent file
3. Check current status and pending tasks
4. Start implementing according to agent guidelines
5. Update status as you progress
6. Coordinate with other agents via handoff sections
