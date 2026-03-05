# SASPulse Analytics Structure

A clear breakdown of analytics separated into **BTS (Back-to-School) Specific** and **General/Year-Round** analytics.

---

## Table of Contents

1. [BTS-Specific Analytics](#bts-specific-analytics)
2. [General/Year-Round Analytics](#generalyear-round-analytics)
3. [Implementation Strategy](#implementation-strategy)
4. [Dashboard Organization](#dashboard-organization)

---

## BTS-Specific Analytics

**Focus:** January-February (Back-to-School season in NZ/Australia)

**Purpose:** Optimize the most critical 2-month revenue period

**Menu Location:** `/dashboard/sales/back-to-school/`

---

### ✅ 1. BTS Sales Forecasting (IMPLEMENTED)
**Location:** `/dashboard/bts-forecasting/`

**What it shows:**
- 2027 BTS season forecast (Jan-Feb)
- Top 20 schools ranked by predicted sales
- Top 20 products ranked by predicted sales
- Historical BTS trends (2022-2027)
- Growth rates year-over-year

**When to use:**
- October-December: Plan inventory for upcoming BTS
- After season: Compare actual vs predicted

**Key Metrics:**
- Total BTS revenue forecast: $XXX,XXX
- Confidence intervals (±20%)
- School-specific forecasts
- Product-specific forecasts

---

### ✅ 2. BTS Customer Lifetime Value (IMPLEMENTED)
**Location:** `/dashboard/bts-forecasting/` (bottom section)

**What it shows:**
- 12-month revenue predictions per school
- Churn risk assessment
- Value tier classification (VIP/High/Medium/Low)
- Growth trends

**BTS-Specific Focus:**
- Which schools are growing their BTS orders?
- Which schools are at risk of not ordering this BTS?
- VIP schools for BTS priority treatment

**Action Items:**
- Contact high-risk VIP schools before BTS season
- Nurture growing accounts
- Plan account manager visits

---

### 🔥 3. BTS Inventory Planning Dashboard
**Priority:** HIGH
**Location:** `/dashboard/bts-inventory/` (NEW)

**What it predicts:**
- How much of each product needed for BTS 2027
- When to place purchase orders
- Supplier lead times for BTS delivery
- Safety stock requirements

**Sections:**
1. **BTS Stock Requirements**
   - Product × Quantity needed
   - Current stock vs required
   - Gap analysis

2. **Purchase Order Recommendations**
   - What to order now
   - Order quantities
   - Target delivery dates (before January)

3. **BTS Stock-Out Risk**
   - Products at risk of running out during BTS
   - Critical alert items
   - Reorder urgency

**Timing:**
- **October-November:** Place orders
- **December:** Verify stock arrival
- **January:** Monitor daily stock levels

---

### 🔥 4. BTS Pre-Season Campaign Planner
**Priority:** MEDIUM
**Location:** `/dashboard/bts-campaigns/` (NEW)

**What it shows:**
- Best schools to target for early orders
- Optimal contact timing (based on historical patterns)
- Personalized product recommendations per school
- Email campaign effectiveness

**Campaign Types:**
1. **Early Bird Specials** (November-December)
   - Target: High-value schools
   - Offer: Early order discounts
   - Goal: Lock in orders early

2. **New Product Launch** (December)
   - Target: All schools
   - Showcase: New designs/products
   - Goal: Increase average order value

3. **Last Minute Rush** (Late January)
   - Target: Schools that haven't ordered
   - Offer: Quick delivery guarantee
   - Goal: Capture remaining demand

**Metrics:**
- Email open rates
- Conversion rates
- Revenue per campaign
- ROI per campaign

---

### 📊 5. BTS Performance Dashboard
**Priority:** MEDIUM
**Location:** `/dashboard/bts-performance/` (NEW)

**What it shows:**
- **Actual vs Forecast** comparison
- **This BTS vs Last BTS** comparison
- Daily sales tracking during Jan-Feb
- Real-time stock levels during BTS

**Key Reports:**
1. **Daily BTS Tracker** (Jan-Feb)
   - Today's sales
   - Week-to-date
   - Month-to-date
   - Comparison to forecast

2. **School Performance**
   - Which schools ordered vs expected
   - Order values vs forecast
   - Missing schools (expected but didn't order)

3. **Product Performance**
   - Best-selling products
   - Slow movers
   - Stock-outs that occurred

**Post-Season Analysis:**
- What went right/wrong
- Forecast accuracy
- Lessons for next year

---

### 📊 6. BTS School Segmentation
**Priority:** LOW
**Location:** `/dashboard/bts-segments/` (NEW)

**What it shows:**
- Schools grouped by ordering behavior
- Segment characteristics
- Targeted strategies per segment

**Segments:**
1. **Early Birds** (Order in November-December)
   - Characteristics: Well-organized, large orders
   - Strategy: Early bird discounts, priority service

2. **Regular Orderers** (Order in January)
   - Characteristics: Consistent, predictable
   - Strategy: Maintain relationship, remind early

3. **Last Minute** (Order in late January-February)
   - Characteristics: Disorganized, urgent needs
   - Strategy: Quick delivery, premium pricing

4. **Skippers** (Don't order every year)
   - Characteristics: Irregular, small
   - Strategy: Win-back campaigns

---

## General/Year-Round Analytics

**Focus:** All sales throughout the year (not just BTS)

**Purpose:** Optimize overall business performance

**Menu Location:** `/dashboard/analytics/`

---

### 🔥 1. Revenue Forecasting Dashboard
**Priority:** HIGHEST
**Location:** `/dashboard/revenue-forecast/` (NEW)

**What it predicts:**
- Monthly revenue for next 12 months
- Quarterly projections
- Year-end forecast
- Budget vs actual tracking

**Breakdowns:**
- By month
- By product category
- By customer type (wholesale vs retail)
- By school (top customers)

**Visualizations:**
- Line chart: Actual vs Forecast vs Budget
- Waterfall: Revenue changes month-to-month
- Heat map: Revenue by month × category
- YoY comparison

**When to use:**
- Monthly: Review performance vs forecast
- Quarterly: Update forecasts
- Annually: Set budgets and targets

**Key Metrics:**
- Total annual revenue forecast
- Growth rate YoY
- Revenue variance (actual vs forecast)
- Confidence intervals

---

### 🔥 2. Stock-Out Risk Prediction
**Priority:** HIGHEST (Daily operational impact)
**Location:** `/dashboard/stock-alerts/` (NEW)

**What it predicts:**
- Which products will run out of stock
- Days until stock-out
- Impact on revenue if not restocked

**Daily Monitoring:**
1. **Critical (< 7 days)**
   - Immediate action required
   - SMS/Email alerts
   - Emergency purchase orders

2. **Warning (7-30 days)**
   - Plan reorder
   - Check supplier availability
   - Update customers if needed

3. **Watch List (30-60 days)**
   - Monitor trends
   - Plan purchase timing

**Features:**
- Real-time stock tracking
- Sales velocity calculation
- Supplier lead time integration
- Automated reorder recommendations

**Business Impact:**
- Prevent lost sales
- Reduce emergency orders
- Optimize inventory investment
- Better customer service

---

### 🔥 3. Customer Account Health Dashboard
**Priority:** HIGH
**Location:** `/dashboard/account-health/` (NEW)

**What it tracks (Year-round, not just BTS):**
- Overall account health score (0-100)
- Order frequency (all months)
- Revenue trends (12-month rolling)
- Payment history
- Engagement level

**Health Score Components:**
1. **Recency** (30%) - Days since last order
2. **Frequency** (25%) - Orders per year
3. **Monetary** (25%) - Annual revenue
4. **Growth** (10%) - Revenue trend
5. **Engagement** (10%) - Communication responsiveness

**Risk Indicators:**
- No orders in 90+ days
- Declining order frequency
- Reduced order values
- Payment delays
- Reduced product variety

**Actions by Score:**
- **90-100:** VIP treatment, thank you gifts
- **70-89:** Maintain relationship, periodic check-ins
- **50-69:** Increase engagement, special offers
- **30-49:** Intervention needed, urgent call
- **0-29:** At-risk, executive escalation

**Views:**
- All accounts ranked by health
- At-risk accounts (score < 50)
- VIP accounts (score > 90)
- Accounts by account manager

---

### 🔥 4. Seasonal Demand Forecasting
**Priority:** HIGH
**Location:** `/dashboard/seasonal-demand/` (NEW)

**What it shows:**
- Monthly demand forecast by product category
- Seasonal patterns for entire year
- Peak periods for each category
- Slow seasons requiring promotions

**Categories:**
- Blazers
- Trousers/Skirts
- Shirts/Blouses
- Sports uniforms
- Accessories
- PE/Sports gear

**Seasonal Insights:**
- **January-February:** BTS peak
- **March-April:** Mid-year replacements
- **May-June:** Winter sports gear
- **July-August:** Mid-year uniform updates
- **September-October:** Spring sports
- **November-December:** Next year planning

**Business Use:**
- Plan purchases for entire year
- Schedule promotions for slow periods
- Optimize warehouse space
- Reduce excess inventory

---

### 📊 5. Product Performance Dashboard
**Priority:** MEDIUM
**Location:** `/dashboard/product-performance/` (NEW)

**What it analyzes:**
- Best/worst performing products
- Product lifecycle stage
- Profit margins by product
- Stock turnover rates

**Key Metrics per Product:**
1. **Revenue Contribution**
   - Total sales
   - % of overall revenue
   - Trend (growing/declining)

2. **Profitability**
   - Gross margin
   - Contribution margin
   - ROI

3. **Inventory Efficiency**
   - Stock turnover rate
   - Days to sell
   - Carrying cost

4. **Customer Adoption**
   - Number of schools buying
   - Repeat purchase rate
   - Market penetration

**Visualizations:**
- BCG Matrix (Stars, Cash Cows, Question Marks, Dogs)
- Product lifecycle curves
- Pareto chart (80/20 rule)
- Heat map: Product × School purchases

**Actions:**
- **Stars:** Invest more, expand
- **Cash Cows:** Maintain, optimize
- **Question Marks:** Decide invest or divest
- **Dogs:** Phase out or promote heavily

---

### 📊 6. Price Optimization Dashboard
**Priority:** MEDIUM
**Location:** `/dashboard/pricing/` (NEW)

**What it analyzes:**
- Price elasticity by product
- Optimal pricing for profit maximization
- Competitive pricing insights
- Discount effectiveness

**Price Elasticity:**
```
Elasticity = (% Change in Quantity) / (% Change in Price)
```

**Categories:**
- **Elastic (>1):** Price-sensitive, discounts drive volume
- **Unit Elastic (=1):** Balanced
- **Inelastic (<1):** Price increases won't hurt demand

**Recommendations:**
- Products where price can increase
- Products needing discounts for volume
- Bundle pricing opportunities
- Seasonal pricing adjustments

**Scenarios:**
- "What if we increase blazer prices by 5%?"
- "What discount drives 20% more volume?"
- "Optimal bundle: Blazer + Trousers + Tie"

---

### 📊 7. Sales Pipeline & Lead Management
**Priority:** MEDIUM
**Location:** `/dashboard/pipeline/` (NEW)

**What it tracks:**
- Prospective schools (leads)
- Conversion probability
- Expected revenue from pipeline
- Sales team performance

**Pipeline Stages:**
1. **Lead** - Initial contact
2. **Qualified** - Genuine interest
3. **Proposal** - Quote sent
4. **Negotiation** - Discussing terms
5. **Won** - Order placed
6. **Lost** - Didn't convert

**Metrics:**
- Conversion rate by stage
- Average time per stage
- Win rate
- Revenue in pipeline
- Sales team performance

**Predictive Analytics:**
- Lead scoring (which leads likely to convert)
- Expected close date
- Revenue forecast from pipeline

---

### 📊 8. Supplier Performance Analytics
**Priority:** LOW
**Location:** `/dashboard/suppliers/` (NEW)

**What it tracks:**
- On-time delivery rate
- Quality issues
- Price trends
- Lead time reliability
- Fill rate

**Metrics per Supplier:**
1. **Delivery Performance**
   - On-time delivery %
   - Average delay days
   - Reliability score

2. **Quality**
   - Defect rate
   - Returns/complaints
   - Quality score

3. **Pricing**
   - Average cost
   - Price trend
   - Cost competitiveness

4. **Responsiveness**
   - Order confirmation time
   - Communication quality
   - Problem resolution

**Scorecard:**
- Overall supplier rating (0-100)
- Traffic light indicators
- Recommended actions (continue/improve/replace)

---

### 📊 9. Product Mix Optimization
**Priority:** LOW
**Location:** `/dashboard/product-mix/` (NEW)

**What it analyzes:**
- Products bought together
- Cross-sell opportunities
- Bundle recommendations
- Market basket analysis

**Association Rules:**
```
If customer buys {Blazer}
Then 87% also buy {Trousers}
Confidence: 87%
Support: 65%
```

**Recommendations:**
- Create bundles (Blazer + Trousers + Tie)
- Cross-sell suggestions for sales team
- "Frequently bought together" displays
- Promotional package ideas

**Business Impact:**
- Increase average order value
- Simplify ordering for schools
- Move slow-moving items via bundles

---

### 🚀 10. Anomaly Detection System
**Priority:** LOW (Advanced)
**Location:** `/dashboard/anomalies/` (NEW)

**What it detects:**
- Unusual sales spikes/drops
- Inventory discrepancies
- Suspicious order patterns
- Data quality issues

**Alerts:**
- "Wellington College ordered 300% above normal"
- "Blazer sales dropped 50% this month"
- "Stock level mismatch: Expected 500, Found 350"
- "Payment delayed 30+ days from 3 customers"

**Response:**
- Investigate cause
- Fix data issues
- Capitalize on trends
- Prevent fraud

---

## Implementation Strategy

### Phase 1: BTS Focus (Months 1-3)
**Goal:** Optimize the most critical revenue period

✅ **Already Done:**
- BTS Sales Forecasting
- BTS Customer Lifetime Value

**To Build:**
1. BTS Inventory Planning Dashboard (Month 1)
2. BTS Performance Dashboard (Month 2)
3. BTS Pre-Season Campaign Planner (Month 3)

**Target:** Ready before October 2026 (for BTS 2027 planning)

---

### Phase 2: Year-Round Optimization (Months 4-6)
**Goal:** Optimize daily operations and revenue

**Priority Order:**
1. Stock-Out Risk Prediction (Month 4) - Prevents daily revenue loss
2. Revenue Forecasting Dashboard (Month 5) - Critical for planning
3. Customer Account Health Dashboard (Month 6) - Retention focus

---

### Phase 3: Strategic Analytics (Months 7-12)
**Goal:** Long-term competitive advantage

**Priority Order:**
1. Seasonal Demand Forecasting (Month 7)
2. Product Performance Dashboard (Month 8)
3. Price Optimization Dashboard (Month 9-10)
4. Sales Pipeline & Lead Management (Month 11-12)

---

### Phase 4: Advanced Features (Year 2)
**Goal:** Machine learning and predictive analytics

1. Anomaly Detection System
2. Supplier Performance Analytics
3. Product Mix Optimization
4. Dynamic Pricing Engine

---

## Dashboard Organization

### Main Menu Structure

```
Dashboard
├── Sales
│   ├── Overview
│   ├── Back to School
│   │   ├── BTS Forecasting ✅
│   │   ├── BTS Inventory Planning (NEW)
│   │   ├── BTS Performance (NEW)
│   │   └── BTS Campaign Planner (NEW)
│   └── General Sales Reports
│
├── Analytics (NEW)
│   ├── Revenue Forecasting (NEW)
│   ├── Customer Health (NEW)
│   ├── Product Performance (NEW)
│   ├── Seasonal Demand (NEW)
│   └── Price Optimization (NEW)
│
├── Inventory
│   ├── Stock Overview
│   ├── Stock-Out Alerts (NEW)
│   └── Reorder Management (NEW)
│
├── Customers
│   ├── Account Management
│   ├── Sales Pipeline (NEW)
│   └── Lead Scoring (NEW)
│
└── Suppliers
    └── Performance Tracking (NEW)
```

---

## Key Differences: BTS vs General

| Aspect | BTS Analytics | General Analytics |
|--------|---------------|-------------------|
| **Time Frame** | Jan-Feb only | Year-round |
| **Purpose** | Optimize 2-month peak | Optimize entire year |
| **Update Frequency** | Annual (Oct planning) | Monthly/Daily |
| **Focus** | Schools, Uniforms | All products, All customers |
| **Urgency** | Seasonal critical | Continuous improvement |
| **Planning Horizon** | 3-4 months ahead | 12 months rolling |
| **Key Metric** | BTS revenue forecast | Annual revenue forecast |
| **Primary Users** | Purchasing, Sales | Management, Finance |

---

## Success Metrics

### BTS-Specific Metrics
- BTS forecast accuracy (target: >90%)
- BTS stock-out incidents (target: <5)
- BTS revenue growth YoY (target: +15%)
- Early orders (Nov-Dec) as % of total (target: >40%)

### General Metrics
- Annual revenue forecast accuracy (target: >85%)
- Stock-out prevention (target: 70% reduction)
- Customer retention rate (target: >90%)
- Inventory turnover rate (target: +20%)
- Average order value (target: +10%)

---

## Conclusion

By separating **BTS analytics** from **General analytics**, we can:

1. **Focus resources** on the most critical period (BTS)
2. **Optimize year-round** operations separately
3. **Avoid confusion** - clear purpose for each dashboard
4. **Measure impact** - Different KPIs for each category
5. **Scale systematically** - Phase 1 (BTS) then Phase 2 (General)

**Next Steps:**
1. Validate this structure with stakeholders
2. Prioritize Phase 1 (BTS) features
3. Build BTS Inventory Planning Dashboard first
4. Gather feedback from BTS 2027 season
5. Then expand to General analytics

---

**Document Version:** 1.0
**Last Updated:** 2026-02-18
**Author:** Claude Code + SAS Team
**Status:** Strategic Planning Document
