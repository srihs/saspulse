"""
Forecast Utilities for 2-Year Rolling Forecast System

This module provides helper functions for generating 24-month rolling forecasts
that use forecasted values as baseline when actual sales data doesn't exist.
"""

from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from typing import Dict, Optional, Tuple, List
import statistics

from django.db import connection
from dashboard.models import SalesForecastBase


def get_or_create_baseline(product_code: str, year: int, month: int) -> Tuple[float, str]:
    """
    Get actual sales or fallback to forecasted values for baseline calculation

    This is the core function that enables 2-year rolling forecasts by using
    forecasted values when actual sales don't exist.

    Args:
        product_code: SKU code of the product
        year: Target year (e.g., 2027)
        month: Target month (1-12)

    Returns:
        Tuple of (baseline_value, source) where source is 'actual' or 'forecast'

    Example:
        baseline, source = get_or_create_baseline('SHIRT-001', 2027, 4)
        # Returns: (120.5, 'forecast') if no actual sales exist for April 2027
    """
    # Step 1: Try to get actual sales for this month/year
    actual_sales = get_actual_sales(product_code, year, month)

    if actual_sales is not None and actual_sales > 0:
        return actual_sales, 'actual'

    # Step 2: No actual sales - try to get forecast from previous year
    previous_year = year - 1
    previous_forecast = get_forecast_value(product_code, previous_year, month)

    if previous_forecast is not None and previous_forecast > 0:
        return previous_forecast, 'forecast'

    # Step 3: No previous forecast - use same month from last available historical year
    last_historical_sales = get_last_historical_sales_for_month(product_code, month)

    if last_historical_sales is not None and last_historical_sales > 0:
        return last_historical_sales, 'historical'

    # Step 4: No data at all - return 0
    return 0.0, 'none'


def get_actual_sales(product_code: str, year: int, month: int) -> Optional[float]:
    """
    Get actual sales for a specific product, year, and month

    Args:
        product_code: SKU code
        year: Year (e.g., 2026)
        month: Month (1-12)

    Returns:
        Total quantity sold in that month, or None if no sales
    """
    query = """
    SELECT SUM(li.qty) as total_qty
    FROM cin7_sync_salesorderlineitem li
    JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
    JOIN cin7_sync_product p ON p.id = li.product_id
    WHERE li.code = %s
      AND (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
      AND p.category_name NOT IN ('Shop', 'Store')
      AND so.stage = 'Dispatched'
      AND so.invoice_date IS NOT NULL
      AND YEAR(so.invoice_date) = %s
      AND MONTH(so.invoice_date) = %s
    """

    with connection.cursor() as cursor:
        cursor.execute(query, [product_code, year, month])
        result = cursor.fetchone()

        if result and result[0]:
            return float(result[0])

    return None


def get_forecast_value(product_code: str, year: int, month: int) -> Optional[float]:
    """
    Get forecasted value for a specific product, year, and month

    Args:
        product_code: SKU code
        year: Year (e.g., 2026)
        month: Month (1-12)

    Returns:
        Forecasted quantity for that month, or None if no forecast exists
    """
    month_key = f"{year}-{month:02d}"

    try:
        forecast = SalesForecastBase.objects.filter(
            entity_name=product_code,
            aggregation_level='product'
        ).order_by('-forecast_date').first()

        if forecast and forecast.monthly_breakdown:
            monthly_data = forecast.monthly_breakdown.get(month_key)
            if monthly_data:
                return float(monthly_data.get('quantity', 0))

    except SalesForecastBase.DoesNotExist:
        pass

    return None


def get_last_historical_sales_for_month(product_code: str, month: int) -> Optional[float]:
    """
    Get the most recent historical sales for a specific month (any year)

    Args:
        product_code: SKU code
        month: Month (1-12)

    Returns:
        Sales quantity from the most recent year this month had sales, or None
    """
    query = """
    SELECT SUM(li.qty) as total_qty, YEAR(so.invoice_date) as year
    FROM cin7_sync_salesorderlineitem li
    JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
    JOIN cin7_sync_product p ON p.id = li.product_id
    WHERE li.code = %s
      AND (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
      AND p.category_name NOT IN ('Shop', 'Store')
      AND so.stage = 'Dispatched'
      AND so.invoice_date IS NOT NULL
      AND MONTH(so.invoice_date) = %s
      AND so.invoice_date >= DATE_SUB(CURDATE(), INTERVAL 1095 DAY)
    GROUP BY YEAR(so.invoice_date)
    ORDER BY year DESC
    LIMIT 1
    """

    with connection.cursor() as cursor:
        cursor.execute(query, [product_code, month])
        result = cursor.fetchone()

        if result and result[0]:
            return float(result[0])

    return None


def calculate_seasonal_factors(product_code: str, years: int = 3) -> Dict[int, float]:
    """
    Calculate monthly seasonal adjustment factors based on historical patterns

    Args:
        product_code: SKU code
        years: Number of historical years to analyze (default: 3)

    Returns:
        Dictionary mapping month (1-12) to seasonal factor (multiplier)

    Example:
        {1: 1.5, 2: 1.4, 3: 0.8, ..., 12: 1.3}
        - 1.5 means January typically has 50% higher sales than average
        - 0.8 means March has 20% lower sales than average
    """
    # Get historical sales by month
    query = """
    SELECT
        MONTH(so.invoice_date) as month,
        SUM(li.qty) as quantity
    FROM cin7_sync_salesorderlineitem li
    JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
    JOIN cin7_sync_product p ON p.id = li.product_id
    WHERE li.code = %s
      AND (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
      AND p.category_name NOT IN ('Shop', 'Store')
      AND so.stage = 'Dispatched'
      AND so.invoice_date IS NOT NULL
      AND so.invoice_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
    GROUP BY MONTH(so.invoice_date)
    """

    monthly_totals = defaultdict(float)

    with connection.cursor() as cursor:
        cursor.execute(query, [product_code, 365 * years])
        rows = cursor.fetchall()

        for row in rows:
            month, quantity = row
            monthly_totals[month] = float(quantity)

    # Calculate average monthly sales
    if not monthly_totals:
        # No data - return neutral factors
        return {m: 1.0 for m in range(1, 13)}

    total_sales = sum(monthly_totals.values())
    avg_monthly_sales = total_sales / 12

    # Calculate seasonal factors
    seasonal_factors = {}
    for month in range(1, 13):
        month_sales = monthly_totals.get(month, 0)

        if avg_monthly_sales > 0:
            # Factor = (month sales / average monthly sales)
            factor = month_sales / avg_monthly_sales
        else:
            factor = 1.0

        seasonal_factors[month] = factor

    return seasonal_factors


def calculate_growth_trend(product_code: str, years: int = 3) -> float:
    """
    Calculate year-over-year growth rate

    Args:
        product_code: SKU code
        years: Number of years to analyze (default: 3)

    Returns:
        Annual growth rate as a decimal (e.g., 0.15 = 15% growth)
    """
    query = """
    SELECT
        YEAR(so.invoice_date) as year,
        SUM(li.qty) as quantity
    FROM cin7_sync_salesorderlineitem li
    JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
    JOIN cin7_sync_product p ON p.id = li.product_id
    WHERE li.code = %s
      AND (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
      AND p.category_name NOT IN ('Shop', 'Store')
      AND so.stage = 'Dispatched'
      AND so.invoice_date IS NOT NULL
      AND so.invoice_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
    GROUP BY YEAR(so.invoice_date)
    ORDER BY year
    """

    annual_totals = {}

    with connection.cursor() as cursor:
        cursor.execute(query, [product_code, 365 * years])
        rows = cursor.fetchall()

        for row in rows:
            year, quantity = row
            annual_totals[year] = float(quantity)

    if len(annual_totals) < 2:
        # Not enough data for growth calculation
        return 0.0

    # Calculate average year-over-year growth
    years_list = sorted(annual_totals.keys())
    first_year_sales = annual_totals[years_list[0]]
    last_year_sales = annual_totals[years_list[-1]]

    if first_year_sales > 0:
        total_growth = (last_year_sales - first_year_sales) / first_year_sales
        num_years = len(years_list) - 1
        annual_growth = total_growth / num_years if num_years > 0 else 0.0
    else:
        annual_growth = 0.0

    # Cap growth at +/-50% to avoid extreme forecasts
    annual_growth = max(-0.5, min(0.5, annual_growth))

    return annual_growth


def generate_24month_forecast(
    product_code: str,
    school: Optional[str] = None,
    shop: Optional[str] = None,
    years_history: int = 3
) -> Dict[str, Dict]:
    """
    Generate 24-month rolling forecast using historical data and forecasted baselines

    This is the main function that implements the 2-year rolling forecast logic:
    1. For months with actual sales: use actual data
    2. For future months (no sales yet): use previous year's forecast as baseline
    3. Apply seasonal adjustments
    4. Apply growth trends

    Args:
        product_code: SKU code
        school: School name (sub_category) - optional
        shop: Shop name (category_name) - optional
        years_history: Number of historical years to use (default: 3)

    Returns:
        Dictionary with monthly forecasts for next 24 months
        {
            '2026-04': {'quantity': 120.5, 'baseline': 100, 'source': 'forecast', ...},
            '2026-05': {'quantity': 135.2, 'baseline': 115, 'source': 'forecast', ...},
            ...
        }
    """
    # Calculate seasonal factors and growth trend
    seasonal_factors = calculate_seasonal_factors(product_code, years_history)
    growth_rate = calculate_growth_trend(product_code, years_history)

    # Generate forecasts for next 24 months
    forecasts = {}
    today = date.today()

    for i in range(24):
        target_date = today + relativedelta(months=i + 1)
        target_year = target_date.year
        target_month = target_date.month
        month_key = f"{target_year}-{target_month:02d}"

        # Get baseline (actual, forecast, or historical)
        baseline, source = get_or_create_baseline(product_code, target_year, target_month)

        # Apply seasonal adjustment
        seasonal_factor = seasonal_factors.get(target_month, 1.0)
        seasonally_adjusted = baseline * seasonal_factor

        # Apply growth trend (compound growth over time)
        years_ahead = (target_date.year - today.year) + (target_date.month - today.month) / 12
        growth_adjusted = seasonally_adjusted * (1 + growth_rate) ** years_ahead

        # Ensure non-negative
        final_forecast = max(0, growth_adjusted)

        forecasts[month_key] = {
            'quantity': round(final_forecast, 1),
            'baseline': round(baseline, 1),
            'baseline_source': source,
            'seasonal_factor': round(seasonal_factor, 2),
            'growth_rate': round(growth_rate, 2),
            'confidence': calculate_forecast_confidence(source, target_date, today)
        }

    return forecasts


def calculate_forecast_confidence(source: str, target_date: date, forecast_date: date) -> str:
    """
    Calculate confidence level for a forecast

    Args:
        source: Source of baseline ('actual', 'forecast', 'historical', 'none')
        target_date: Date being forecasted
        forecast_date: Date forecast was generated

    Returns:
        Confidence level: 'high', 'medium', 'low'
    """
    # Calculate months ahead
    months_ahead = (target_date.year - forecast_date.year) * 12 + (target_date.month - forecast_date.month)

    if source == 'actual':
        return 'high'
    elif source == 'forecast':
        # Forecast-based forecasts have declining confidence over time
        if months_ahead <= 6:
            return 'high'
        elif months_ahead <= 12:
            return 'medium'
        else:
            return 'low'
    elif source == 'historical':
        # Historical baselines are medium confidence
        if months_ahead <= 6:
            return 'medium'
        else:
            return 'low'
    else:
        # No baseline data - low confidence
        return 'low'


def get_forecast_summary(forecasts: Dict[str, Dict]) -> Dict:
    """
    Generate summary statistics for a 24-month forecast

    Args:
        forecasts: Dictionary of monthly forecasts

    Returns:
        Summary statistics dictionary
    """
    if not forecasts:
        return {
            'total_24month': 0,
            'avg_monthly': 0,
            'min_month': 0,
            'max_month': 0,
            'peak_months': [],
            'low_months': [],
            'confidence_distribution': {}
        }

    quantities = [f['quantity'] for f in forecasts.values()]
    confidences = [f['confidence'] for f in forecasts.values()]

    # Find peak and low months
    sorted_months = sorted(forecasts.items(), key=lambda x: x[1]['quantity'], reverse=True)
    peak_months = [m[0] for m in sorted_months[:3]]  # Top 3
    low_months = [m[0] for m in sorted_months[-3:]]  # Bottom 3

    # Confidence distribution
    confidence_dist = {
        'high': confidences.count('high'),
        'medium': confidences.count('medium'),
        'low': confidences.count('low')
    }

    return {
        'total_24month': round(sum(quantities), 1),
        'avg_monthly': round(statistics.mean(quantities), 1),
        'min_month': round(min(quantities), 1),
        'max_month': round(max(quantities), 1),
        'peak_months': peak_months,
        'low_months': low_months,
        'confidence_distribution': confidence_dist
    }
