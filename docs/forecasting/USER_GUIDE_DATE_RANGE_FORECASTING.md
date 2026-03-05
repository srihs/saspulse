# User Guide: Date Range Based Forecasting

## Overview

The SASPulse Sales Forecasting dashboard now supports flexible date range selection, allowing you to view forecasts for any period within a 365-day window.

---

## Accessing the Dashboard

1. Log in to SASPulse
2. Navigate to: **Dashboard → Sales Forecasting**
3. URL: `http://localhost:8000/dashboard/forecasting/`

---

## How to Use

### Method 1: Quick Select Buttons (Recommended)

For common date ranges, use the quick select buttons:

1. **Next 7 Days**: View forecasts for the upcoming week
2. **Next 30 Days**: View forecasts for the next month
3. **Next 90 Days**: View forecasts for the next quarter
4. **This Month**: View forecasts for the current calendar month

**Steps**:
1. Click one of the quick select buttons
2. The date fields will auto-populate
3. Click "Apply Filters"
4. View your forecasts

### Method 2: Manual Date Selection

For custom date ranges:

1. Click on the **Start Date** field
2. Select your desired start date from the calendar picker
3. Click on the **End Date** field
4. Select your desired end date from the calendar picker
5. Click "Apply Filters"
6. View your forecasts

---

## Date Range Rules

### Valid Ranges
- ✅ End date must be after start date
- ✅ Maximum range: 365 days
- ✅ Any dates within the next 365 days

### Invalid Ranges
- ❌ End date before or equal to start date
- ❌ Date range exceeding 365 days

**What happens**: You'll see an error message, and the form won't submit.

---

## Understanding the Display

### Summary Cards (Top of Page)

1. **Total Forecasts**: Number of entities (products, schools, etc.) forecasted
2. **Forecast Horizon**: Your selected date range (e.g., "2026-03-05 to 2026-04-04 (30 days)")
3. **Average Accuracy**: Overall forecast accuracy score
4. **Model Type**: AI/ML model used (typically "Hybrid AI")

### Date Range Info

Below the filters, you'll see:
```
Selected Range: 2026-03-05 to 2026-04-04 (30 days) [Cached]
```

- **Date range**: Your selected dates
- **Days count**: Number of days in the range
- **Cached badge**: Appears if data loaded from cache (faster)

### Forecast Table

Displays forecasts based on your selected aggregation level:

**Product Level**:
- Shows parent products with expandable variations (sizes)
- Click a product row to see size-by-size breakdown
- Shows stock on hand, incoming stock, and forecasted demand
- **Stock Gap**: Green (surplus) or Red (shortage)

**School Level**:
- Shows forecasts by school
- Click "Products" to see product breakdown for that school

**Shop/Category Level**:
- Shows forecasts by location or category

---

## Interpreting Stock Gaps (Product Level)

For each product variation (size):

- **Stock on Hand**: Current inventory
- **Incoming Stock**: Purchase orders in transit
- **Forecasted Stock**: Predicted demand for selected date range
- **Stock Gap**: (On Hand + Incoming) - Forecasted
  - **Green (+50)**: Surplus of 50 units - you have enough stock
  - **Red (-30)**: Shortage of 30 units - you need to reorder

---

## Advanced Features

### Daily Forecast Details

Click "Details" button to see:
- Day-by-day breakdown
- 7-day summary
- Peak demand day
- Confidence intervals (80% probability range)

### Forecast Chart

Click "Chart" button to view:
- Visual trend line
- Confidence bands
- Interactive chart with zoom/pan

---

## Performance Tips

### Faster Loading

1. **Use Quick Select buttons** for common ranges (7, 30, 90 days)
   - These are cached for 30 minutes
   - Second load is instant

2. **Avoid excessive ranges**
   - Smaller date ranges load faster
   - Recommended: 7-90 days for detailed analysis

3. **Cache indicator**
   - Look for the "Cached" badge
   - Indicates data loaded from memory (very fast)

### Best Practices

1. **Start with Quick Select**
   - Use "Next 30 Days" for general overview
   - Drill down with custom ranges if needed

2. **Meaningful Date Ranges**
   - Align with business cycles (weekly, monthly, quarterly)
   - Use "This Month" for month-end planning

3. **Regular Refresh**
   - Common ranges cache for 30 minutes
   - Custom ranges cache for 10 minutes
   - Refresh page for latest data if needed

---

## Examples

### Example 1: Weekly Inventory Planning

**Goal**: Plan next week's inventory needs

**Steps**:
1. Select aggregation level: **By Product**
2. Click: **Next 7 Days**
3. Click: **Apply Filters**
4. Review products with negative stock gaps
5. Click variations to see size-by-size needs

### Example 2: Monthly Demand Forecast

**Goal**: Forecast demand for March 2026

**Steps**:
1. Select aggregation level: **By School**
2. Click on **Start Date**: Select March 1, 2026
3. Click on **End Date**: Select March 31, 2026
4. Click: **Apply Filters**
5. Review total forecasted demand by school

### Example 3: Quarter Planning

**Goal**: Plan for Q1 2026

**Steps**:
1. Select aggregation level: **By Product**
2. Click: **Next 90 Days**
3. Click: **Apply Filters**
4. Sort by total quantity (highest first)
5. Identify top products for bulk ordering

### Example 4: Specific Event Planning

**Goal**: Prepare for Back-to-School period (Jan 1 - Feb 16, 2026)

**Steps**:
1. Select aggregation level: **By Product**
2. Click on **Start Date**: Select January 1, 2026
3. Click on **End Date**: Select February 16, 2026
4. Click: **Apply Filters**
5. Export or screenshot for planning meeting

---

## Aggregation Levels

### By Product
- **Best for**: Inventory management, purchasing decisions
- **Shows**: Individual products with size variations
- **Features**: Stock gap analysis, expandable variations

### By School
- **Best for**: School-specific planning, territory analysis
- **Shows**: Demand by school location
- **Features**: Product breakdown modal

### By Shop Location
- **Best for**: Retail store planning
- **Shows**: Demand by shop/branch
- **Features**: Location-based analysis

### By Category
- **Best for**: Category management, trend analysis
- **Shows**: Demand by product category
- **Features**: High-level overview

---

## Common Questions

### Q: Why are some sizes missing?

**A**: Only variations with at least 10 historical sales are forecasted. Low-volume sizes (e.g., 2XS, 4XL) may not appear if they have insufficient data for accurate forecasting.

### Q: What does "Cached" mean?

**A**: Your forecast was loaded from memory instead of recalculated. This makes it load instantly but may be up to 30 minutes old.

### Q: How often are forecasts updated?

**A**: Base forecasts are typically generated daily. Check with your admin for the exact schedule.

### Q: Can I export the forecast data?

**A**: Currently, you can:
- Take screenshots
- Copy from the table
- Use browser print function
- Future: Export to CSV/Excel (coming soon)

### Q: What's the difference between confidence lower/upper?

**A**: These represent the 80% confidence interval:
- **Confidence Lower**: 10% chance sales will be below this
- **Forecast**: Most likely value
- **Confidence Upper**: 10% chance sales will be above this

### Q: Why is my date range grayed out?

**A**: Either:
1. End date is before start date (invalid)
2. Range exceeds 365 days (too large)
3. Invalid date format

Fix the dates and try again.

---

## Troubleshooting

### Problem: "End date must be after start date" error

**Solution**: Make sure your end date is later than your start date.

### Problem: "Date range cannot exceed 365 days" error

**Solution**: Select a shorter date range (maximum 365 days).

### Problem: No data showing

**Possible causes**:
1. No forecasts generated yet (check with admin)
2. Selected date range has no data
3. Filter combination returns no results

**Solutions**:
1. Try "Next 30 Days" quick select
2. Change aggregation level
3. Contact support if issue persists

### Problem: Slow loading

**Solutions**:
1. Use quick select buttons (faster)
2. Select shorter date range
3. Clear browser cache
4. Wait for cache to build (second load is faster)

### Problem: Stock gaps seem incorrect

**Checks**:
1. Verify "Stock on Hand" is current
2. Check "Incoming Stock" matches POs
3. Confirm date range includes your planning period
4. Review forecast details for accuracy

---

## Tips & Tricks

### Tip 1: Planning Cycle Alignment

Align your date ranges with your business cycles:
- **Weekly planning**: Next 7 Days
- **Monthly planning**: This Month or Next 30 Days
- **Quarterly planning**: Next 90 Days

### Tip 2: Comparing Forecasts

To compare different time periods:
1. Note your first date range forecast
2. Change dates to second period
3. Compare totals and trends
4. Identify seasonal patterns

### Tip 3: Stock Gap Analysis

Focus on products with:
- Large negative gaps (urgent reorder)
- High forecasted demand (bulk order candidates)
- Low accuracy scores (review manually)

### Tip 4: Keyboard Shortcuts

- **Tab**: Move between date fields
- **Arrow keys**: Navigate calendar (when picker is open)
- **Enter**: Submit form (after selecting dates)
- **Esc**: Close calendar picker

### Tip 5: Mobile Usage

On mobile devices:
- Use quick select buttons (easier than date pickers)
- Rotate to landscape for better table view
- Tap product rows to expand variations

---

## Support

For questions or issues:
1. Check this guide first
2. Contact your system administrator
3. Reference the technical documentation: `DATE_RANGE_FORECASTING_IMPLEMENTATION.md`

---

## Quick Reference

| Action | Steps |
|--------|-------|
| Next 7 days forecast | Click "Next 7 Days" → Apply Filters |
| Next 30 days forecast | Click "Next 30 Days" → Apply Filters |
| Custom range | Set Start Date → Set End Date → Apply Filters |
| View by product | Select "By Product" level → Apply Filters |
| See product variations | Click on product row (expands sizes) |
| View daily breakdown | Click "Details" button |
| View forecast chart | Click "Chart" button |

---

**Last Updated**: March 5, 2026
**Version**: 1.0
**System**: SASPulse Date Range Forecasting
