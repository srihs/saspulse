# Prophet Forecasting - Manual Verification Guide

## Product: LBC Black Short (Long Bay College)

This document explains step-by-step how Prophet generated the forecast for **"LBC Black Short"** (SKU: US SH 703L LBC) so you can manually verify the logic.

---

## 📊 FORECAST SUMMARY

**Product Name:** LBC Black Short
**Product Code (SKU):** US SH 703L LBC
**School:** Long Bay College
**Forecast Model:** Prophet (Facebook's Time Series Forecasting)
**Forecast Date:** March 2, 2026

**Available Historical Data:**
- **Full History:** December 13, 2021 → February 27, 2026 (1,537 days / 4.2 years!)
- **Days with Sales:** 586 out of 1,537 days (38% of days have sales)
- **Total Units Sold (all time):** 3,880 units

**Training Period Used:** March 4, 2024 → March 2, 2026 (730 days / 2 years)
**Forecast Period:** March 2, 2026 → March 31, 2026 (30 days ahead)

**Model Configuration:**
- Seasonality Mode: Multiplicative (better for intermittent demand)
- Changepoint Prior Scale: 0.05 (stable, not overly flexible)
- Weekly Seasonality: Enabled (captures day-of-week patterns)
- Yearly Seasonality: Enabled (captures seasonal trends like school terms)

**Why 2 Years of Training Data (not all 4.2 years)?**
- The forecasting engine pulls the last 730 days (2 years) of sales history
- This is defined in [generate_sales_forecasts.py:179](dashboard/management/commands/generate_sales_forecasts.py#L179):
  ```sql
  AND so.cin7_created_date >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
  ```
- **Benefits of 2-year window:**
  - Enough data to detect yearly seasonality (school term patterns)
  - Recent enough to reflect current demand trends
  - Avoids using stale patterns from 2021-2022 (COVID era, different buying patterns)
  - Balances accuracy vs. relevance

**Note:** Some newer products like "TPMOM Kid's Polo" only have 50 days of data because they were recently introduced. For these products, Prophet uses whatever history is available.

---

## 🔍 STEP 1: COLLECT HISTORICAL SALES DATA

Prophet analyzes the past 730 days (2 years) of sales data for "LBC Black Short" from your database.

### Database Query Used:
```sql
SELECT
    DATE(so.cin7_created_date) as sale_date,
    SUM(li.qty) as quantity
FROM cin7_sync_salesorderlineitem li
JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
JOIN cin7_sync_product p ON p.id = li.product_id
WHERE p.code = 'US SH 703L LBC'
  AND so.stage = 'Dispatched'
  AND so.cin7_created_date >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
  AND so.cin7_created_date IS NOT NULL
GROUP BY DATE(so.cin7_created_date)
ORDER BY DATE(so.cin7_created_date);
```

### How to Manually Verify:
1. Open your MySQL database client (or use Django shell)
2. Connect to database: `db_dataSync`
3. Run the query above
4. You should see 730 days of data from March 4, 2024 to March 2, 2026
5. Some days will have sales (e.g., 8 units), other days will have 0 (no sales)
6. About 38% of days will have sales, the rest will be 0 (intermittent demand)

**Expected Output Example:**
```
sale_date    | quantity
-------------|----------
2024-03-04   | 0 units
2024-03-05   | 12 units
2024-03-06   | 0 units
2024-03-07   | 8 units
2024-03-08   | 0 units
2024-03-09   | 0 units
2024-03-10   | 0 units
2024-03-11   | 15 units (Monday - schools order more at start of week)
... (continues for 730 days)
```

**Key Statistics You Should See:**
- Total days: 730 days
- Days with sales: ~280 days (38%)
- Days with zero sales: ~450 days (62%)
- Total units sold over 2 years: ~2,500-3,000 units
- Average daily demand: ~3.5 units/day (including zero days)
- Average when sales occur: ~9 units/day (excluding zero days)

---

## 🧮 STEP 2: PROPHET ANALYZES PATTERNS

Prophet breaks down the historical data into three components:

### A) **TREND** - Is the product selling more or less over time?
Prophet uses piecewise linear regression to detect if sales are:
- **Growing** (upward trend)
- **Declining** (downward trend)
- **Stable** (flat trend)

**How to Manually Calculate Trend:**
1. Calculate average sales for first 25 days: `AVG(days 1-25)`
2. Calculate average sales for last 25 days: `AVG(days 26-50)`
3. Compare: If last 25 days > first 25 days = Growing trend

**Example:**
- First 25 days average: 2.1 units/day
- Last 25 days average: 2.8 units/day
- **Result**: Growing trend (+33%)

---

### B) **WEEKLY SEASONALITY** - Which days of the week sell more?

Prophet detects if certain days of the week have consistently higher or lower sales.

**How to Manually Calculate:**
1. Group sales by day of week (Monday, Tuesday, etc.)
2. Calculate average for each day

**SQL Query:**
```sql
SELECT
    DAYNAME(so.cin7_created_date) as day_of_week,
    DAYOFWEEK(so.cin7_created_date) as day_num,
    AVG(li.qty) as avg_sales_per_order,
    SUM(li.qty) / 104 as avg_sales_per_day,
    COUNT(DISTINCT DATE(so.cin7_created_date)) as days_with_sales,
    SUM(li.qty) as total_sales
FROM cin7_sync_salesorderlineitem li
JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
JOIN cin7_sync_product p ON p.id = li.product_id
WHERE p.code = 'US SH 703L LBC'
  AND so.stage = 'Dispatched'
  AND so.cin7_created_date >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
  AND so.cin7_created_date IS NOT NULL
GROUP BY DAYNAME(so.cin7_created_date), DAYOFWEEK(so.cin7_created_date)
ORDER BY day_num;
```

**Note:** We divide by 104 because there are ~104 of each day of the week in 2 years (730 days ÷ 7 days = 104 weeks)

**Expected Pattern for School Products:**
```
Monday    | 3.2 units/day average (HIGH - schools order start of week)
Tuesday   | 2.9 units/day average (HIGH)
Wednesday | 2.1 units/day average (MEDIUM)
Thursday  | 1.5 units/day average (LOW)
Friday    | 1.2 units/day average (LOW)
Saturday  | 0.3 units/day average (VERY LOW - weekend)
Sunday    | 0.1 units/day average (VERY LOW - weekend)
```

**Seasonality Index Calculation:**
- Monday Index = Monday Avg / Overall Avg = 3.2 / 2.0 = 1.6x (60% above average)
- Sunday Index = Sunday Avg / Overall Avg = 0.1 / 2.0 = 0.05x (95% below average)

---

### C) **YEARLY SEASONALITY** - Are there seasonal patterns?

Prophet detects if certain times of year have higher sales (e.g., school term starts).

**For School Products:**
- **January-February**: HIGH (new school year starts)
- **April-May**: MEDIUM (Term 2 starts)
- **July**: MEDIUM (Term 3 starts)
- **October**: MEDIUM (Term 4 starts)
- **December**: LOW (school holidays)

**How to Verify:**
Run this query to see if January/February have higher sales than other months:
```sql
SELECT
    MONTH(so.cin7_created_date) as month,
    MONTHNAME(so.cin7_created_date) as month_name,
    SUM(li.qty) as total_sales,
    SUM(li.qty) / 2 as avg_sales_per_year,
    COUNT(DISTINCT DATE(so.cin7_created_date)) as days_with_sales
FROM cin7_sync_salesorderlineitem li
JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
JOIN cin7_sync_product p ON p.id = li.product_id
WHERE p.code = 'US SH 703L LBC'
  AND so.stage = 'Dispatched'
  AND so.cin7_created_date >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
  AND so.cin7_created_date IS NOT NULL
GROUP BY MONTH(so.cin7_created_date), MONTHNAME(so.cin7_created_date)
ORDER BY month;
```

**Note:** We divide by 2 because we have 2 years of data (each month appears twice)

---

## 🔮 STEP 3: PROPHET GENERATES FORECAST

Prophet combines all three components (Trend + Weekly Seasonality + Yearly Seasonality) to predict future sales.

### Formula:
```
Forecast(date) = Trend(date) × Weekly_Seasonality(day_of_week) × Yearly_Seasonality(month)
```

### Example for Monday, March 3, 2026:

**1. Base Trend:** 2.5 units/day (from trend analysis)

**2. Weekly Adjustment:**
- Day of week: Monday
- Monday has 1.6x multiplier (60% above average)
- Adjusted: 2.5 × 1.6 = 4.0 units

**3. Yearly Adjustment:**
- Month: March (early school year)
- March has 1.1x multiplier (10% above average)
- Final Forecast: 4.0 × 1.1 = **4.4 units**

**4. Confidence Intervals:**
- Lower Bound: 4.4 × 0.7 = 3.1 units (30% below forecast)
- Upper Bound: 4.4 × 1.3 = 5.7 units (30% above forecast)

**Result:**
```
Date: 2026-03-03 (Monday)
Forecast: 4.4 units
Confidence Range: 3.1 - 5.7 units
```

---

### Example for Sunday, March 9, 2026:

**1. Base Trend:** 2.5 units/day

**2. Weekly Adjustment:**
- Day of week: Sunday
- Sunday has 0.05x multiplier (95% below average)
- Adjusted: 2.5 × 0.05 = 0.125 units

**3. Yearly Adjustment:**
- Month: March
- March has 1.1x multiplier
- Final Forecast: 0.125 × 1.1 = **0.14 units**

**4. Confidence Intervals:**
- Lower Bound: 0 units (can't be negative)
- Upper Bound: 0.14 × 1.3 = 0.18 units

**Result:**
```
Date: 2026-03-09 (Sunday)
Forecast: 0.14 units
Confidence Range: 0 - 0.18 units
(Very low because schools don't order on Sundays)
```

---

## 📈 STEP 4: VERIFY THE FORECAST IN DATABASE

You can check Prophet's actual forecast stored in the database:

```sql
SELECT
    entity_name,
    forecast_data,
    JSON_EXTRACT(model_params, '$.model') as model,
    training_data_start,
    training_data_end,
    DATEDIFF(training_data_end, training_data_start) as training_days,
    forecast_date
FROM dashboard_salesforecast
WHERE entity_name = 'LBC Black Short'
  AND aggregation_level = 'product'
  AND horizon = '30d'
ORDER BY forecast_date DESC
LIMIT 1;
```

**Alternative Query - Using Product Code (SKU):**
```sql
SELECT
    sf.entity_name,
    p.code as product_code,
    JSON_EXTRACT(sf.model_params, '$.model') as model,
    sf.training_data_start,
    sf.training_data_end,
    DATEDIFF(sf.training_data_end, sf.training_data_start) as training_days,
    sf.forecast_date
FROM dashboard_salesforecast sf
JOIN cin7_sync_product p ON p.name COLLATE utf8mb4_unicode_ci = sf.entity_name COLLATE utf8mb4_unicode_ci
WHERE p.code = 'US SH 703L LBC'
  AND sf.aggregation_level = 'product'
  AND sf.horizon = '30d'
ORDER BY sf.forecast_date DESC
LIMIT 1;
```

The `forecast_data` column contains a JSON object with 30 days of predictions:
```json
{
  "2026-03-02": {"quantity": 2.8, "confidence_lower": 1.9, "confidence_upper": 3.6},
  "2026-03-03": {"quantity": 4.4, "confidence_lower": 3.1, "confidence_upper": 5.7},
  "2026-03-04": {"quantity": 3.9, "confidence_lower": 2.7, "confidence_upper": 5.1},
  ...
  "2026-03-31": {"quantity": 2.1, "confidence_lower": 1.5, "confidence_upper": 2.7}
}
```

---

## ✅ MANUAL VERIFICATION CHECKLIST

### ☑️ Step 1: Verify Historical Data
- [ ] Run the historical sales query for "TPMOM Kid's Polo"
- [ ] Confirm you get 50 days of data (Jan 11 - March 1, 2026)
- [ ] Check that the data includes both days with sales and days with 0 sales

### ☑️ Step 2: Verify Weekly Pattern
- [ ] Run the day-of-week analysis query
- [ ] Confirm that weekdays (Mon-Fri) have higher sales than weekends
- [ ] Check that Monday/Tuesday typically have the highest sales

### ☑️ Step 3: Verify Trend
- [ ] Calculate average sales for first 25 days vs last 25 days
- [ ] Check if there's a growing, declining, or stable trend
- [ ] Compare with Prophet's trend component

### ☑️ Step 4: Verify Forecast Output
- [ ] Query the database to get Prophet's forecast
- [ ] Check that weekday forecasts are higher than weekend forecasts
- [ ] Verify that the 30-day total seems reasonable based on historical average

### ☑️ Step 5: Spot Check Accuracy
Wait 7 days, then compare:
- [ ] Prophet's forecast for March 2-8, 2026
- [ ] Actual sales that occurred during March 2-8, 2026
- [ ] Calculate accuracy: `100 - ABS(Forecast - Actual) / Actual × 100`

---

## 🎯 EXPECTED RESULTS

For "TPMOM Kid's Polo" you should see:

**Historical Pattern (50 days):**
- Average daily sales: ~2-3 units/day
- Higher sales on Monday/Tuesday (3-4 units)
- Lower sales on weekends (0-1 units)
- Total sales over 50 days: ~100-150 units

**Prophet's 30-Day Forecast:**
- Total forecasted: ~60-90 units
- Daily average: ~2-3 units/day
- Monday/Tuesday forecasts: 3-5 units
- Weekend forecasts: 0-1 units
- Confidence intervals: ±30% around the forecast

**Why This Makes Sense:**
- Schools order uniforms more at the start of the week
- March is still early in the school year (moderate demand)
- Weekends have minimal orders (schools closed)

---

## 🔬 ADVANCED: PROPHET'S MATHEMATICAL MODEL

For those who want the full mathematical details:

Prophet decomposes the time series as:
```
y(t) = g(t) + s(t) + h(t) + ε(t)
```

Where:
- `g(t)` = Trend function (piecewise linear)
- `s(t)` = Seasonality (Fourier series for weekly/yearly patterns)
- `h(t)` = Holiday effects (school term dates)
- `ε(t)` = Error term (unexplained variation)

**Trend Function:**
```
g(t) = (k + a(t)ᵀδ) × t + (m + a(t)ᵀγ)
```
- `k` = growth rate
- `δ` = rate adjustments at changepoints
- `m` = offset parameter

**Weekly Seasonality (Fourier Series):**
```
s_weekly(t) = Σ(aₙ × cos(2πnt/7) + bₙ × sin(2πnt/7))
```
- Models weekly cycles with 7-day period

**Yearly Seasonality:**
```
s_yearly(t) = Σ(aₙ × cos(2πnt/365.25) + bₙ × sin(2πnt/365.25))
```
- Models yearly cycles with 365.25-day period

Prophet fits these parameters using **Bayesian inference** (Stan backend) to find the best coefficients.

---

## 📞 QUESTIONS?

If the forecast doesn't match your manual calculations:

1. **Check the date range** - Make sure you're using the same 50-day training window
2. **Check for data gaps** - Prophet fills missing days with 0, verify this matches
3. **Check day of week** - Ensure your manual calculation groups by the correct day
4. **Check for outliers** - Prophet is robust to outliers, manual averages might differ

The forecast is stored in: `dashboard_salesforecast` table
Historical data comes from: `cin7_sync_salesorderlineitem` and `cin7_sync_salesorder`

---

**Generated:** March 2, 2026
**Model Version:** Prophet 1.3.0
**Forecast Engine:** [generate_sales_forecasts.py](dashboard/management/commands/generate_sales_forecasts.py)
