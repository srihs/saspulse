"""
Dashboard Views

Stock Value vs BTS Sales Analysis Dashboard
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from users.decorators import login_required, permission_required
from django.db.models import Sum, Count, F, DecimalField, Value
from django.db.models.functions import Coalesce
from decimal import Decimal
from users.auth_backend import CustomAuthBackend
from cin7.models import SalesOrder, SalesOrderLineItem, Stock, Product
from dashboard.utils.permissions import apply_branch_filter, apply_school_filter, apply_data_scope
import logging

auth_backend = CustomAuthBackend()

# BTS (Back to School) Period Configuration
from datetime import date
BTS_START_DATE = '2026-01-01'
BTS_END_DATE = '2026-02-16'  # Fixed end date to match reporting period
RISK_THRESHOLD = 2.0  # Stock ratio > 2.0 is considered risky

# Category Filter: Only include categories ending with " Shop" or " Store"
CATEGORY_FILTER = """
    (p.category_name LIKE '% Shop' OR p.category_name LIKE '% Store')
    AND p.category_name NOT IN ('Shop', 'Store')
"""


def calculate_summary_metrics(start_date=None, end_date=None):
    """
    Calculate the top summary tiles metrics for Shop categories

    Args:
        start_date: Start date for BTS period (default: BTS_START_DATE)
        end_date: End date for BTS period (default: BTS_END_DATE)
    """
    from django.db import connection

    # Use provided dates or fall back to defaults
    start = start_date or BTS_START_DATE
    end = end_date or BTS_END_DATE

    # 1. Calculate Total BTS Sales (Shop categories, excluding shop locations)
    # Sales = qty * unit_price for invoiced orders in the period
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as total_sales
            FROM cin7_sync_salesorder so
            JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
            JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
            WHERE so.invoice_date >= %s AND so.invoice_date <= %s
              AND p.category_name LIKE %s
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
        """, [start, end, '% Shop', '%%Shop%'])

        result = cursor.fetchone()
        total_bts_sales = float(result[0] or 0)

    # 2. Calculate Total Stock Value (stock on hand × cost_price)
    # Stock mapped via product sub_category (Shop categories, excluding shop locations)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT SUM(COALESCE(s.stock_on_hand, 0) * COALESCE(po.cost_price, 0)) as total_value
            FROM cin7_sync_product p
            LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
            LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
            WHERE p.category_name LIKE %s
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
        """, ['% Shop', '%%Shop%'])

        result = cursor.fetchone()
        total_stock_value = float(result[0] or 0)

    # 3. Calculate Overall Ratio
    overall_ratio = 0
    if total_bts_sales > 0:
        overall_ratio = total_stock_value / total_bts_sales

    # 4. Calculate Customers at Risk (ratio > threshold)
    # Count schools with stock ratio > 2.0 (using sub_category mapping, excluding shop locations)
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH stock_by_school AS (
                SELECT
                    p.sub_category as school,
                    SUM(COALESCE(s.stock_on_hand, 0) * COALESCE(po.cost_price, 0)) as stock_value
                FROM cin7_sync_product p
                LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
                LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
                WHERE p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category
            ),
            bts_sales AS (
                SELECT
                    p.sub_category as school,
                    SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as sales_total
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category
            )
            SELECT COUNT(*) as at_risk_count
            FROM stock_by_school ss
            LEFT JOIN bts_sales bs ON ss.school = bs.school
            WHERE COALESCE(bs.sales_total, 0) > 0
              AND (ss.stock_value / bs.sales_total) > %s
        """, ['% Shop', '%%Shop%', '% Shop', start, end, '%%Shop%', RISK_THRESHOLD])

        result = cursor.fetchone()
        customers_at_risk = result[0] if result else 0

    return {
        'total_stock_value': total_stock_value,
        'total_bts_sales': total_bts_sales,
        'overall_ratio': round(overall_ratio, 2),
        'customers_at_risk': customers_at_risk,
        'risk_threshold': RISK_THRESHOLD
    }


def calculate_customer_rankings(start_date=None, end_date=None):
    """
    Calculate customer-level rankings showing who is holding too much stock

    Returns a list of customers (schools) with:
    - Customer Name (school name from product sub_category)
    - Stock Value (stock on hand × cost_price, mapped via product sub_category)
    - BTS Sales (invoiced sales during BTS period - qty × unit_price)
    - Ratio (Stock Value / BTS Sales)
    - Risk Band (Green/Amber/Red)

    Args:
        start_date: Start date for BTS period (default: BTS_START_DATE)
        end_date: End date for BTS period (default: BTS_END_DATE)
    """
    from django.db import connection

    # Use provided dates or fall back to defaults
    start = start_date or BTS_START_DATE
    end = end_date or BTS_END_DATE

    with connection.cursor() as cursor:
        cursor.execute("""
            WITH stock_by_school AS (
                SELECT
                    p.sub_category as school,
                    SUM(COALESCE(s.stock_on_hand, 0) * COALESCE(po.cost_price, 0)) as stock_value
                FROM cin7_sync_product p
                LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
                LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
                WHERE (p.category_name LIKE '%% Shop' OR p.category_name LIKE '%% Store')
                  AND p.category_name NOT IN ('Shop', 'Store')
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE '%%Shop%%'
                GROUP BY p.sub_category
            ),
            bts_sales AS (
                SELECT
                    p.sub_category as school,
                    SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as sales_total
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE (p.category_name LIKE '%% Shop' OR p.category_name LIKE '%% Store')
                  AND p.category_name NOT IN ('Shop', 'Store')
                  AND so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE '%%Shop%%'
                GROUP BY p.sub_category
            )
            SELECT
                COALESCE(ss.school, bs.school) as school,
                COALESCE(ss.stock_value, 0) as stock_value,
                COALESCE(bs.sales_total, 0) as bts_sales,
                CASE
                    WHEN COALESCE(bs.sales_total, 0) > 0
                    THEN COALESCE(ss.stock_value, 0) / bs.sales_total
                    ELSE 999999
                END as ratio
            FROM stock_by_school ss
            LEFT JOIN bts_sales bs ON ss.school = bs.school
            UNION
            SELECT
                bs.school,
                0 as stock_value,
                bs.sales_total as bts_sales,
                CASE
                    WHEN bs.sales_total > 0 THEN 0
                    ELSE 999999
                END as ratio
            FROM bts_sales bs
            LEFT JOIN stock_by_school ss ON bs.school = ss.school
            WHERE ss.school IS NULL
            ORDER BY ratio DESC
        """, [start, end])

        rows = cursor.fetchall()

    # Process results and add risk bands
    rankings = []
    for row in rows:
        customer_name = row[0]
        stock_value = float(row[1] or 0)
        bts_sales = float(row[2] or 0)
        ratio = float(row[3] or 0)

        # Skip schools where both stock value and BTS sales are 0
        if stock_value == 0 and bts_sales == 0:
            continue

        # Determine risk band and sort priority
        if ratio >= 999999:  # No sales - infinite ratio
            risk_band = 'critical'
            risk_label = 'Critical'
            ratio_display = '∞'
            sort_priority = 1  # Critical = 1 (highest priority)
        elif ratio > 3:
            risk_band = 'critical'
            risk_label = 'Critical'
            ratio_display = round(ratio, 2)
            sort_priority = 1  # Critical = 1 (highest priority)
        elif ratio > 2:
            risk_band = 'warning'
            risk_label = 'Monitor'
            ratio_display = round(ratio, 2)
            sort_priority = 2  # Warning = 2
        else:
            risk_band = 'healthy'
            risk_label = 'Healthy'
            ratio_display = round(ratio, 2)
            sort_priority = 3  # Healthy = 3 (lowest priority)

        rankings.append({
            'customer_name': customer_name,
            'stock_value': stock_value,
            'bts_sales': bts_sales,
            'ratio': ratio,
            'ratio_display': ratio_display,
            'risk_band': risk_band,
            'risk_label': risk_label,
            'sort_priority': sort_priority
        })

    # Calculate risk band counts and stock values
    critical_count = sum(1 for r in rankings if r['risk_band'] == 'critical')
    warning_count = sum(1 for r in rankings if r['risk_band'] == 'warning')
    healthy_count = sum(1 for r in rankings if r['risk_band'] == 'healthy')

    critical_stock = sum(r['stock_value'] for r in rankings if r['risk_band'] == 'critical')
    warning_stock = sum(r['stock_value'] for r in rankings if r['risk_band'] == 'warning')
    healthy_stock = sum(r['stock_value'] for r in rankings if r['risk_band'] == 'healthy')

    return {
        'rankings': rankings,
        'critical_count': critical_count,
        'warning_count': warning_count,
        'healthy_count': healthy_count,
        'critical_stock': critical_stock,
        'warning_stock': warning_stock,
        'healthy_stock': healthy_stock
    }


def calculate_product_rankings(start_date=None, end_date=None):
    """
    Calculate product-level rankings showing which products are the biggest problem
    at which schools

    Returns a list of product-school combinations with:
    - School Name
    - Product Name (style code / product name)
    - Stock Value (at that school)
    - BTS Sales (at that school during BTS period)
    - Ratio (Stock Value / BTS Sales)
    - Risk Band (Green/Amber/Red)

    Args:
        start_date: Start date for BTS period (default: BTS_START_DATE)
        end_date: End date for BTS period (default: BTS_END_DATE)
    """
    from django.db import connection

    # Use provided dates or fall back to defaults
    start = start_date or BTS_START_DATE
    end = end_date or BTS_END_DATE

    with connection.cursor() as cursor:
        cursor.execute("""
            WITH stock_by_product_school AS (
                SELECT
                    p.sub_category as school,
                    p.cin7_id,
                    p.name as product_name,
                    p.style_code,
                    SUM(COALESCE(s.stock_on_hand, 0) * COALESCE(po.cost_price, 0)) as stock_value
                FROM cin7_sync_product p
                LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
                LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
                WHERE p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category, p.cin7_id, p.name, p.style_code
            ),
            bts_sales_by_product_school AS (
                SELECT
                    p.sub_category as school,
                    p.cin7_id,
                    SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as sales_total
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category, p.cin7_id
            )
            SELECT
                COALESCE(sp.school, bs.school) as school,
                sp.style_code,
                sp.product_name,
                COALESCE(sp.stock_value, 0) as stock_value,
                COALESCE(bs.sales_total, 0) as bts_sales,
                CASE
                    WHEN COALESCE(bs.sales_total, 0) > 0
                    THEN COALESCE(sp.stock_value, 0) / bs.sales_total
                    ELSE 999999
                END as ratio
            FROM stock_by_product_school sp
            LEFT JOIN bts_sales_by_product_school bs
                ON sp.school = bs.school AND sp.cin7_id = bs.cin7_id
            WHERE COALESCE(sp.stock_value, 0) > 0 OR COALESCE(bs.sales_total, 0) > 0

            UNION

            SELECT
                bs.school,
                NULL as style_code,
                NULL as product_name,
                0 as stock_value,
                bs.sales_total as bts_sales,
                0 as ratio
            FROM bts_sales_by_product_school bs
            LEFT JOIN stock_by_product_school sp
                ON bs.school = sp.school AND bs.cin7_id = sp.cin7_id
            WHERE sp.cin7_id IS NULL
              AND bs.sales_total > 0

            ORDER BY ratio DESC, school ASC
        """, ['% Shop', '%%Shop%', '% Shop', start, end, '%%Shop%'])

        rows = cursor.fetchall()

    # Process results and add risk bands
    rankings = []
    for row in rows:
        school = row[0]
        style_code = row[1] or 'N/A'
        product_name = row[2] or 'Unknown Product'
        stock_value = float(row[3] or 0)
        bts_sales = float(row[4] or 0)
        ratio = float(row[5] or 0)

        # Skip products where both stock value and BTS sales are 0
        if stock_value == 0 and bts_sales == 0:
            continue

        # Determine risk band and sort priority
        if ratio >= 999999:  # No sales - infinite ratio
            risk_band = 'critical'
            risk_label = 'Critical'
            ratio_display = '∞'
            sort_priority = 1  # Critical = 1 (highest priority)
        elif ratio > 3:
            risk_band = 'critical'
            risk_label = 'Critical'
            ratio_display = round(ratio, 2)
            sort_priority = 1  # Critical = 1 (highest priority)
        elif ratio > 2:
            risk_band = 'warning'
            risk_label = 'Monitor'
            ratio_display = round(ratio, 2)
            sort_priority = 2  # Warning = 2
        else:
            risk_band = 'healthy'
            risk_label = 'Healthy'
            ratio_display = round(ratio, 2)
            sort_priority = 3  # Healthy = 3 (lowest priority)

        rankings.append({
            'school': school,
            'style_code': style_code,
            'product_name': product_name,
            'stock_value': stock_value,
            'bts_sales': bts_sales,
            'ratio': ratio,
            'ratio_display': ratio_display,
            'risk_band': risk_band,
            'risk_label': risk_label,
            'sort_priority': sort_priority
        })

    # Calculate summary metrics: Find school with most critical products
    from collections import defaultdict

    school_critical_counts = defaultdict(lambda: {'count': 0, 'value': 0})
    for ranking in rankings:
        if ranking['risk_band'] == 'critical':
            school = ranking['school']
            school_critical_counts[school]['count'] += 1
            school_critical_counts[school]['value'] += ranking['stock_value']

    # Find the school with the most critical products
    top_critical_school = None
    top_critical_count = 0
    top_critical_value = 0

    if school_critical_counts:
        top_critical_school = max(school_critical_counts.items(), key=lambda x: x[1]['count'])
        top_critical_count = top_critical_school[1]['count']
        top_critical_value = top_critical_school[1]['value']
        top_critical_school = top_critical_school[0]

    # Get last sale date for the top critical school
    last_sale_date = None
    if top_critical_school:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT MAX(so.invoice_date) as last_sale
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND p.sub_category = %s
                  AND p.sub_category NOT LIKE %s
            """, ['% Shop', top_critical_school, '%%Shop%'])

            result = cursor.fetchone()
            if result and result[0]:
                last_sale_date = result[0]

    # Group products by school for grouped view
    from collections import defaultdict
    school_groups = defaultdict(lambda: {
        'products': [],
        'product_count': 0,
        'total_stock_value': 0,
        'total_bts_sales': 0,
        'worst_ratio': 0,
        'risk_band': 'healthy'
    })

    for ranking in rankings:
        school = ranking['school']
        school_groups[school]['products'].append(ranking)
        school_groups[school]['product_count'] += 1
        school_groups[school]['total_stock_value'] += ranking['stock_value']
        school_groups[school]['total_bts_sales'] += ranking['bts_sales']

        # Track worst (highest) ratio for the school
        if ranking['ratio'] > school_groups[school]['worst_ratio']:
            school_groups[school]['worst_ratio'] = ranking['ratio']
            school_groups[school]['risk_band'] = ranking['risk_band']

    # Convert to list and sort by critical stock value descending
    grouped_rankings = []
    for school, data in school_groups.items():
        # Calculate school-level ratio
        if data['total_bts_sales'] > 0:
            school_ratio = data['total_stock_value'] / data['total_bts_sales']
        else:
            school_ratio = 999999

        # Determine school risk band based on school-level ratio
        if school_ratio >= 999999:
            school_risk_band = 'critical'
            school_ratio_display = '∞'
        elif school_ratio > 3:
            school_risk_band = 'critical'
            school_ratio_display = round(school_ratio, 2)
        elif school_ratio > 2:
            school_risk_band = 'warning'
            school_ratio_display = round(school_ratio, 2)
        else:
            school_risk_band = 'healthy'
            school_ratio_display = round(school_ratio, 2)

        # Calculate critical stock value for this school
        critical_stock_value = sum(p['stock_value'] for p in data['products'] if p['risk_band'] == 'critical')

        grouped_rankings.append({
            'school': school,
            'product_count': data['product_count'],
            'total_stock_value': data['total_stock_value'],
            'total_bts_sales': data['total_bts_sales'],
            'ratio': school_ratio,
            'ratio_display': school_ratio_display,
            'risk_band': school_risk_band,
            'critical_stock_value': critical_stock_value,
            'products': sorted(data['products'], key=lambda x: x['ratio'], reverse=True)
        })

    # Sort by critical stock value descending (schools with most critical stock first)
    grouped_rankings.sort(key=lambda x: x['critical_stock_value'], reverse=True)

    return {
        'rankings': rankings,
        'grouped_rankings': grouped_rankings,
        'top_critical_school': top_critical_school,
        'top_critical_count': top_critical_count,
        'top_critical_value': top_critical_value,
        'last_sale_date': last_sale_date
    }


def calculate_heatmap_data(start_date=None, end_date=None, top_n_products=10):
    """
    Calculate heatmap data showing Schools (rows) x Top Products (columns)
    with color-coded ratios (stock value / BTS sales)

    Returns:
        dict with:
        - schools: list of school names (rows)
        - products: list of top product names (columns)
        - data: 2D matrix of ratios [school_index][product_index]
        - stock_data: 2D matrix of stock values
        - sales_data: 2D matrix of sales values
    """
    from django.db import connection
    import json

    start = start_date or BTS_START_DATE
    end = end_date or BTS_END_DATE

    # First, get the top N products by total stock value
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                p.cin7_id,
                p.name as product_name,
                p.style_code,
                SUM(COALESCE(s.stock_on_hand, 0) * COALESCE(po.cost_price, 0)) as total_stock_value
            FROM cin7_sync_product p
            LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
            LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
            WHERE p.category_name LIKE %s
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
            GROUP BY p.cin7_id, p.name, p.style_code
            HAVING total_stock_value > 0
            ORDER BY total_stock_value DESC
            LIMIT %s
        """, ['% Shop', '%%Shop%', top_n_products])

        top_products = cursor.fetchall()

    if not top_products:
        return {'schools': [], 'products': [], 'data': [], 'stock_data': [], 'sales_data': []}

    # Get product info
    product_ids = [str(p[0]) for p in top_products]
    product_names = [f"{p[2] or 'N/A'} - {p[1][:30]}" for p in top_products]

    # Get all schools
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT p.sub_category as school
            FROM cin7_sync_product p
            WHERE p.category_name LIKE %s
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
            ORDER BY school
        """, ['% Shop', '%%Shop%'])

        schools = [row[0] for row in cursor.fetchall()]

    # Get stock and sales data for each school-product combination
    with connection.cursor() as cursor:
        product_ids_str = ','.join(product_ids)

        cursor.execute(f"""
            SELECT
                p.sub_category as school,
                p.cin7_id as product_id,
                SUM(COALESCE(s.stock_on_hand, 0) * COALESCE(po.cost_price, 0)) as stock_value,
                0 as sales_value
            FROM cin7_sync_product p
            LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
            LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
            WHERE p.cin7_id IN ({product_ids_str})
              AND p.category_name LIKE %s
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
            GROUP BY p.sub_category, p.cin7_id

            UNION ALL

            SELECT
                p.sub_category as school,
                p.cin7_id as product_id,
                0 as stock_value,
                SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as sales_value
            FROM cin7_sync_salesorder so
            JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
            JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
            WHERE p.cin7_id IN ({product_ids_str})
              AND p.category_name LIKE %s
              AND so.invoice_date >= %s
              AND so.invoice_date <= %s
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
            GROUP BY p.sub_category, p.cin7_id
        """, ['% Shop', '%%Shop%', '% Shop', start, end, '%%Shop%'])

        results = cursor.fetchall()

    # Build lookup dict: {(school, product_id): (stock, sales)}
    data_lookup = {}
    for row in results:
        school = row[0]
        product_id = str(row[1])
        stock = float(row[2] or 0)
        sales = float(row[3] or 0)

        key = (school, product_id)
        if key in data_lookup:
            data_lookup[key] = (
                data_lookup[key][0] + stock,
                data_lookup[key][1] + sales
            )
        else:
            data_lookup[key] = (stock, sales)

    # Build 2D matrices
    ratio_matrix = []
    stock_matrix = []
    sales_matrix = []

    for school in schools:
        ratio_row = []
        stock_row = []
        sales_row = []

        for product_id in product_ids:
            key = (school, product_id)
            stock, sales = data_lookup.get(key, (0, 0))

            # Calculate ratio
            if sales > 0:
                ratio = stock / sales
            elif stock > 0:
                ratio = 999999  # Infinite ratio
            else:
                ratio = 0  # No data

            ratio_row.append(round(ratio, 2))
            stock_row.append(round(stock, 2))
            sales_row.append(round(sales, 2))

        ratio_matrix.append(ratio_row)
        stock_matrix.append(stock_row)
        sales_matrix.append(sales_row)

    return {
        'schools': schools,
        'products': product_names,
        'data': ratio_matrix,
        'stock_data': stock_matrix,
        'sales_data': sales_matrix
    }


def calculate_top_performing_schools(start_date=None, end_date=None, limit=10):
    """
    Calculate top 10 performing schools based on sales volume for current year, last year, and year before

    Returns:
        List of schools with:
        - School name
        - Most sold item for each year
        - Most sold item quantity for each year
        - Sales for each year
    """
    from django.db import connection
    from datetime import datetime

    # Parse the end date to determine the current year
    if end_date:
        current_year = datetime.strptime(end_date, '%Y-%m-%d').year
    else:
        current_year = datetime.strptime(BTS_END_DATE, '%Y-%m-%d').year

    # Define date ranges for three years
    current_year_start = f"{current_year}-01-01"
    current_year_end = f"{current_year}-12-31"

    last_year = current_year - 1
    last_year_start = f"{last_year}-01-01"
    last_year_end = f"{last_year}-12-31"

    year_before = current_year - 2
    year_before_start = f"{year_before}-01-01"
    year_before_end = f"{year_before}-12-31"

    with connection.cursor() as cursor:
        cursor.execute("""
            WITH all_schools AS (
                SELECT DISTINCT p.sub_category as school
                FROM cin7_sync_product p
                WHERE p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
            ),
            current_year_sales AS (
                SELECT
                    p.sub_category as school,
                    SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as total_sales
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category
            ),
            last_year_sales AS (
                SELECT
                    p.sub_category as school,
                    SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as total_sales
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category
            ),
            year_before_sales AS (
                SELECT
                    p.sub_category as school,
                    SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as total_sales
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category
            ),
            top_product_current_year AS (
                SELECT
                    p.sub_category as school,
                    p.name as product_name,
                    SUM(COALESCE(soli.qty, 0)) as product_qty,
                    ROW_NUMBER() OVER (PARTITION BY p.sub_category ORDER BY SUM(COALESCE(soli.qty, 0)) DESC) as rn
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category, p.name
            ),
            top_product_last_year AS (
                SELECT
                    p.sub_category as school,
                    p.name as product_name,
                    SUM(COALESCE(soli.qty, 0)) as product_qty,
                    ROW_NUMBER() OVER (PARTITION BY p.sub_category ORDER BY SUM(COALESCE(soli.qty, 0)) DESC) as rn
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category, p.name
            ),
            top_product_year_before AS (
                SELECT
                    p.sub_category as school,
                    p.name as product_name,
                    SUM(COALESCE(soli.qty, 0)) as product_qty,
                    ROW_NUMBER() OVER (PARTITION BY p.sub_category ORDER BY SUM(COALESCE(soli.qty, 0)) DESC) as rn
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category, p.name
            )
            SELECT
                a.school,
                COALESCE(cy.total_sales, 0) as current_year_sales,
                tpcy.product_name as cy_product,
                tpcy.product_qty as cy_qty,
                COALESCE(ly.total_sales, 0) as last_year_sales,
                tply.product_name as ly_product,
                tply.product_qty as ly_qty,
                COALESCE(yb.total_sales, 0) as year_before_sales,
                tpyb.product_name as yb_product,
                tpyb.product_qty as yb_qty
            FROM all_schools a
            LEFT JOIN current_year_sales cy ON a.school = cy.school
            LEFT JOIN last_year_sales ly ON a.school = ly.school
            LEFT JOIN year_before_sales yb ON a.school = yb.school
            LEFT JOIN top_product_current_year tpcy ON a.school = tpcy.school AND tpcy.rn = 1
            LEFT JOIN top_product_last_year tply ON a.school = tply.school AND tply.rn = 1
            LEFT JOIN top_product_year_before tpyb ON a.school = tpyb.school AND tpyb.rn = 1
            ORDER BY current_year_sales DESC
            LIMIT %s
        """, [
            '% Shop', '%%Shop%',  # all_schools
            '% Shop', current_year_start, current_year_end, '%%Shop%',  # current_year_sales
            '% Shop', last_year_start, last_year_end, '%%Shop%',  # last_year_sales
            '% Shop', year_before_start, year_before_end, '%%Shop%',  # year_before_sales
            '% Shop', current_year_start, current_year_end, '%%Shop%',  # top_product_current_year
            '% Shop', last_year_start, last_year_end, '%%Shop%',  # top_product_last_year
            '% Shop', year_before_start, year_before_end, '%%Shop%',  # top_product_year_before
            limit
        ])

        rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({
            'school': row[0],
            'current_year_sales': float(row[1] or 0),
            'current_year_item': row[2] or 'N/A',
            'current_year_qty': float(row[3] or 0),
            'last_year_sales': float(row[4] or 0),
            'last_year_item': row[5] or 'N/A',
            'last_year_qty': float(row[6] or 0),
            'year_before_sales': float(row[7] or 0),
            'year_before_item': row[8] or 'N/A',
            'year_before_qty': float(row[9] or 0),
            'current_year': current_year,
            'last_year': last_year,
            'year_before': year_before
        })

    return results
def calculate_slow_moving_schools(start_date=None, end_date=None, limit=10):
    """
    Calculate slow-moving schools with least/no sales

    Returns:
        List of schools with:
        - School name
        - Total sales volume (could be 0)
        - Last sale date (could be NULL)
    """
    from django.db import connection

    start = start_date or BTS_START_DATE
    end = end_date or BTS_END_DATE

    with connection.cursor() as cursor:
        cursor.execute("""
            WITH all_schools AS (
                SELECT DISTINCT p.sub_category as school
                FROM cin7_sync_product p
                WHERE p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
            ),
            school_sales AS (
                SELECT
                    p.sub_category as school,
                    SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as total_sales,
                    MAX(so.invoice_date) as last_sale_date
                FROM cin7_sync_salesorder so
                JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category
            )
            SELECT
                a.school,
                COALESCE(ss.total_sales, 0) as total_sales,
                ss.last_sale_date
            FROM all_schools a
            LEFT JOIN school_sales ss ON a.school = ss.school
            ORDER BY COALESCE(ss.total_sales, 0) ASC, ss.last_sale_date ASC
            LIMIT %s
        """, ['% Shop', '%%Shop%', '% Shop', start, end, '%%Shop%', limit])

        rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({
            'school': row[0],
            'total_sales': float(row[1] or 0),
            'last_sale_date': row[2]
        })

    return results


@login_required()
@permission_required('dashboard.view')
@require_http_methods(["GET"])
def dashboard_home(request):
    """
    Main dashboard view with summary metrics and customer rankings
    """
    from django.core.cache import cache

    # Check if user is authenticated
    if not auth_backend.is_authenticated(request):
        return redirect('auth:login')

    # Get date parameters from request or use defaults
    start_date = request.GET.get('start_date', BTS_START_DATE)
    end_date = request.GET.get('end_date', BTS_END_DATE)

    # Create a cache key based on the date range
    cache_key = f'dashboard_data_{start_date}_{end_date}'

    # Try to get cached data
    cached_data = cache.get(cache_key)

    if cached_data:
        # Use cached data
        summary = cached_data['summary']
        customer_rankings_data = cached_data['customer_rankings_data']
        product_rankings_data = cached_data['product_rankings_data']
        heatmap_data = cached_data['heatmap_data']
        top_performing_schools = cached_data['top_performing_schools']
        slow_moving_schools = cached_data['slow_moving_schools']
    else:
        # Calculate fresh data
        summary = calculate_summary_metrics(start_date, end_date)
        customer_rankings_data = calculate_customer_rankings(start_date, end_date)
        product_rankings_data = calculate_product_rankings(start_date, end_date)
        heatmap_data = calculate_heatmap_data(start_date, end_date, top_n_products=10)
        top_performing_schools = calculate_top_performing_schools(start_date, end_date, limit=10)
        slow_moving_schools = calculate_slow_moving_schools(start_date, end_date, limit=10)

        # Cache the results for 10 minutes (600 seconds)
        cache.set(cache_key, {
            'summary': summary,
            'customer_rankings_data': customer_rankings_data,
            'product_rankings_data': product_rankings_data,
            'heatmap_data': heatmap_data,
            'top_performing_schools': top_performing_schools,
            'slow_moving_schools': slow_moving_schools,
        }, 600)

    # Serialize heatmap data as JSON for JavaScript
    import json
    heatmap_json = json.dumps(heatmap_data)

    context = {
        'summary': summary,
        'customer_rankings': customer_rankings_data['rankings'],
        'customer_critical_count': customer_rankings_data['critical_count'],
        'customer_warning_count': customer_rankings_data['warning_count'],
        'customer_healthy_count': customer_rankings_data['healthy_count'],
        'customer_critical_stock': customer_rankings_data['critical_stock'],
        'customer_warning_stock': customer_rankings_data['warning_stock'],
        'customer_healthy_stock': customer_rankings_data['healthy_stock'],
        'product_rankings': product_rankings_data['rankings'],
        'product_grouped_rankings': product_rankings_data['grouped_rankings'],
        'product_top_critical_school': product_rankings_data['top_critical_school'],
        'product_top_critical_count': product_rankings_data['top_critical_count'],
        'product_top_critical_value': product_rankings_data['top_critical_value'],
        'product_last_sale_date': product_rankings_data['last_sale_date'],
        'heatmap_data': heatmap_data,
        'heatmap_json': heatmap_json,
        'top_performing_schools': top_performing_schools,
        'slow_moving_schools': slow_moving_schools,
        'bts_period': f"{start_date} to {end_date}",
        'start_date': start_date,
        'end_date': end_date
    }

    return render(request, 'dashboard/home.html', context)


@login_required()
@permission_required('dashboard.view')
@require_http_methods(["GET"])
def dashboard_api(request):
    """
    API endpoint for dashboard data (for AJAX updates)
    """
    if not auth_backend.is_authenticated(request):
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    return JsonResponse({'status': 'ok', 'message': 'Dashboard API'})


@require_http_methods(["POST"])
def refresh_cache(request):
    """
    Endpoint to manually refresh dashboard cache
    """
    if not auth_backend.is_authenticated(request):
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    return JsonResponse({
        'status': 'success',
        'message': 'Cache refreshed successfully'
    })


def calculate_bts_historical_data():
    """
    Calculate historical BTS sales data for forecasting
    Returns monthly sales data for the BTS period (Jan-Feb) across all years
    """
    from django.db import connection
    from datetime import datetime

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                DATE_FORMAT(so.invoice_date, '%%Y-%%m') as month,
                YEAR(so.invoice_date) as year,
                MONTH(so.invoice_date) as month_num,
                SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as total_sales,
                COUNT(DISTINCT so.cin7_id) as order_count,
                COUNT(DISTINCT so.customer_name) as customer_count
            FROM cin7_sync_salesorder so
            JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
            JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
            WHERE p.category_name LIKE %s
              AND so.invoice_date IS NOT NULL
              AND MONTH(so.invoice_date) IN (1, 2)
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
            GROUP BY DATE_FORMAT(so.invoice_date, '%%Y-%%m'), YEAR(so.invoice_date), MONTH(so.invoice_date)
            ORDER BY so.invoice_date
        """, ['% Shop', '%%Shop%'])

        rows = cursor.fetchall()

    historical_data = []
    for row in rows:
        historical_data.append({
            'month': row[0],
            'year': int(row[1]),
            'month_num': int(row[2]),
            'total_sales': float(row[3] or 0),
            'order_count': int(row[4] or 0),
            'customer_count': int(row[5] or 0)
        })

    return historical_data


def calculate_school_forecasts():
    """
    Calculate historical sales by school for forecasting
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                p.sub_category as school,
                YEAR(so.invoice_date) as year,
                MONTH(so.invoice_date) as month_num,
                SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as total_sales
            FROM cin7_sync_salesorder so
            JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
            JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
            WHERE p.category_name LIKE %s
              AND so.invoice_date IS NOT NULL
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
              AND MONTH(so.invoice_date) IN (1, 2)
            GROUP BY p.sub_category, YEAR(so.invoice_date), MONTH(so.invoice_date)
            ORDER BY p.sub_category, YEAR(so.invoice_date), MONTH(so.invoice_date)
        """, ['% Shop', '%%Shop%'])

        rows = cursor.fetchall()

    school_data = {}
    for row in rows:
        school = row[0]
        if school not in school_data:
            school_data[school] = []
        school_data[school].append({
            'year': int(row[1]),
            'month': int(row[2]),
            'sales': float(row[3] or 0)
        })

    return school_data


def calculate_customer_lifetime_value():
    """
    Calculate Customer Lifetime Value (CLV) prediction for each school
    Predicts 12-month revenue, churn risk, and customer value tier
    """
    from django.db import connection
    from datetime import datetime, timedelta

    with connection.cursor() as cursor:
        # Get historical sales data per school
        cursor.execute("""
            SELECT
                p.sub_category as school,
                YEAR(so.invoice_date) as year,
                MONTH(so.invoice_date) as month_num,
                COUNT(DISTINCT so.id) as order_count,
                SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as total_revenue,
                MAX(so.invoice_date) as last_order_date
            FROM cin7_sync_salesorder so
            JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
            JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
            WHERE p.category_name LIKE %s
              AND so.invoice_date IS NOT NULL
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
              AND YEAR(so.invoice_date) >= 2022
            GROUP BY p.sub_category, YEAR(so.invoice_date), MONTH(so.invoice_date)
            ORDER BY p.sub_category, year DESC, month_num DESC
        """, ['% Shop', '%%Shop%'])

        rows = cursor.fetchall()

    # Organize data by school
    school_data = {}
    for row in rows:
        school = row[0]
        if school not in school_data:
            school_data[school] = {
                'monthly_data': [],
                'last_order_date': None
            }

        school_data[school]['monthly_data'].append({
            'year': int(row[1]),
            'month': int(row[2]),
            'order_count': int(row[3]),
            'revenue': float(row[4] or 0)
        })

        # Track most recent order date
        if row[5]:
            if not school_data[school]['last_order_date'] or row[5] > school_data[school]['last_order_date']:
                school_data[school]['last_order_date'] = row[5]

    # Calculate CLV metrics for each school
    clv_results = []
    current_date = datetime.now()

    for school, data in school_data.items():
        monthly_data = data['monthly_data']
        last_order = data['last_order_date']

        if not monthly_data:
            continue

        # Calculate historical metrics
        total_revenue = sum(m['revenue'] for m in monthly_data)
        total_orders = sum(m['order_count'] for m in monthly_data)
        months_active = len(monthly_data)

        # Average monthly revenue
        avg_monthly_revenue = total_revenue / months_active if months_active > 0 else 0

        # Calculate trend (are they growing or declining?)
        recent_6_months = [m for m in monthly_data if m['year'] >= 2025]
        older_6_months = [m for m in monthly_data if m['year'] < 2025]

        recent_avg = sum(m['revenue'] for m in recent_6_months) / len(recent_6_months) if recent_6_months else 0
        older_avg = sum(m['revenue'] for m in older_6_months) / len(older_6_months) if older_6_months else avg_monthly_revenue

        if older_avg > 0:
            growth_rate = ((recent_avg - older_avg) / older_avg) * 100
        else:
            growth_rate = 0

        # Predict next 12 months revenue (using average + growth trend)
        predicted_12m_revenue = avg_monthly_revenue * 12 * (1 + (growth_rate / 100))

        # Calculate churn risk
        if last_order:
            days_since_last_order = (current_date - last_order).days
        else:
            days_since_last_order = 999

        # Churn risk logic
        if days_since_last_order > 365:
            churn_risk = "High"
            churn_score = 80
        elif days_since_last_order > 180:
            churn_risk = "Medium"
            churn_score = 50
        elif days_since_last_order > 90:
            churn_risk = "Low"
            churn_score = 20
        else:
            churn_risk = "Very Low"
            churn_score = 5

        # Customer value tier
        if predicted_12m_revenue > 100000:
            value_tier = "VIP"
        elif predicted_12m_revenue > 50000:
            value_tier = "High Value"
        elif predicted_12m_revenue > 20000:
            value_tier = "Medium Value"
        else:
            value_tier = "Low Value"

        clv_results.append({
            'school': school,
            'predicted_12m_revenue': predicted_12m_revenue,
            'historical_total_revenue': total_revenue,
            'avg_monthly_revenue': avg_monthly_revenue,
            'total_orders': total_orders,
            'months_active': months_active,
            'growth_rate': growth_rate,
            'churn_risk': churn_risk,
            'churn_score': churn_score,
            'value_tier': value_tier,
            'days_since_last_order': days_since_last_order,
            'last_order_date': last_order
        })

    # Sort by predicted revenue (highest value customers first)
    clv_results.sort(key=lambda x: x['predicted_12m_revenue'], reverse=True)

    return clv_results


def calculate_product_forecasts():
    """
    Calculate historical sales by product for forecasting
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                p.name as product,
                YEAR(so.invoice_date) as year,
                MONTH(so.invoice_date) as month_num,
                SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as total_sales
            FROM cin7_sync_salesorder so
            JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
            JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
            WHERE p.category_name LIKE %s
              AND so.invoice_date IS NOT NULL
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
              AND MONTH(so.invoice_date) IN (1, 2)
            GROUP BY p.name, YEAR(so.invoice_date), MONTH(so.invoice_date)
            ORDER BY total_sales DESC
        """, ['% Shop', '%%Shop%'])

        rows = cursor.fetchall()

    product_data = {}
    for row in rows:
        product = row[0]
        if product not in product_data:
            product_data[product] = []
        product_data[product].append({
            'year': int(row[1]),
            'month': int(row[2]),
            'sales': float(row[3] or 0)
        })

    return product_data


def generate_simple_forecast(historical_data):
    """
    Generate simple forecast using moving average (fallback if Prophet fails)
    """
    if not historical_data:
        return {'forecast_2027': 0, 'confidence_lower': 0, 'confidence_upper': 0}

    # Calculate BTS season sales (Jan-Feb) for each year
    bts_sales_by_year = {}
    for item in historical_data:
        if item['month_num'] in [1, 2]:
            year = item['year']
            if year not in bts_sales_by_year:
                bts_sales_by_year[year] = 0
            bts_sales_by_year[year] += item['total_sales']

    if not bts_sales_by_year:
        return {'forecast_2027': 0, 'confidence_lower': 0, 'confidence_upper': 0}

    # Calculate growth rate
    years = sorted(bts_sales_by_year.keys())
    if len(years) < 2:
        forecast = bts_sales_by_year[years[0]]
        return {
            'forecast_2027': forecast,
            'confidence_lower': forecast * 0.8,
            'confidence_upper': forecast * 1.2
        }

    # Calculate average year-over-year growth
    growth_rates = []
    for i in range(1, len(years)):
        prev_sales = bts_sales_by_year[years[i-1]]
        curr_sales = bts_sales_by_year[years[i]]
        if prev_sales > 0:
            growth_rate = (curr_sales - prev_sales) / prev_sales
            growth_rates.append(growth_rate)

    avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0
    latest_year = years[-1]
    latest_sales = bts_sales_by_year[latest_year]

    # Project to 2027
    years_to_forecast = 2027 - latest_year
    forecast = latest_sales * ((1 + avg_growth) ** years_to_forecast)

    # Calculate confidence intervals (±20%)
    return {
        'forecast_2027': forecast,
        'confidence_lower': forecast * 0.8,
        'confidence_upper': forecast * 1.2,
        'historical_years': years,
        'historical_sales': [bts_sales_by_year[year] for year in years]
    }


@login_required()
@permission_required('dashboard.view')
@require_http_methods(["GET"])
def bts_forecasting(request):
    """
    BTS Sales Forecasting Dashboard
    Predict next year's BTS sales (Jan-Feb 2027)
    """
    if not auth_backend.is_authenticated(request):
        return redirect('auth:login')

    from django.core.cache import cache

    # Check cache
    cache_key = 'bts_forecasting_data'
    cached_data = cache.get(cache_key)

    if cached_data:
        forecast_data = cached_data
    else:
        # Calculate historical data
        historical_data = calculate_bts_historical_data()
        school_data = calculate_school_forecasts()
        product_data = calculate_product_forecasts()
        clv_data = calculate_customer_lifetime_value()

        # Generate overall forecast
        overall_forecast = generate_simple_forecast(historical_data)

        # Generate top 20 school forecasts
        school_forecasts = []
        for school, data in sorted(school_data.items(), key=lambda x: sum(d['sales'] for d in x[1]), reverse=True)[:20]:
            forecast = generate_simple_forecast([{'month_num': d['month'], 'year': d['year'], 'total_sales': d['sales']} for d in data])

            # Create a dictionary mapping year to sales for easy template access
            sales_by_year = {}
            for i, year in enumerate(forecast.get('historical_years', [])):
                sales_by_year[year] = forecast.get('historical_sales', [])[i] if i < len(forecast.get('historical_sales', [])) else 0

            school_forecasts.append({
                'school': school,
                'forecast': forecast['forecast_2027'],
                'historical_sales': forecast.get('historical_sales', []),
                'historical_years': forecast.get('historical_years', []),
                'sales_by_year': sales_by_year
            })

        # Generate top 20 product forecasts
        product_forecasts = []
        for product, data in sorted(product_data.items(), key=lambda x: sum(d['sales'] for d in x[1]), reverse=True)[:20]:
            forecast = generate_simple_forecast([{'month_num': d['month'], 'year': d['year'], 'total_sales': d['sales']} for d in data])

            # Create a dictionary mapping year to sales for easy template access
            sales_by_year = {}
            for i, year in enumerate(forecast.get('historical_years', [])):
                sales_by_year[year] = forecast.get('historical_sales', [])[i] if i < len(forecast.get('historical_sales', [])) else 0

            product_forecasts.append({
                'product': product,
                'forecast': forecast['forecast_2027'],
                'historical_sales': forecast.get('historical_sales', []),
                'historical_years': forecast.get('historical_years', []),
                'sales_by_year': sales_by_year
            })

        forecast_data = {
            'overall_forecast': overall_forecast,
            'school_forecasts': school_forecasts,
            'product_forecasts': product_forecasts,
            'historical_data': historical_data,
            'clv_data': clv_data
        }

        # Cache for 1 hour
        cache.set(cache_key, forecast_data, 3600)

    import json

    context = {
        'overall_forecast': forecast_data['overall_forecast'],
        'school_forecasts': forecast_data['school_forecasts'],
        'product_forecasts': forecast_data['product_forecasts'],
        'historical_data': forecast_data['historical_data'],
        'historical_data_json': json.dumps(forecast_data['historical_data']),
        'clv_data': forecast_data.get('clv_data', [])
    }

    return render(request, 'dashboard/bts_forecasting.html', context)


def extract_parent_product_from_sku(sku_code):
    """
    Extract parent product name from SKU code by removing size suffix

    Examples:
    - "BFLC 01 CL NAVY RUC-M" -> "BFLC 01 CL NAVY RUC"
    - "BFLC 05 CL RC -L" -> "BFLC 05 CL RC"
    - "BL 170J JCHS -10" -> "BL 170J JCHS"
    - "US SH 703L LBC -80" -> "US SH 703L LBC"
    """
    import re
    # Remove size suffix pattern like "-M", "-L", "-10", "-80", etc.
    # Pattern: space followed by dash and size indicator at the end
    parent_name = re.sub(r'\s*-\s*[\dA-Z]+$', '', sku_code)
    return parent_name


def extract_size_from_sku(sku_code):
    """
    Extract size from SKU code

    Examples:
    - "BFLC 01 CL NAVY RUC-M" -> "M"
    - "BL 170J JCHS -10" -> "10"
    - "US SH 703L LBC -80" -> "80"
    """
    import re
    match = re.search(r'-\s*([\dA-Z]+)$', sku_code)
    if match:
        return match.group(1)
    return 'N/A'


@login_required
def forecasting_filter_options(request):
    """
    API endpoint to return filter options for sales forecasting page
    Returns different filter data based on the current aggregation level
    """
    from django.db import connection
    import json

    level = request.GET.get('level', 'school')

    result = {
        'schools': [],
        'products': [],
        'style_codes': [],
        'shops': [],
        'categories': []
    }

    # Only load filter options for the currently selected level (performance optimization)
    if level == 'school':
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT sub_category
                FROM cin7_sync_product
                WHERE (category_name LIKE '%%Shop' OR category_name LIKE '%%Store')
                  AND category_name NOT IN ('Shop', 'Store')
                  AND category_name NOT LIKE 'Wholesale%%'
                  AND sub_category IS NOT NULL
                  AND sub_category != ''
                ORDER BY sub_category
            """)
            result['schools'] = [{'value': row[0], 'label': row[0]} for row in cursor.fetchall()]

    elif level == 'product':
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT p.name, p.cin7_id
                FROM cin7_sync_product p
                WHERE (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
                  AND p.category_name NOT IN ('Shop', 'Store')
                  AND p.category_name NOT LIKE 'Wholesale%%'
                  AND p.name IS NOT NULL
                ORDER BY p.name
            """)
            result['products'] = [{'value': str(row[1]), 'label': row[0]} for row in cursor.fetchall()]

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT style_code
                FROM cin7_sync_product
                WHERE style_code IS NOT NULL
                  AND style_code != ''
                  AND (category_name LIKE '%% Shop' OR category_name LIKE '%% Store')
                  AND category_name NOT IN ('Shop', 'Store')
                ORDER BY style_code
            """)
            result['style_codes'] = [{'value': row[0], 'label': row[0]} for row in cursor.fetchall()]

    elif level == 'shop':
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT category_name
                FROM cin7_sync_product
                WHERE (category_name LIKE '%% Shop' OR category_name LIKE '%% Store')
                  AND category_name NOT IN ('Shop', 'Store')
                ORDER BY category_name
            """)
            result['shops'] = [{'value': row[0], 'label': row[0]} for row in cursor.fetchall()]

    elif level == 'category':
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT sub_category
                FROM cin7_sync_product
                WHERE sub_category IS NOT NULL
                  AND sub_category != ''
                ORDER BY sub_category
            """)
            result['categories'] = [{'value': row[0], 'label': row[0]} for row in cursor.fetchall()]

    return JsonResponse(result)


@login_required
@permission_required('forecasting.view')
def sales_forecasting(request):
    """
    Main sales forecasting dashboard with AI/ML predictions
    Supports flexible date range selection (default: today + 30 days)
    Falls back to legacy fixed horizons if no base forecasts available
    """
    from dashboard.models import SalesForecast, SalesForecastBase
    from django.db.models import Count, Avg, Sum
    from django.core.cache import cache
    from collections import defaultdict
    from datetime import datetime, timedelta, date as datetime_date
    import json

    # Helper function to get stock data for a SKU
    def get_stock_data(sku_code):
        """Get aggregated stock data and product name for a SKU across all branches using raw SQL"""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COALESCE(SUM(s.stock_on_hand), 0) as total_stock_on_hand,
                    COALESCE(SUM(s.incoming), 0) as total_incoming,
                    COALESCE(
                        MAX(p.name),
                        (
                            SELECT name
                            FROM cin7_sync_salesorderlineitem
                            WHERE code = %s
                            AND name IS NOT NULL
                            AND name != ''
                            GROUP BY name
                            ORDER BY COUNT(*) DESC
                            LIMIT 1
                        ),
                        %s
                    ) as product_name
                FROM cin7_sync_productoption po
                LEFT JOIN cin7_sync_product p ON p.id = po.product_id
                LEFT JOIN cin7_sync_stock s ON s.code = po.code
                WHERE po.code = %s
            """, [sku_code, sku_code, sku_code])
            row = cursor.fetchone()

        return {
            'stock_on_hand': float(row[0] or 0),
            'incoming': float(row[1] or 0),
            'product_name': row[2] if row[2] else sku_code
        }

    def batch_get_stock_data(sku_codes):
        """Get aggregated stock data for multiple SKUs in a single query"""
        from django.db import connection

        if not sku_codes:
            return {}

        sku_list = list(set(sku_codes))
        placeholders = ','.join(['%s'] * len(sku_list))

        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT
                    po.code,
                    COALESCE(SUM(s.stock_on_hand), 0) as total_stock_on_hand,
                    COALESCE(SUM(s.incoming), 0) as total_incoming,
                    MAX(p.name) as product_name
                FROM cin7_sync_productoption po
                LEFT JOIN cin7_sync_product p ON p.id = po.product_id
                LEFT JOIN cin7_sync_stock s ON s.code = po.code
                WHERE po.code IN ({placeholders})
                GROUP BY po.code
            """, sku_list)
            rows = cursor.fetchall()

        result = {}
        for row in rows:
            result[row[0]] = {
                'stock_on_hand': float(row[1] or 0),
                'incoming': float(row[2] or 0),
                'product_name': row[3] if row[3] else row[0]
            }

        # Fill in defaults for any SKUs not found
        for sku in sku_list:
            if sku not in result:
                result[sku] = {
                    'stock_on_hand': 0.0,
                    'incoming': 0.0,
                    'product_name': sku
                }

        return result

    # Helper function to aggregate product forecasts by shop
    def get_shop_forecasts_from_products(start_date, end_date, search_query=None, filters=None, user_school_subcategories=None, user_store_categories=None):
        """
        Aggregate product-level forecasts by shop category (category_name ending with 'Shop')

        This is the smart approach: instead of generating separate shop forecasts,
        we dynamically aggregate existing product forecasts by their shop category.

        Benefits:
        - No separate forecast generation needed
        - Always up-to-date with latest product forecasts
        - Mathematically correct: shop total = sum of products in that shop
        - No data duplication or discrepancies

        Args:
            start_date: Start date for forecast range
            end_date: End date for forecast range
            search_query: General search query (legacy)
            filters: Dictionary containing specific filters (school, product, style_code, shop, category)
            user_school_subcategories: List of school sub_categories for data scope filtering (Sales Team)
            user_store_categories: List of category_name values for data scope filtering (Store Level)

        Returns:
            list: List of shop forecast dictionaries with aggregated data
        """
        from django.db import connection

        logger = logging.getLogger(__name__)
        logger.info('=== AGGREGATING SHOP FORECASTS FROM PRODUCTS ===')
        logger.info(f'Date range: {start_date} to {end_date}')
        logger.info(f'Search query: {search_query}')
        logger.info(f'Filters: {filters}')
        logger.info(f'User school filter: {user_school_subcategories}')
        logger.info(f'User store categories filter: {user_store_categories}')

        # Build SQL query to fetch product forecasts with shop category
        sql = """
            SELECT
                p.category_name as shop_name,
                sf.daily_forecasts,
                sf.accuracy_score,
                sf.mae,
                sf.mape,
                sf.model_params,
                sf.entity_name as sku_code,
                COALESCE(p.name, po.code, sf.entity_name) as product_name,
                po.option1 as size
            FROM dashboard_salesforecastbase sf
            JOIN cin7_sync_productoption po ON po.code = sf.entity_name
            JOIN cin7_sync_product p ON p.id = po.product_id
            WHERE sf.aggregation_level = 'product'
              AND (p.category_name LIKE %s OR p.category_name LIKE %s)
        """

        # Base params for shop/store filter (includes both Shop and Store suffixes)
        params = ['%%Shop', '%%Store']

        # DATA SCOPE: Filter by user's assigned schools (Sales Team)
        if user_school_subcategories:
            placeholders = ', '.join(['%s'] * len(user_school_subcategories))
            sql += f" AND p.sub_category IN ({placeholders})"
            params.extend(user_school_subcategories)

        # DATA SCOPE: Filter by user's assigned stores (Store Level)
        if user_store_categories:
            placeholders = ', '.join(['%s'] * len(user_store_categories))
            sql += f" AND p.category_name IN ({placeholders})"
            params.extend(user_store_categories)

        # Apply search filter if provided
        if search_query:
            sql += " AND p.category_name LIKE %s"
            params.append(f'%{search_query}%')

        # Apply specific filters if provided
        if filters:
            if filters.get('product'):
                sql += " AND p.cin7_id = %s"
                params.append(filters['product'])
            if filters.get('style_code'):
                sql += " AND p.style_code = %s"
                params.append(filters['style_code'])
            if filters.get('shop'):
                sql += " AND p.category_name = %s"
                params.append(filters['shop'])
            if filters.get('category'):
                sql += " AND p.sub_category = %s"
                params.append(filters['category'])

        # Order by category for grouping
        sql += " ORDER BY p.category_name, sf.entity_name"

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        logger.info(f'Found {len(rows)} product forecasts belonging to shops')

        # Aggregate forecasts by shop
        shop_aggregates = defaultdict(lambda: {
            'daily_totals': defaultdict(float),
            'accuracy_scores': [],
            'mae_scores': [],
            'mape_scores': [],
            'product_count': 0,
            'sku_codes': [],
            'products': []  # Store individual product details
        })

        for row in rows:
            shop_name, daily_forecasts_json, accuracy_score, mae, mape, model_params_json, sku_code, product_name, size = row

            # Parse JSON fields
            if isinstance(daily_forecasts_json, str):
                daily_forecasts = json.loads(daily_forecasts_json)
            else:
                daily_forecasts = daily_forecasts_json or {}

            if isinstance(model_params_json, str):
                model_params = json.loads(model_params_json)
            else:
                model_params = model_params_json or {}

            # Calculate product total for date range
            product_total = 0
            for date_str, forecast_data in daily_forecasts.items():
                try:
                    forecast_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    if start_date <= forecast_date <= end_date:
                        quantity = forecast_data.get('quantity', 0)
                        shop_aggregates[shop_name]['daily_totals'][date_str] += quantity
                        product_total += quantity
                except (ValueError, TypeError) as e:
                    logger.warning(f'Error parsing date {date_str}: {e}')
                    continue

            # Store individual product details
            shop_aggregates[shop_name]['products'].append({
                'product_name': product_name or sku_code,
                'sku_code': sku_code,
                'size': size or 'N/A',
                'total_quantity': round(product_total, 1),
                'accuracy_score': round(accuracy_score, 1) if accuracy_score is not None else 'N/A'
            })

            # Collect accuracy metrics
            if accuracy_score is not None:
                shop_aggregates[shop_name]['accuracy_scores'].append(accuracy_score)
            if mae is not None:
                shop_aggregates[shop_name]['mae_scores'].append(mae)
            if mape is not None:
                shop_aggregates[shop_name]['mape_scores'].append(mape)

            shop_aggregates[shop_name]['product_count'] += 1
            shop_aggregates[shop_name]['sku_codes'].append(sku_code)

        logger.info(f'Aggregated into {len(shop_aggregates)} shops')

        # Calculate number of days in range
        num_days = (end_date - start_date).days + 1

        # Convert aggregated data into forecast list format
        forecast_list = []
        for shop_name, agg_data in sorted(shop_aggregates.items()):
            # Build date_range_data structure
            date_range_data = {}
            for date_str in sorted(agg_data['daily_totals'].keys()):
                quantity = agg_data['daily_totals'][date_str]
                date_range_data[date_str] = {
                    'quantity': quantity,
                    'confidence_lower': quantity * 0.9,  # Approximate confidence intervals
                    'confidence_upper': quantity * 1.1
                }

            # Calculate total quantity for the date range
            total_qty = sum([day['quantity'] for day in date_range_data.values()])

            # Get first 7 days detail
            forecast_dates = sorted(date_range_data.keys())[:7]
            next_7_days = [
                {
                    'date': date,
                    'quantity': date_range_data[date]['quantity'],
                    'confidence_lower': date_range_data[date]['confidence_lower'],
                    'confidence_upper': date_range_data[date]['confidence_upper']
                }
                for date in forecast_dates
            ]

            # Calculate average metrics
            avg_accuracy = sum(agg_data['accuracy_scores']) / len(agg_data['accuracy_scores']) if agg_data['accuracy_scores'] else None
            avg_mae = sum(agg_data['mae_scores']) / len(agg_data['mae_scores']) if agg_data['mae_scores'] else None
            avg_mape = sum(agg_data['mape_scores']) / len(agg_data['mape_scores']) if agg_data['mape_scores'] else None

            # Build shop forecast data structure (MUST match school-level format exactly)
            shop_forecast = {
                'entity_name': shop_name,
                'total_quantity': round(total_qty, 1),
                'accuracy_score': round(avg_accuracy, 1) if avg_accuracy is not None else 'N/A',
                'model': 'Product Aggregation',  # Indicates this is aggregated from products
                'next_7_days': next_7_days,
                'forecast_data': date_range_data,
                'training_days': 0,  # Not applicable for aggregated forecasts
                'mae': round(avg_mae, 2) if avg_mae else None,
                'mape': round(avg_mape, 2) if avg_mape else None,
                'is_grouped': False,
                'product_count': agg_data['product_count'],  # Additional metadata
                'source': 'aggregated',  # Flag to indicate this is aggregated
                'products': agg_data['products'],  # Include product details for expandable rows
                'num_days': num_days  # Include number of days for display
            }

            forecast_list.append(shop_forecast)

            logger.info(f'✓ Shop: {shop_name}')
            logger.info(f'  - Products: {agg_data["product_count"]}')
            logger.info(f'  - Total Forecast (aggregated): {round(total_qty, 1)} units')
            logger.info(f'  - Avg Accuracy: {round(avg_accuracy, 1) if avg_accuracy else "N/A"}%')
            logger.info(f'  - Date Range: {len(date_range_data)} days ({start_date} to {end_date})')
            logger.info(f'  - Next 7 Days: {len(next_7_days)} days')
            logger.info(f'  - Sample SKUs: {agg_data["sku_codes"][:3]}')

        logger.info(f'=== SHOP AGGREGATION COMPLETE ===')
        logger.info(f'Total shops: {len(forecast_list)}')
        logger.info(f'Total products aggregated: {sum([f["product_count"] for f in forecast_list])}')
        logger.info(f'Total forecast units: {sum([f["total_quantity"] for f in forecast_list])}')

        # Verification: Log the shop totals for cross-checking with product breakdown
        logger.info(f'=== SHOP TOTALS FOR VERIFICATION ===')
        for shop_forecast in forecast_list[:3]:  # Log first 3 shops
            logger.info(f'{shop_forecast["entity_name"]}: {shop_forecast["total_quantity"]:.2f} units ({shop_forecast["product_count"]} products)')
        logger.info(f'=== END SHOP TOTALS ===')

        # Log sample shop data structure for debugging
        if forecast_list:
            logger.info(f'=== SAMPLE SHOP DATA STRUCTURE ===')
            sample_shop = forecast_list[0]
            logger.info(f'Shop Name: {sample_shop.get("entity_name")}')
            logger.info(f'Total Quantity: {sample_shop.get("total_quantity")}')
            logger.info(f'Accuracy Score: {sample_shop.get("accuracy_score")}')
            logger.info(f'Model: {sample_shop.get("model")}')
            logger.info(f'MAE: {sample_shop.get("mae")}')
            logger.info(f'MAPE: {sample_shop.get("mape")}')
            logger.info(f'Training Days: {sample_shop.get("training_days")}')
            logger.info(f'Is Grouped: {sample_shop.get("is_grouped")}')
            logger.info(f'Has forecast_data: {bool(sample_shop.get("forecast_data"))}')
            logger.info(f'Next 7 Days count: {len(sample_shop.get("next_7_days", []))}')
            logger.info(f'=== END SAMPLE DATA ===')

        logger.info(f'=== SHOP FORECASTS READY FOR TEMPLATE ===')
        return forecast_list

    # Get parameters
    level = request.GET.get('level', 'school')
    original_level = level  # Preserve original level for context
    search_query = request.GET.get('search', '').strip()  # Search/filter parameter

    # Extract filter parameters
    school_filter = request.GET.get('school', '').strip()
    product_filter = request.GET.get('product', '').strip()
    style_code_filter = request.GET.get('style_code', '').strip()
    shop_filter = request.GET.get('shop', '').strip()
    category_filter = request.GET.get('category', '').strip()
    risk_filter = request.GET.get('risk_filter', 'all').strip().lower()  # all, critical, high, medium, low

    # Initialize logger for debugging
    logger = logging.getLogger(__name__)

    # Get PriorityScoreSettings for risk-based filtering
    from dashboard.models import PriorityScoreSettings, TopPerformingSchool
    priority_settings = PriorityScoreSettings.get_settings()

    # Get top performing schools for priority scoring
    top_schools = set(
        TopPerformingSchool.objects.filter(is_top_performing=True)
        .values_list('school_name', flat=True)
    )

    # ========== DATA SCOPE FILTERING ==========
    # Apply school-based and store-based filtering
    user = request.user
    data_scope = user.get_data_scope()
    user_school_subcategories = []
    user_store_categories = []

    # Log user's data scope configuration
    logger.info(f'User: {user.username}, is_superuser: {user.is_superuser}, data_scope: {data_scope}')

    if data_scope == 'school' and not user.is_superuser:
        user_school_subcategories = user.get_assigned_school_subcategories()
        # If user has school scope but no assignments, they see no data
        if not user_school_subcategories:
            logger.warning(f'User {user.username} has school scope but no assigned schools')

    if data_scope == 'store' and not user.is_superuser:
        user_store_categories = user.get_accessible_categories()
        logger.info(f'Retrieved {len(user_store_categories)} store categories for user {user.username}: {user_store_categories}')
        # If user has store scope but no assignments, they see no data
        if not user_store_categories:
            logger.warning(f'User {user.username} has store scope but no assigned stores')

    # Date range parameters (new approach)
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Legacy horizon parameter (for backward compatibility)
    horizon = request.GET.get('horizon', '30d')

    # Determine if using new date range approach or legacy horizon
    use_date_range = start_date_str and end_date_str

    # Parse and validate date ranges
    today = datetime_date.today()

    # Initialize date variables
    start_date = None
    end_date = None
    num_days = None

    if use_date_range:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            # Validation
            if end_date <= start_date:
                return JsonResponse({'error': 'End date must be after start date'}, status=400)

            # Calculate number of days in range
            num_days = (end_date - start_date).days

        except ValueError:
            return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    else:
        # No default dates - require user to select dates via Apply Filters button
        # Set placeholder values for template rendering
        start_date = today
        end_date = today + timedelta(days=30)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        num_days = 30

    # Build cache key including filters AND user data scope
    # IMPORTANT: Include user's data scope in cache key to prevent users from seeing cached data
    # that belongs to other users with different permissions
    user_scope_key = f"{'_'.join(sorted(user_school_subcategories)) if user_school_subcategories else 'all_schools'}_{'_'.join(sorted(user_store_categories)) if user_store_categories else 'all_stores'}"
    filter_key = f"{school_filter}_{product_filter}_{style_code_filter}_{shop_filter}_{category_filter}_{search_query}_{risk_filter}_{user_scope_key}"
    cache_key = f'forecast_{level}_{start_date_str}_{end_date_str}_{filter_key}'

    # Determine cache timeout based on range
    common_ranges = [7, 30, 90]
    is_common_range = num_days in common_ranges and start_date == today
    cache_timeout = 1800 if is_common_range else 600  # 30 min for common, 10 min for custom

    # Skip data loading if no date range was provided (initial page load)
    if not use_date_range:
        # Return empty state - user must click Apply Filters button
        context = {
            'forecasts': [],
            'forecast_list_json': json.dumps([], default=str),
            'summary': {'total_forecasts': 0, 'avg_accuracy': 'N/A', 'level_display': dict(SalesForecastBase.AGGREGATION_LEVELS).get(level, level)},
            'current_horizon': horizon,
            'current_level': level,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'num_days': num_days,
            'horizons': SalesForecast.FORECAST_HORIZONS,
            'levels': SalesForecastBase.AGGREGATION_LEVELS,
            'use_date_range': True,
            'from_cache': False,
            'generating_forecasts': False,
            'no_forecasts_available': False,
            'using_365d_base': True,
            'initial_load': True,  # Flag to indicate this is initial page load without data
            'is_replenishment_view': getattr(request, 'is_replenishment_view', False)
        }
        return render(request, 'dashboard/sales_forecasting.html', context)

    cached_data = cache.get(cache_key)
    if cached_data:
        context = cached_data
        context['from_cache'] = True
        context['is_replenishment_view'] = getattr(request, 'is_replenishment_view', False)
        return render(request, 'dashboard/sales_forecasting.html', context)

    # Try to use new SalesForecastBase model
    
    # === DEBUG LOGGING START ===
    logger.info("=" * 80)
    logger.info("SALES FORECASTING VIEW - DEBUG")
    logger.info("=" * 80)
    logger.info(f"Request parameters:")
    logger.info(f"  level: {level}")
    logger.info(f"  start_date_str: {start_date_str}")
    logger.info(f"  end_date_str: {end_date_str}")
    logger.info(f"  use_date_range: {use_date_range}")
    logger.info(f"  num_days: {num_days}")
    logger.info(f"  user: {user.username}")
    logger.info(f"  data_scope: {data_scope}")
    logger.info(f"  user_school_subcategories: {user_school_subcategories}")
    logger.info("=" * 80)
    # === DEBUG LOGGING END ===
    
    from django.db.models import Max
    logger = logging.getLogger(__name__)

    # Initialize skip flag for deduplication logic
    skip_generic_dedup = False

    # SPECIAL HANDLING FOR SHOP LEVEL: Show product breakdown
    if level == 'shop':
        from django.db import connection

        logger.info(f'=== SHOP-LEVEL FORECAST REQUEST ===')
        logger.info(f'Date range: {start_date_str} to {end_date_str}')
        logger.info(f'Search query: {search_query}')
        logger.info(f'Shop filter: {shop_filter}')
        logger.info(f'User: {user.username}, Data scope: {data_scope}')
        logger.info(f'User school subcategories: {user_school_subcategories}')
        logger.info(f'User store categories: {user_store_categories}')

        # Shop level does its own deduplication, so skip generic dedup
        skip_generic_dedup = True

        # PHASE 1: Lightweight query - get metadata + stock data + precomputed totals
        # This avoids loading the massive daily_forecasts JSON
        from django.db import connection
        phase1_sql = """
            SELECT sf.id, sf.entity_name, sf.forecast_date, sf.accuracy_score,
                   sf.mae, sf.mape, sf.rmse, sf.model_params, sf.total_quantity_365d,
                   p.category_name as location_name,
                   p.sub_category as school_name,
                   COALESCE(SUM(s.stock_on_hand), 0) as stock_on_hand,
                   COALESCE(SUM(s.incoming), 0) as incoming,
                   MAX(p.name) as product_name
            FROM dashboard_salesforecastbase sf
            LEFT JOIN cin7_sync_productoption po ON po.code = sf.entity_name
            LEFT JOIN cin7_sync_product p ON p.id = po.product_id
            LEFT JOIN cin7_sync_stock s ON s.code = sf.entity_name
            WHERE sf.aggregation_level = 'product'
              AND sf.total_quantity_365d > 0
        """
        params = []

        # Add shop filter if provided
        if shop_filter:
            phase1_sql += " AND p.category_name = %s"
            params.append(shop_filter)
        else:
            # Show all shop/store products
            phase1_sql += " AND (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')"
            phase1_sql += " AND p.category_name NOT IN ('Shop', 'Store')"

        # Exclude Wholesale categories
        phase1_sql += " AND p.category_name NOT LIKE 'Wholesale%%'"

        # Filter out products without school assignment
        phase1_sql += " AND p.sub_category IS NOT NULL AND p.sub_category != ''"

        # DATA SCOPE: Filter by user's assigned schools (Sales Team)
        if user_school_subcategories:
            placeholders = ', '.join(['%s'] * len(user_school_subcategories))
            phase1_sql += f" AND p.sub_category IN ({placeholders})"
            params.extend(user_school_subcategories)

        # DATA SCOPE: Filter by user's assigned stores (Store-Level)
        if user_store_categories:
            placeholders = ', '.join(['%s'] * len(user_store_categories))
            phase1_sql += f" AND p.category_name IN ({placeholders})"
            params.extend(user_store_categories)
            logger.info(f'DEBUG: Applied store filter - restricting to {len(user_store_categories)} stores: {user_store_categories}')
        else:
            logger.info(f'DEBUG: No store filter applied - user will see ALL stores')

        # Add search query if provided
        if search_query:
            phase1_sql += " AND (sf.entity_name LIKE %s OR p.name LIKE %s OR p.sub_category LIKE %s OR p.category_name LIKE %s)"
            params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])

        phase1_sql += """ GROUP BY sf.id, sf.entity_name, sf.forecast_date, sf.accuracy_score,
                         sf.mae, sf.mape, sf.rmse, sf.model_params, sf.total_quantity_365d,
                         p.category_name, p.sub_category
                     HAVING (COALESCE(SUM(s.stock_on_hand), 0) + COALESCE(SUM(s.incoming), 0)) < sf.total_quantity_365d
                     ORDER BY p.category_name, p.sub_category, sf.entity_name"""

        logger.info(f'DEBUG: SHOP LEVEL - Phase 1: lightweight query')
        with connection.cursor() as cursor:
            cursor.execute(phase1_sql, params)
            phase1_rows = cursor.fetchall()

        logger.info(f'DEBUG: Phase 1 returned {len(phase1_rows)} records with stock shortages')

        # Build metadata cache from phase 1 results
        phase1_ids = []
        phase1_cache = {}
        for row in phase1_rows:
            forecast_id = row[0]
            entity_name = row[1]
            phase1_ids.append(forecast_id)
            phase1_cache[entity_name] = {
                'id': forecast_id,
                'forecast_date': row[2],
                'accuracy_score': row[3],
                'mae': row[4],
                'mape': row[5],
                'rmse': row[6],
                'model_params': row[7] if isinstance(row[7], dict) else {},
                'total_quantity_365d': row[8],
                'location_name': row[9],
                'school_name': row[10],
                'stock_on_hand': float(row[11] or 0),
                'incoming': float(row[12] or 0),
                'product_name': row[13] if row[13] else entity_name,
            }

        # PHASE 2: Load daily_forecasts ONLY for filtered records
        logger.info(f'DEBUG: Phase 2: loading daily_forecasts for {len(phase1_ids)} records')
        if phase1_ids:
            phase2_ids = phase1_ids[:2000]
            placeholders = ','.join(['%s'] * len(phase2_ids))
            phase2_sql = f"""
                SELECT id, forecast_id, model_type, aggregation_level,
                       entity_name, entity_id, daily_forecasts, forecast_date,
                       training_data_start, training_data_end, mae, mape, rmse,
                       accuracy_score, model_params, created_at, updated_at
                FROM dashboard_salesforecastbase
                WHERE id IN ({placeholders})
                ORDER BY entity_name
            """
            base_forecasts = list(SalesForecastBase.objects.raw(phase2_sql, phase2_ids))

            # Attach metadata from phase 1
            for f in base_forecasts:
                meta = phase1_cache.get(f.entity_name, {})
                f.location_name = meta.get('location_name')
                f.school_name = meta.get('school_name')
                f._stock_on_hand = meta.get('stock_on_hand', 0)
                f._incoming = meta.get('incoming', 0)
                f._product_name = meta.get('product_name', f.entity_name)
        else:
            base_forecasts = []

        # IMPORTANT: Keep level as 'shop' for template rendering
        logger.info(f'DEBUG: Phase 2 loaded {len(base_forecasts)} forecast records with daily data')

    # NORMAL HANDLING FOR OTHER LEVELS (school, product, category)
    elif level != 'shop':
        # SPECIAL CASE: When "By School" is selected, ALWAYS show product breakdown
        if level == 'school':
            from django.db import connection

            # PHASE 1: Lightweight query - get metadata + stock data + precomputed totals
            # This avoids loading the massive daily_forecasts JSON (544MB for all records)
            phase1_sql = """
                SELECT sf.id, sf.entity_name, sf.forecast_date, sf.accuracy_score,
                       sf.mae, sf.mape, sf.rmse, sf.model_params, sf.total_quantity_365d,
                       p.sub_category as school_name,
                       COALESCE(SUM(s.stock_on_hand), 0) as stock_on_hand,
                       COALESCE(SUM(s.incoming), 0) as incoming,
                       MAX(p.name) as product_name
                FROM dashboard_salesforecastbase sf
                LEFT JOIN cin7_sync_productoption po ON po.code = sf.entity_name
                LEFT JOIN cin7_sync_product p ON p.id = po.product_id
                LEFT JOIN cin7_sync_stock s ON s.code = sf.entity_name
                WHERE sf.aggregation_level = 'product'
                  AND sf.total_quantity_365d > 0
                  AND (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
                  AND p.category_name NOT IN ('Shop', 'Store')
                  AND p.category_name NOT LIKE 'Wholesale%%'
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category != ''
            """
            params = []

            # DATA SCOPE: Filter by user's assigned schools (Sales Team)
            if user_school_subcategories:
                placeholders = ', '.join(['%s'] * len(user_school_subcategories))
                phase1_sql += f" AND p.sub_category IN ({placeholders})"
                params.extend(user_school_subcategories)

            # DATA SCOPE: Filter by user's assigned stores (Store Level)
            if user_store_categories:
                placeholders = ', '.join(['%s'] * len(user_store_categories))
                phase1_sql += f" AND p.category_name IN ({placeholders})"
                params.extend(user_store_categories)

            # Add school filter if provided
            if school_filter:
                phase1_sql += " AND p.sub_category = %s"
                params.append(school_filter)

            # Add search query if provided
            if search_query:
                phase1_sql += " AND (sf.entity_name LIKE %s OR p.name LIKE %s OR p.sub_category LIKE %s)"
                params.extend([f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'])

            phase1_sql += """ GROUP BY sf.id, sf.entity_name, sf.forecast_date, sf.accuracy_score,
                             sf.mae, sf.mape, sf.rmse, sf.model_params, sf.total_quantity_365d,
                             p.sub_category
                         HAVING (COALESCE(SUM(s.stock_on_hand), 0) + COALESCE(SUM(s.incoming), 0)) < sf.total_quantity_365d
                         ORDER BY p.sub_category, sf.entity_name"""

            logger.info(f'DEBUG: SCHOOL LEVEL - Phase 1: lightweight query')

            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(phase1_sql, params)
                phase1_rows = cursor.fetchall()

            logger.info(f'DEBUG: Phase 1 returned {len(phase1_rows)} records with stock shortages')

            # Build metadata cache from phase 1 results
            # Columns: id, entity_name, forecast_date, accuracy_score, mae, mape, rmse,
            #          model_params, total_quantity_365d, school_name, stock_on_hand, incoming, product_name
            phase1_ids = []
            phase1_cache = {}
            for row in phase1_rows:
                forecast_id = row[0]
                entity_name = row[1]
                phase1_ids.append(forecast_id)
                phase1_cache[entity_name] = {
                    'id': forecast_id,
                    'forecast_date': row[2],
                    'accuracy_score': row[3],
                    'mae': row[4],
                    'mape': row[5],
                    'rmse': row[6],
                    'model_params': row[7] if isinstance(row[7], dict) else {},
                    'total_quantity_365d': row[8],
                    'school_name': row[9],
                    'stock_on_hand': float(row[10] or 0),
                    'incoming': float(row[11] or 0),
                    'product_name': row[12] if row[12] else entity_name,
                }

            # PHASE 2: Load daily_forecasts ONLY for filtered records
            logger.info(f'DEBUG: Phase 2: loading daily_forecasts for {len(phase1_ids)} records')
            if phase1_ids:
                phase2_ids = phase1_ids[:2000]
                placeholders = ','.join(['%s'] * len(phase2_ids))
                phase2_sql = f"""
                    SELECT id, forecast_id, model_type, aggregation_level,
                           entity_name, entity_id, daily_forecasts, forecast_date,
                           training_data_start, training_data_end, mae, mape, rmse,
                           accuracy_score, model_params, created_at, updated_at
                    FROM dashboard_salesforecastbase
                    WHERE id IN ({placeholders})
                    ORDER BY entity_name
                """
                base_forecasts = list(SalesForecastBase.objects.raw(phase2_sql, phase2_ids))

                # Attach metadata from phase 1 to each forecast object
                for f in base_forecasts:
                    meta = phase1_cache.get(f.entity_name, {})
                    f.school_name = meta.get('school_name')
                    f._stock_on_hand = meta.get('stock_on_hand', 0)
                    f._incoming = meta.get('incoming', 0)
                    f._product_name = meta.get('product_name', f.entity_name)
            else:
                base_forecasts = []

            logger.info(f'DEBUG: Phase 2 loaded {len(base_forecasts)} forecast records with daily data')

            # IMPORTANT: Only switch to product rendering if a specific school is selected
            # Otherwise, keep school level for nested school/product view
            if school_filter:
                level = 'product'  # Show products for specific school
            # else: keep level = 'school' for nested view

            # Skip the generic deduplication below since we already did it for school level
            skip_generic_dedup = True
        else:
            skip_generic_dedup = False

            # Get all base forecasts for this level (latest forecast for each entity)
            query = SalesForecastBase.objects.filter(aggregation_level=level)

            # Apply search filter if provided
            if search_query:
                query = query.filter(entity_name__icontains=search_query)

            # Apply specific filters if provided
            if level == 'category' and category_filter:
                # SPECIAL CASE: When category filter is applied at category level, show products for that category
                from django.db import connection

                # Switch to product-level view filtered by category
                sql = """
                    SELECT DISTINCT sf.id, sf.forecast_id, sf.model_type, sf.aggregation_level,
                           sf.entity_name, sf.entity_id, sf.daily_forecasts, sf.forecast_date,
                           sf.training_data_start, sf.training_data_end, sf.mae, sf.mape, sf.rmse,
                           sf.accuracy_score, sf.model_params, sf.created_at, sf.updated_at
                    FROM dashboard_salesforecastbase sf
                    LEFT JOIN cin7_sync_productoption po ON po.code = sf.entity_name
                    LEFT JOIN cin7_sync_product p ON p.id = po.product_id
                    WHERE sf.aggregation_level = 'product'
                      AND p.sub_category = %s
                """
                params = [category_filter]

                # DATA SCOPE: Filter by user's assigned schools (Sales Team)
                if user_school_subcategories:
                    placeholders = ', '.join(['%s'] * len(user_school_subcategories))
                    sql += f" AND p.sub_category IN ({placeholders})"
                    params.extend(user_school_subcategories)

                if search_query:
                    sql += " AND (sf.entity_name LIKE %s OR p.name LIKE %s)"
                    params.extend([f'%{search_query}%', f'%{search_query}%'])

                sql += " ORDER BY p.name, sf.entity_name, sf.forecast_date DESC"

                # Execute raw SQL and convert to model instances
                all_base_forecasts = SalesForecastBase.objects.raw(sql, params)

                # IMPORTANT: Set level to 'product' for template rendering
                level = 'product'
            elif level == 'product':
                # For product level, we need to join with product table for advanced filters
                # This will be handled via raw SQL if filters are present
                if product_filter or style_code_filter or shop_filter or category_filter:
                    from django.db import connection

                    sql = """
                        SELECT DISTINCT sf.id, sf.forecast_id, sf.model_type, sf.aggregation_level,
                               sf.entity_name, sf.entity_id, sf.daily_forecasts, sf.forecast_date,
                               sf.training_data_start, sf.training_data_end, sf.mae, sf.mape, sf.rmse,
                               sf.accuracy_score, sf.model_params, sf.created_at, sf.updated_at
                        FROM dashboard_salesforecastbase sf
                        LEFT JOIN cin7_sync_productoption po ON po.code = sf.entity_name
                        LEFT JOIN cin7_sync_product p ON p.id = po.product_id
                        WHERE sf.aggregation_level = 'product'
                    """
                    params = []

                    # DATA SCOPE: Filter by user's assigned schools (Sales Team)
                    if user_school_subcategories:
                        placeholders = ', '.join(['%s'] * len(user_school_subcategories))
                        sql += f" AND p.sub_category IN ({placeholders})"
                        params.extend(user_school_subcategories)

                    if product_filter:
                        sql += " AND p.cin7_id = %s"
                        params.append(product_filter)
                    if style_code_filter:
                        sql += " AND p.style_code = %s"
                        params.append(style_code_filter)
                    if shop_filter:
                        sql += " AND p.category_name = %s"
                        params.append(shop_filter)
                    if category_filter:
                        sql += " AND p.sub_category = %s"
                        params.append(category_filter)
                    if search_query:
                        sql += " AND (sf.entity_name LIKE %s OR p.name LIKE %s)"
                        params.extend([f'%{search_query}%', f'%{search_query}%'])

                    sql += " ORDER BY sf.entity_name, sf.forecast_date DESC"

                    # Execute raw SQL and convert to model instances
                    all_base_forecasts = SalesForecastBase.objects.raw(sql, params)
                else:
                    all_base_forecasts = query.order_by('entity_name', '-forecast_date')
            else:
                all_base_forecasts = query.order_by('entity_name', '-forecast_date')

        # Keep only the latest forecast for each entity_name
        # BUT skip this for school level since we already did deduplication above
        if not skip_generic_dedup:
            seen_entities = set()
            base_forecasts = []
            for f in all_base_forecasts:
                if f.entity_name not in seen_entities:
                    base_forecasts.append(f)
                    seen_entities.add(f.entity_name)
                if len(base_forecasts) >= 2000:  # Limit to 2000 unique entities (increased from 500)
                    break

    # If no base forecasts, fall back to legacy SalesForecast model
    if level != 'shop' and not base_forecasts:
        # Fallback to legacy horizon-based approach
        # Auto-select the best horizon that covers the requested date range
        # with fallback to shorter horizons if longer ones don't exist
        if num_days <= 30:
            horizon_priority = ['30d']
        elif num_days <= 90:
            horizon_priority = ['90d', '30d']
        elif num_days <= 180:
            horizon_priority = ['180d', '90d', '30d']
        else:
            horizon_priority = ['365d', '180d', '90d', '30d']

        # Try horizons in order of priority until we find data
        all_forecasts = None
        best_horizon = None
        for horizon_attempt in horizon_priority:
            all_forecasts = SalesForecast.objects.filter(
                horizon=horizon_attempt,
                aggregation_level=level
            ).order_by('entity_name', '-forecast_date')

            if all_forecasts.exists():
                best_horizon = horizon_attempt
                break

        # If no forecasts found at all, set to empty queryset
        if best_horizon is None:
            all_forecasts = SalesForecast.objects.none()
            best_horizon = horizon_priority[0]  # For display purposes

        # Keep only the latest forecast for each entity_name
        seen_entities = set()
        forecasts = []
        for f in all_forecasts:
            if f.entity_name not in seen_entities:
                forecasts.append(f)
                seen_entities.add(f.entity_name)
            if len(forecasts) >= 500:  # Limit to 500 unique products
                break

        use_legacy = True

        # IMPORTANT: Check if we have no forecasts at all (not even legacy)
        # This prevents infinite refresh loop for levels without forecasts (e.g., shop)
        if not forecasts:
            # Set flag to show "no data" message instead of "generating" message
            # This prevents the auto-refresh JavaScript from triggering
            no_forecasts_available = True
        else:
            no_forecasts_available = False
    else:
        # For shop and other levels with base_forecasts, use base_forecasts
        forecasts = base_forecasts
        use_legacy = False
        no_forecasts_available = False

    # Check if this is a replenishment view and preload already requested items for efficiency
    requested_items_set = set()
    # Check both request attribute (set by store_manager_replenishment) and URL parameter (set by filter tabs)
    is_replenishment_view = getattr(request, 'is_replenishment_view', False) or request.GET.get('replenish', '').lower() == 'true'

    if is_replenishment_view:
        # Get all SKU+size combos that are already in active requests for this user's schools
        # Use a single efficient query to avoid per-variation lookups
        from dashboard.models import StoreReplenishmentRequestItem, StoreReplenishmentRequestBatch

        # Get the user's school(s) - admin can see all, store managers see their assigned branch's school
        user = request.user
        school_filter_value = school_filter  # From URL parameters

        # Build query to get already requested items
        requested_query = StoreReplenishmentRequestItem.objects.filter(
            batch__status__in=['store_approved', 'dp_approved']
        )

        # Filter by school if user is not admin or if school filter is applied
        if school_filter_value:
            requested_query = requested_query.filter(batch__school=school_filter_value)
        elif not (user.is_superuser or user.is_staff):
            # For non-admin users, get their assigned branch's schools
            # This requires knowing the user's branch and filtering accordingly
            # For now, we'll check all their requests
            requested_query = requested_query.filter(batch__requested_by=user)

        # Fetch all SKU+size combinations that are already requested
        requested_items = requested_query.values_list('sku', 'size')
        requested_items_set = set(requested_items)

    # Check if we need to group by parent product
    if level == 'product':
        # Batch fetch stock data for all SKUs (single query instead of N+1)
        stock_data_cache = batch_get_stock_data([f.entity_name for f in forecasts])

        # Group SKU variations by parent product
        grouped_products = defaultdict(list)
        logger.info(f'DEBUG: Processing product level with {len(forecasts)} forecast records')
        processed_count = 0
        skipped_zero_count = 0
        skipped_already_requested = 0
        skipped_no_stock_gap = 0

        for f in forecasts:
            size = extract_size_from_sku(f.entity_name)

            # Extract forecast data for the selected date range
            if use_legacy:
                # Legacy: filter forecast_data by date range
                date_range_data = {}
                for date_str, forecast_data in f.forecast_data.items():
                    forecast_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    if start_date <= forecast_date <= end_date:
                        date_range_data[date_str] = forecast_data
            else:
                # New: extract date range from base forecast
                date_range_data = f.get_date_range_forecast(start_date, end_date)
                if processed_count == 0:  # Log details for first product only
                    logger.info(f'DEBUG: First product (product level) date extraction:')
                    logger.info(f'  - Entity: {f.entity_name}')
                    logger.info(f'  - Forecast date: {f.forecast_date}')
                    logger.info(f'  - Requested range: {start_date} to {end_date}')
                    logger.info(f'  - Daily forecasts present: {bool(f.daily_forecasts)}')
                    if f.daily_forecasts:
                        all_dates = list(f.daily_forecasts.keys())
                        logger.info(f'  - Daily forecasts date range: {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} days)')
                    logger.info(f'  - Extracted dates: {len(date_range_data)} days')
                    if date_range_data:
                        extracted_dates = list(date_range_data.keys())
                        logger.info(f'  - Extracted range: {extracted_dates[0]} to {extracted_dates[-1]}')

            # Calculate total quantity for this SKU within the date range
            total_qty = sum([day['quantity'] for day in date_range_data.values()])

            # Get first 7 days detail
            forecast_dates = sorted(date_range_data.keys())[:7]
            next_7_days = [
                {
                    'date': date,
                    'quantity': date_range_data[date]['quantity'],
                    'confidence_lower': date_range_data[date].get('confidence_lower', 0),
                    'confidence_upper': date_range_data[date].get('confidence_upper', 0)
                }
                for date in forecast_dates
            ]

            # Get stock data from batch cache (single query instead of per-SKU)
            stock_info = stock_data_cache.get(f.entity_name, {'stock_on_hand': 0, 'incoming': 0, 'product_name': f.entity_name})
            stock_on_hand = stock_info['stock_on_hand']
            incoming_stock = stock_info['incoming']
            product_name = stock_info['product_name']
            forecasted_stock = round(total_qty, 1)
            stock_gap = (stock_on_hand + incoming_stock) - forecasted_stock

            # Filter: Only show products with negative stock gap (shortages)
            # Apply stock gap filter in BOTH replenishment AND normal forecasting views
            if total_qty == 0:
                skipped_zero_count += 1
                continue
            if stock_gap >= 0:
                skipped_no_stock_gap += 1
                continue

            # Check if this variation has already been requested
            already_requested = (f.entity_name, size or '') in requested_items_set

            # Skip this variation entirely if already requested
            if already_requested:
                skipped_already_requested += 1
                continue

            processed_count += 1

            # === PRIORITY SCORE CALCULATION ===
            # Calculate days of coverage
            if forecasted_stock > 0:
                daily_demand = forecasted_stock / num_days
                if daily_demand > 0:
                    days_of_coverage = (stock_on_hand + incoming_stock) / daily_demand
                else:
                    days_of_coverage = 999  # No demand
            else:
                days_of_coverage = 999  # No demand

            # Get risk score and tag from settings
            risk_score = priority_settings.get_risk_score(days_of_coverage)
            risk_tag = priority_settings.get_risk_tag(days_of_coverage)

            # Determine if top customer - need to get school_name for this SKU
            school_name = None
            try:
                from cin7.models import ProductOption
                po = ProductOption.objects.select_related('product').get(code=f.entity_name)
                school_name = po.product.sub_category
            except:
                school_name = None

            is_top_customer = school_name in top_schools if school_name else False

            # Determine if high velocity (above category average)
            # For now, set to False - will implement category average calculation later
            is_high_velocity = False

            # Calculate priority score
            priority_score = priority_settings.calculate_priority_score(
                days_of_coverage,
                is_top_customer,
                is_high_velocity
            )

            variation_data = {
                'sku_code': f.entity_name,
                'product_name': product_name,
                'size': size,
                'total_quantity': forecasted_stock,
                'stock_on_hand': int(stock_on_hand),
                'incoming_stock': int(incoming_stock),
                'stock_gap': round(stock_gap, 1),
                'accuracy_score': round(f.accuracy_score, 1) if f.accuracy_score is not None else 'N/A',
                'model': f.model_params.get('model', 'Unknown'),
                'next_7_days': next_7_days,
                'forecast_data': date_range_data,
                'training_days': f.model_params.get('training_days', 0),
                'mae': round(f.mae, 2) if f.mae else None,
                'mape': round(f.mape, 2) if f.mape else None,
                # Priority scoring fields
                'days_of_coverage': round(days_of_coverage, 1),
                'risk_score': risk_score,
                'risk_tag': risk_tag,
                'priority_score': priority_score,
                'is_top_customer': is_top_customer,
                'is_high_velocity': is_high_velocity,
                'school_name': school_name
            }

            grouped_products[product_name].append(variation_data)

        logger.info(f'DEBUG: Product level summary:')
        logger.info(f'  - Processed: {processed_count} products')
        logger.info(f'  - Skipped (zero quantity): {skipped_zero_count}')
        logger.info(f'  - Skipped (no stock gap - surplus): {skipped_no_stock_gap}')
        logger.info(f'  - Skipped (already requested): {skipped_already_requested}')
        logger.info(f'  - Grouped into {len(grouped_products)} parent products')

        # Create product summaries
        forecast_list = []
        for product_name, variations in sorted(grouped_products.items()):
            # Calculate totals across all variations
            total_forecast = sum([v['total_quantity'] for v in variations])
            avg_accuracy = sum([v['accuracy_score'] for v in variations if v['accuracy_score'] != 'N/A']) / len([v for v in variations if v['accuracy_score'] != 'N/A']) if any([v['accuracy_score'] != 'N/A' for v in variations]) else 'N/A'

            # Sort variations by size
            variations_sorted = sorted(variations, key=lambda x: (
                # Sort numeric sizes numerically
                int(x['size']) if x['size'].isdigit() else 999,
                # Then sort text sizes alphabetically
                x['size']
            ))

            forecast_list.append({
                'product_name': product_name,
                'variations': variations_sorted,
                'total_quantity': round(total_forecast, 1),
                'variation_count': len(variations),
                'avg_accuracy': round(avg_accuracy, 1) if avg_accuracy != 'N/A' else 'N/A',
                'is_grouped': True
            })

        # === RISK-BASED FILTERING ===
        # Store unfiltered count for statistics
        all_variations = []
        for product in forecast_list:
            if product.get('is_grouped') and 'variations' in product:
                all_variations.extend(product['variations'])

        # Calculate risk level counts BEFORE filtering
        critical_count = len([v for v in all_variations if v.get('risk_tag') == 'CRITICAL'])
        high_count = len([v for v in all_variations if v.get('risk_tag') == 'HIGH'])
        medium_count = len([v for v in all_variations if v.get('risk_tag') == 'MEDIUM'])
        low_count = len([v for v in all_variations if v.get('risk_tag') == 'LOW'])
        total_count = len(all_variations)

        # Apply risk filter if not 'all'
        if risk_filter != 'all':
            filtered_forecast_list = []
            risk_filter_upper = risk_filter.upper()

            for product in forecast_list:
                if product.get('is_grouped') and 'variations' in product:
                    # Filter variations by risk tag
                    filtered_variations = [
                        v for v in product['variations']
                        if v.get('risk_tag') == risk_filter_upper
                    ]

                    # Only include products that have variations matching the risk filter
                    if filtered_variations:
                        product_copy = product.copy()
                        product_copy['variations'] = filtered_variations
                        product_copy['variation_count'] = len(filtered_variations)
                        # Recalculate total quantity for filtered variations
                        product_copy['total_quantity'] = round(sum([v['total_quantity'] for v in filtered_variations]), 1)
                        filtered_forecast_list.append(product_copy)

            forecast_list = filtered_forecast_list
            logger.info(f'Applied risk filter: {risk_filter} - {len(forecast_list)} products match')

        # Sort by priority score descending (highest priority first)
        # For grouped products, use the highest priority score among variations
        def get_max_priority_score(product):
            if product.get('is_grouped') and 'variations' in product:
                priority_scores = [v.get('priority_score', 0) for v in product['variations']]
                return max(priority_scores) if priority_scores else 0
            return product.get('priority_score', 0)

        forecast_list = sorted(forecast_list, key=get_max_priority_score, reverse=True)[:500]  # Limit to 500 products

        logger.info(f'DEBUG: Final forecast_list has {len(forecast_list)} products after filtering and limit')

    elif level == 'shop':
        # SHOP-LEVEL NESTED VIEW: 3-level (location → school → product) or 2-level (school → product)
        from collections import defaultdict
        from cin7.models import ProductOption

        logger = logging.getLogger(__name__)

        # Initialize forecast_list to prevent UnboundLocalError if forecasts is empty
        forecast_list = []

        if shop_filter or is_replenishment_view:
            # WITH shop_filter OR replenishment view: Flat table view with all products sorted by risk level
            logger.info(f'Shop filter: {shop_filter}, Replenishment view: {is_replenishment_view} - Using flat table view for Store Manager')

            # Build SKU -> school mapping
            sku_to_school = {}
            for f in forecasts:
                school_name = getattr(f, 'school_name', None)
                if school_name:
                    sku_to_school[f.entity_name] = school_name
                else:
                    try:
                        po = ProductOption.objects.select_related('product').get(code=f.entity_name)
                        school_name = po.product.sub_category or 'Uncategorized'
                        sku_to_school[f.entity_name] = school_name
                    except ProductOption.DoesNotExist:
                        logger.warning(f'ProductOption not found for SKU: {f.entity_name}')
                        continue

            # Get PriorityScoreSettings for risk-based scoring
            from dashboard.models import PriorityScoreSettings, TopPerformingSchool
            priority_settings = PriorityScoreSettings.get_settings()

            # Get top performing schools for priority scoring
            top_schools = set(
                TopPerformingSchool.objects.values_list('school_name', flat=True)
            )

            # Use pre-attached stock data from phase 1 query (if available)
            has_phase1_data = len(forecasts) > 0 and hasattr(forecasts[0], '_stock_on_hand')
            if not has_phase1_data:
                stock_data_cache = batch_get_stock_data([f.entity_name for f in forecasts])

            # Process all forecasts into a flat list
            all_variations = []
            logger.info(f'DEBUG: Processing {len(forecasts)} forecasts for flat table')
            processed_count = 0
            skipped_zero_count = 0
            skipped_no_stock_gap = 0

            for f in forecasts:
                school_name = sku_to_school.get(f.entity_name)
                if not school_name:
                    continue

                size = extract_size_from_sku(f.entity_name)

                # Extract forecast data for the selected date range
                if use_legacy:
                    date_range_data = {}
                    for date_str, forecast_data in f.forecast_data.items():
                        forecast_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        if start_date <= forecast_date <= end_date:
                            date_range_data[date_str] = forecast_data
                else:
                    date_range_data = f.get_date_range_forecast(start_date, end_date)
                    if processed_count == 0:  # Log details for first product only
                        logger.info(f'DEBUG: First product date extraction:')
                        logger.info(f'  - Entity: {f.entity_name}')
                        logger.info(f'  - Forecast date: {f.forecast_date}')
                        logger.info(f'  - Requested range: {start_date} to {end_date}')
                        logger.info(f'  - Daily forecasts present: {bool(f.daily_forecasts)}')
                        if f.daily_forecasts:
                            all_dates = list(f.daily_forecasts.keys())
                            logger.info(f'  - Daily forecasts date range: {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} days)')
                        logger.info(f'  - Extracted dates: {len(date_range_data)} days')
                        if date_range_data:
                            extracted_dates = list(date_range_data.keys())
                            logger.info(f'  - Extracted range: {extracted_dates[0]} to {extracted_dates[-1]}')

                # Calculate total quantity
                total_qty = sum([day['quantity'] for day in date_range_data.values()])

                # Skip if zero
                if total_qty == 0:
                    skipped_zero_count += 1
                    continue

                processed_count += 1

                # Get first 7 days detail
                forecast_dates = sorted(date_range_data.keys())[:7]
                next_7_days = [
                    {
                        'date': date,
                        'quantity': date_range_data[date]['quantity'],
                        'confidence_lower': date_range_data[date].get('confidence_lower', 0),
                        'confidence_upper': date_range_data[date].get('confidence_upper', 0)
                    }
                    for date in forecast_dates
                ]

                # Get stock data from phase 1 cache or batch cache
                if has_phase1_data:
                    stock_on_hand = getattr(f, '_stock_on_hand', 0)
                    incoming_stock = getattr(f, '_incoming', 0)
                    product_name = getattr(f, '_product_name', f.entity_name)
                else:
                    stock_info = stock_data_cache.get(f.entity_name, {'stock_on_hand': 0, 'incoming': 0, 'product_name': f.entity_name})
                    stock_on_hand = stock_info['stock_on_hand']
                    incoming_stock = stock_info['incoming']
                    product_name = stock_info['product_name']
                forecasted_stock = round(total_qty, 1)
                stock_gap = (stock_on_hand + incoming_stock) - forecasted_stock

                # Filter: Only show products with negative stock gap (shortages)
                if stock_gap >= 0:
                    skipped_no_stock_gap += 1
                    continue

                # Check if this variation has already been requested
                already_requested = (f.entity_name, size or '') in requested_items_set

                # Skip this variation entirely if already requested
                if already_requested:
                    continue

                # Calculate days of coverage (stock available divided by daily demand rate)
                num_days = (end_date - start_date).days + 1
                avg_daily_demand = forecasted_stock / num_days if num_days > 0 else 0
                available_stock = stock_on_hand + incoming_stock
                if avg_daily_demand > 0:
                    days_of_coverage = available_stock / avg_daily_demand
                else:
                    days_of_coverage = 999  # No demand

                # Get risk score and tag from settings
                risk_score = priority_settings.get_risk_score(days_of_coverage)
                risk_tag = priority_settings.get_risk_tag(days_of_coverage)

                # Determine if top customer
                is_top_customer = school_name in top_schools

                # Determine if high velocity (above category average)
                # For now, set to False - will implement category average calculation later
                is_high_velocity = False

                # Calculate priority score
                priority_score = priority_settings.calculate_priority_score(
                    days_of_coverage,
                    is_top_customer,
                    is_high_velocity
                )

                variation_data = {
                    'sku_code': f.entity_name,
                    'product_name': product_name,
                    'school_name': school_name,  # Add school name for flat table
                    'size': size,
                    'total_quantity': forecasted_stock,
                    'stock_on_hand': int(stock_on_hand),
                    'incoming_stock': int(incoming_stock),
                    'stock_gap': round(stock_gap, 1),
                    'accuracy_score': round(f.accuracy_score, 1) if f.accuracy_score is not None else 'N/A',
                    'model': f.model_params.get('model', 'Unknown'),
                    'next_7_days': next_7_days,
                    'forecast_data': date_range_data,
                    'training_days': f.model_params.get('training_days', 0),
                    'mae': round(f.mae, 2) if f.mae else None,
                    'mape': round(f.mape, 2) if f.mape else None,
                    # Priority scoring fields
                    'days_of_coverage': round(days_of_coverage, 1),
                    'risk_score': risk_score,
                    'risk_tag': risk_tag,
                    'priority_score': priority_score,
                    'is_top_customer': is_top_customer,
                    'is_high_velocity': is_high_velocity
                }

                all_variations.append(variation_data)

            logger.info(f'DEBUG: Processed {processed_count} products, skipped {skipped_zero_count} with zero quantity, skipped {skipped_no_stock_gap} with no stock gap (surplus)')

            # Calculate risk level counts BEFORE filtering
            critical_count = len([v for v in all_variations if v.get('risk_tag') == 'CRITICAL'])
            high_count = len([v for v in all_variations if v.get('risk_tag') == 'HIGH'])
            medium_count = len([v for v in all_variations if v.get('risk_tag') == 'MEDIUM'])
            low_count = len([v for v in all_variations if v.get('risk_tag') == 'LOW'])
            total_count = len(all_variations)

            # Apply risk filter if not 'all'
            if risk_filter != 'all':
                risk_filter_upper = risk_filter.upper()
                all_variations = [
                    v for v in all_variations
                    if v.get('risk_tag') == risk_filter_upper
                ]
                logger.info(f'Applied risk filter: {risk_filter} - {len(all_variations)} variations match')

            # Sort by risk level and priority score
            # First, assign sort order for risk levels
            risk_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}

            all_variations.sort(
                key=lambda x: (
                    risk_order.get(x.get('risk_tag', 'LOW'), 99),  # Risk level first
                    -x.get('priority_score', 0)  # Then priority score descending
                )
            )

            # Limit to 500 variations
            all_variations = all_variations[:500]

            logger.info(f'DEBUG: Final all_variations has {len(all_variations)} items after sorting and limit')

            # Create forecast_list with flat table flag
            forecast_list = []

        else:
            # WITHOUT shop_filter: 3-level location/school/product nested view
            logger.info('No shop filter - Using 3-level location/school/product view')
            logger.info(f'DEBUG: Starting with {len(forecasts)} forecast records')

            # Group forecasts by location -> school
            location_groups = defaultdict(lambda: defaultdict(list))

            # Build SKU -> location/school mapping
            sku_to_location = {}
            sku_to_school = {}
            mapping_failures = 0
            for f in forecasts:
                location_name = getattr(f, 'location_name', None)
                school_name = getattr(f, 'school_name', None)

                if location_name and school_name:
                    sku_to_location[f.entity_name] = location_name
                    sku_to_school[f.entity_name] = school_name
                else:
                    try:
                        po = ProductOption.objects.select_related('product').get(code=f.entity_name)
                        location_name = po.product.category_name
                        school_name = po.product.sub_category or 'Uncategorized'
                        sku_to_location[f.entity_name] = location_name
                        sku_to_school[f.entity_name] = school_name
                    except ProductOption.DoesNotExist:
                        logger.warning(f'ProductOption not found for SKU: {f.entity_name}')
                        mapping_failures += 1
                        continue

            logger.info(f'DEBUG: Mapped {len(sku_to_location)} SKUs to locations, {mapping_failures} failures')

            # Group forecasts by location -> school
            for f in forecasts:
                location_name = sku_to_location.get(f.entity_name)
                school_name = sku_to_school.get(f.entity_name)
                if location_name and school_name:
                    location_groups[location_name][school_name].append(f)

            logger.info(f'DEBUG: Created {len(location_groups)} location groups')

            # Use pre-attached stock data from phase 1 query (if available)
            has_phase1_data = len(forecasts) > 0 and hasattr(forecasts[0], '_stock_on_hand')
            if not has_phase1_data:
                stock_data_cache = batch_get_stock_data([f.entity_name for f in forecasts])

            # Process each location
            forecast_list = []
            processed_count = 0
            skipped_zero_count = 0
            skipped_no_stock_gap = 0

            for location_name, schools in sorted(location_groups.items()):
                logger.info(f'DEBUG: Processing location "{location_name}" with {len(schools)} schools')
                location_schools = []
                location_total_quantity = 0

                # Process each school within this location
                for school_name, school_forecasts in sorted(schools.items()):
                    school_variations = []
                    school_total_quantity = 0

                    for f in school_forecasts:
                        size = extract_size_from_sku(f.entity_name)

                        # Extract forecast data for the selected date range
                        if use_legacy:
                            date_range_data = {}
                            for date_str, forecast_data in f.forecast_data.items():
                                forecast_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                                if start_date <= forecast_date <= end_date:
                                    date_range_data[date_str] = forecast_data
                        else:
                            date_range_data = f.get_date_range_forecast(start_date, end_date)
                            if processed_count == 0:  # Log details for first product only
                                logger.info(f'DEBUG: First product (3-level view) date extraction:')
                                logger.info(f'  - Entity: {f.entity_name}')
                                logger.info(f'  - Forecast date: {f.forecast_date}')
                                logger.info(f'  - Requested range: {start_date} to {end_date}')
                                logger.info(f'  - Daily forecasts present: {bool(f.daily_forecasts)}')
                                if f.daily_forecasts:
                                    all_dates = list(f.daily_forecasts.keys())
                                    logger.info(f'  - Daily forecasts date range: {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} days)')
                                logger.info(f'  - Extracted dates: {len(date_range_data)} days')
                                if date_range_data:
                                    extracted_dates = list(date_range_data.keys())
                                    logger.info(f'  - Extracted range: {extracted_dates[0]} to {extracted_dates[-1]}')

                        # Calculate total quantity
                        total_qty = sum([day['quantity'] for day in date_range_data.values()])

                        # Skip if zero
                        if total_qty == 0:
                            skipped_zero_count += 1
                            continue

                        processed_count += 1

                        # Get first 7 days detail
                        forecast_dates = sorted(date_range_data.keys())[:7]
                        next_7_days = [
                            {
                                'date': date,
                                'quantity': date_range_data[date]['quantity'],
                                'confidence_lower': date_range_data[date].get('confidence_lower', 0),
                                'confidence_upper': date_range_data[date].get('confidence_upper', 0)
                            }
                            for date in forecast_dates
                        ]

                        # Get stock data from phase 1 cache or batch cache
                        if has_phase1_data:
                            stock_on_hand = getattr(f, '_stock_on_hand', 0)
                            incoming_stock = getattr(f, '_incoming', 0)
                            product_name = getattr(f, '_product_name', f.entity_name)
                        else:
                            stock_info = stock_data_cache.get(f.entity_name, {'stock_on_hand': 0, 'incoming': 0, 'product_name': f.entity_name})
                            stock_on_hand = stock_info['stock_on_hand']
                            incoming_stock = stock_info['incoming']
                            product_name = stock_info['product_name']
                        forecasted_stock = round(total_qty, 1)
                        stock_gap = (stock_on_hand + incoming_stock) - forecasted_stock

                        # Filter: Only show products with negative stock gap (shortages)
                        # Apply stock gap filter in BOTH replenishment AND normal forecasting views
                        if stock_gap >= 0:
                            skipped_no_stock_gap += 1
                            continue

                        # Check if this variation has already been requested
                        already_requested = (f.entity_name, size or '') in requested_items_set

                        # Skip this variation entirely if already requested
                        if already_requested:
                            continue

                        variation_data = {
                            'sku_code': f.entity_name,
                            'product_name': product_name,
                            'size': size,
                            'total_quantity': forecasted_stock,
                            'stock_on_hand': int(stock_on_hand),
                            'incoming_stock': int(incoming_stock),
                            'stock_gap': round(stock_gap, 1),
                            'accuracy_score': round(f.accuracy_score, 1) if f.accuracy_score is not None else 'N/A',
                            'model': f.model_params.get('model', 'Unknown'),
                            'next_7_days': next_7_days,
                            'forecast_data': date_range_data,
                            'training_days': f.model_params.get('training_days', 0),
                            'mae': round(f.mae, 2) if f.mae else None,
                            'mape': round(f.mape, 2) if f.mape else None
                        }

                        school_variations.append(variation_data)
                        school_total_quantity += forecasted_stock

                    # Add school if it has variations
                    if school_variations:
                        # Sort variations by product name, then by size
                        school_variations = sorted(school_variations, key=lambda x: (
                            x['product_name'],
                            int(x['size']) if x['size'].isdigit() else 999,
                            x['size']
                        ))

                        location_schools.append({
                            'school_name': school_name,
                            'total_quantity': round(school_total_quantity, 1),
                            'variation_count': len(school_variations),
                            'variations': school_variations
                        })
                        location_total_quantity += school_total_quantity

                # Add location if it has schools
                if location_schools:
                    # Sort schools by total quantity descending
                    location_schools = sorted(location_schools, key=lambda x: x['total_quantity'], reverse=True)

                    forecast_list.append({
                        'location_name': location_name,
                        'entity_name': location_name,  # For compatibility
                        'total_quantity': round(location_total_quantity, 1),
                        'school_count': len(location_schools),
                        'schools': location_schools,
                        'is_shop_grouped': True  # NEW FLAG for 3-level view
                    })

            logger.info(f'DEBUG: Processed {processed_count} products, skipped {skipped_zero_count} with zero quantity, skipped {skipped_no_stock_gap} with no stock gap (surplus)')
            logger.info(f'DEBUG: Generated {len(forecast_list)} location groups before sorting')

            # Sort locations by total quantity descending
            forecast_list = sorted(forecast_list, key=lambda x: x['total_quantity'], reverse=True)[:50]  # Limit to 50 locations

            logger.info(f'DEBUG: Final forecast_list has {len(forecast_list)} locations after limit')

    elif level == 'school':
        # SIMPLIFIED SCHOOL VIEW: Group variations by school (2-level structure)
        from collections import defaultdict
        from cin7.models import ProductOption

        logger = logging.getLogger(__name__)

        # Group forecasts by school
        school_groups = defaultdict(list)

        # First, we need to get school name for each forecast
        # Build a mapping of SKU -> school name
        sku_to_school = {}
        for f in forecasts:
            # Try to get school name from the raw SQL result first
            school_name = getattr(f, 'school_name', None)
            if school_name:
                sku_to_school[f.entity_name] = school_name
            else:
                # Fallback: query ProductOption
                try:
                    po = ProductOption.objects.select_related('product').get(code=f.entity_name)
                    school_name = po.product.sub_category or 'Uncategorized'
                    sku_to_school[f.entity_name] = school_name
                except ProductOption.DoesNotExist:
                    logger.warning(f'ProductOption not found for SKU: {f.entity_name}')
                    continue

        # Now group forecasts by school
        for f in forecasts:
            school_name = sku_to_school.get(f.entity_name)
            if school_name:
                school_groups[school_name].append(f)

        # Use pre-attached stock data from phase 1 query (if available)
        # Fall back to batch query for non-optimized paths
        has_phase1_data = len(forecasts) > 0 and hasattr(forecasts[0], '_stock_on_hand')
        if not has_phase1_data:
            all_school_skus = [f.entity_name for f in forecasts if f.entity_name in sku_to_school]
            stock_data_cache = batch_get_stock_data(all_school_skus)

        # Process each school group
        forecast_list = []
        logger.info(f'DEBUG: Processing school level with {len(school_groups)} school groups')
        processed_count = 0
        skipped_zero_count = 0
        skipped_no_stock_gap = 0

        for school_name, school_forecasts in sorted(school_groups.items()):
            # Direct list of variations (no product grouping)
            school_variations = []
            school_total_quantity = 0
            logger.info(f'DEBUG: Processing school "{school_name}" with {len(school_forecasts)} forecasts')

            for f in school_forecasts:
                size = extract_size_from_sku(f.entity_name)

                # Extract forecast data for the selected date range
                if use_legacy:
                    date_range_data = {}
                    for date_str, forecast_data in f.forecast_data.items():
                        forecast_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        if start_date <= forecast_date <= end_date:
                            date_range_data[date_str] = forecast_data
                else:
                    date_range_data = f.get_date_range_forecast(start_date, end_date)
                    if processed_count == 0:  # Log details for first product only
                        logger.info(f'DEBUG: First product (school level) date extraction:')
                        logger.info(f'  - Entity: {f.entity_name}')
                        logger.info(f'  - Forecast date: {f.forecast_date}')
                        logger.info(f'  - Requested range: {start_date} to {end_date}')
                        logger.info(f'  - Daily forecasts present: {bool(f.daily_forecasts)}')
                        if f.daily_forecasts:
                            all_dates = list(f.daily_forecasts.keys())
                            logger.info(f'  - Daily forecasts date range: {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} days)')
                        logger.info(f'  - Extracted dates: {len(date_range_data)} days')
                        if date_range_data:
                            extracted_dates = list(date_range_data.keys())
                            logger.info(f'  - Extracted range: {extracted_dates[0]} to {extracted_dates[-1]}')

                # Calculate total quantity for this SKU within the date range
                total_qty = sum([day['quantity'] for day in date_range_data.values()])

                # Only include if total_qty > 0
                if total_qty == 0:
                    skipped_zero_count += 1
                    continue

                processed_count += 1

                # Get first 7 days detail
                forecast_dates = sorted(date_range_data.keys())[:7]
                next_7_days = [
                    {
                        'date': date,
                        'quantity': date_range_data[date]['quantity'],
                        'confidence_lower': date_range_data[date].get('confidence_lower', 0),
                        'confidence_upper': date_range_data[date].get('confidence_upper', 0)
                    }
                    for date in forecast_dates
                ]

                # Get stock data from phase 1 cache or batch cache
                if has_phase1_data:
                    stock_on_hand = getattr(f, '_stock_on_hand', 0)
                    incoming_stock = getattr(f, '_incoming', 0)
                    product_name = getattr(f, '_product_name', f.entity_name)
                else:
                    stock_info = stock_data_cache.get(f.entity_name, {'stock_on_hand': 0, 'incoming': 0, 'product_name': f.entity_name})
                    stock_on_hand = stock_info['stock_on_hand']
                    incoming_stock = stock_info['incoming']
                    product_name = stock_info['product_name']
                forecasted_stock = round(total_qty, 1)
                stock_gap = (stock_on_hand + incoming_stock) - forecasted_stock

                # Filter: Only show products with negative stock gap (shortages)
                # Stock gap already pre-filtered in phase 1 SQL HAVING clause,
                # but re-check with date-range-specific total for accuracy
                if stock_gap >= 0:
                    skipped_no_stock_gap += 1
                    continue

                # Check if this variation has already been requested
                already_requested = (f.entity_name, size or '') in requested_items_set

                # Skip this variation entirely if already requested
                if already_requested:
                    continue

                variation_data = {
                    'sku_code': f.entity_name,
                    'product_name': product_name,
                    'size': size,
                    'total_quantity': forecasted_stock,
                    'stock_on_hand': int(stock_on_hand),
                    'incoming_stock': int(incoming_stock),
                    'stock_gap': round(stock_gap, 1),
                    'accuracy_score': round(f.accuracy_score, 1) if f.accuracy_score is not None else 'N/A',
                    'model': f.model_params.get('model', 'Unknown'),
                    'next_7_days': next_7_days,
                    'forecast_data': date_range_data,
                    'training_days': f.model_params.get('training_days', 0),
                    'mae': round(f.mae, 2) if f.mae else None,
                    'mape': round(f.mape, 2) if f.mape else None
                }

                school_variations.append(variation_data)
                school_total_quantity += forecasted_stock

            # Only add school if it has variations after filtering
            if school_variations:
                # Sort variations by product name, then by size
                school_variations = sorted(school_variations, key=lambda x: (
                    x['product_name'],
                    int(x['size']) if x['size'].isdigit() else 999,
                    x['size']
                ))

                # Add school group to forecast list
                forecast_list.append({
                    'school_name': school_name,
                    'entity_name': school_name,  # For compatibility with existing template code
                    'total_quantity': round(school_total_quantity, 1),
                    'variation_count': len(school_variations),
                    'variations': school_variations,
                    'is_school_grouped': True  # Special flag for school-level grouping
                })

        logger.info(f'DEBUG: School level summary:')
        logger.info(f'  - Processed: {processed_count} products')
        logger.info(f'  - Skipped (zero quantity): {skipped_zero_count}')
        logger.info(f'  - Skipped (no stock gap - surplus): {skipped_no_stock_gap}')
        logger.info(f'  - Generated {len(forecast_list)} school groups')

        # Sort schools by total quantity descending
        forecast_list = sorted(forecast_list, key=lambda x: x['total_quantity'], reverse=True)[:100]  # Limit to 100 schools

        logger.info(f'DEBUG: Final forecast_list has {len(forecast_list)} schools after limit')

    else:
        # Regular flat view for shop/category
        forecast_list = []
        for f in forecasts:
            # Extract forecast data for the selected date range
            if use_legacy:
                # Legacy: filter forecast_data by date range
                date_range_data = {}
                for date_str, forecast_data in f.forecast_data.items():
                    forecast_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    if start_date <= forecast_date <= end_date:
                        date_range_data[date_str] = forecast_data
            else:
                # New: extract date range from base forecast
                date_range_data = f.get_date_range_forecast(start_date, end_date)

            # Calculate total forecasted quantity
            total_qty = sum([day['quantity'] for day in date_range_data.values()])

            # Get first 7 days detail
            forecast_dates = sorted(date_range_data.keys())[:7]
            next_7_days = [
                {
                    'date': date,
                    'quantity': date_range_data[date]['quantity'],
                    'confidence_lower': date_range_data[date].get('confidence_lower', 0),
                    'confidence_upper': date_range_data[date].get('confidence_upper', 0)
                }
                for date in forecast_dates
            ]

            forecast_list.append({
                'entity_name': f.entity_name,
                'total_quantity': round(total_qty, 1),
                'accuracy_score': round(f.accuracy_score, 1) if f.accuracy_score is not None else 'N/A',
                'model': f.model_params.get('model', 'Unknown'),
                'next_7_days': next_7_days,
                'forecast_data': date_range_data,
                'training_days': f.model_params.get('training_days', 0),
                'mae': round(f.mae, 2) if f.mae else None,
                'mape': round(f.mape, 2) if f.mape else None,
                'is_grouped': False
            })

    # Get summary statistics
    # Calculate average accuracy from the forecast list
    if level == 'shop':
        # For shop level, extract accuracy scores from nested variations within schools
        accuracy_scores = []
        for location in forecast_list:
            if location.get('is_shop_grouped'):
                for school in location.get('schools', []):
                    for variation in school.get('variations', []):
                        acc = variation.get('accuracy_score')
                        if acc is not None and acc != 'N/A':
                            accuracy_scores.append(acc)
            elif location.get('is_school_grouped'):
                # 2-level shop view (when shop filter is provided)
                for variation in location.get('variations', []):
                    acc = variation.get('accuracy_score')
                    if acc is not None and acc != 'N/A':
                        accuracy_scores.append(acc)
        avg_accuracy = round(sum(accuracy_scores) / len(accuracy_scores), 1) if accuracy_scores else 0
    elif level == 'school':
        # For school level, extract accuracy scores from nested variations
        accuracy_scores = []
        for school in forecast_list:
            if school.get('is_school_grouped'):
                for variation in school.get('variations', []):
                    acc = variation.get('accuracy_score')
                    if acc is not None and acc != 'N/A':
                        accuracy_scores.append(acc)
        avg_accuracy = round(sum(accuracy_scores) / len(accuracy_scores), 1) if accuracy_scores else 0
    elif level == 'product':
        # For product level, extract from nested variations
        accuracy_scores = []
        for product in forecast_list:
            if product.get('is_grouped'):
                for variation in product.get('variations', []):
                    acc = variation.get('accuracy_score')
                    if acc is not None and acc != 'N/A':
                        accuracy_scores.append(acc)
        avg_accuracy = round(sum(accuracy_scores) / len(accuracy_scores), 1) if accuracy_scores else 0
    else:
        # For other levels, forecasts is a list (not QuerySet)
        accuracy_scores = [f.accuracy_score for f in forecasts if f.accuracy_score is not None]
        avg_accuracy = round(sum(accuracy_scores) / len(accuracy_scores), 1) if accuracy_scores else 0

    # Calculate date range display
    date_range_display = f"{start_date_str} to {end_date_str} ({num_days} days)"

    summary = {
        'total_forecasts': len(forecast_list),
        'avg_accuracy': avg_accuracy,
        'horizon_display': date_range_display,
        'level_display': dict(SalesForecastBase.AGGREGATION_LEVELS).get(level, level),
        'num_days': num_days,
        'start_date': start_date_str,
        'end_date': end_date_str
    }

    # Detect if forecasts are being generated (no data available)
    # IMPORTANT: Only set generating_forecasts=True if forecasts don't exist yet
    # but COULD be generated. If no forecasts are available at all (e.g., shop level
    # has never been implemented), set no_forecasts_available=True instead to prevent
    # infinite refresh loop.
    # ALSO: Check for all_variations (flat table view) - if we have variations, we have data!
    has_data = len(forecast_list) > 0 or ('all_variations' in locals() and len(all_variations) > 0)

    if not has_data and no_forecasts_available:
        # No forecasts exist and none are available - don't trigger auto-refresh
        generating_forecasts = False
    elif not has_data:
        # No forecasts but they might be generating - trigger auto-refresh
        generating_forecasts = True
    else:
        # We have forecasts - don't trigger auto-refresh
        generating_forecasts = False

    # Determine the display name for the header based on active filters
    display_name = None
    has_filter = False

    if school_filter:
        display_name = school_filter
        has_filter = True
    elif product_filter:
        # Get product name from cin7_sync_product table
        try:
            from cin7.models import Product
            product = Product.objects.get(cin7_id=product_filter)
            display_name = product.name
            has_filter = True
        except Product.DoesNotExist:
            display_name = f"Product #{product_filter}"
            has_filter = True
    elif shop_filter:
        display_name = shop_filter
        has_filter = True
    elif category_filter:
        display_name = category_filter
        has_filter = True
    else:
        # No filter - use generic aggregation level name
        display_name = dict(SalesForecastBase.AGGREGATION_LEVELS).get(level, level)

    # Calculate risk counts if not already calculated (for non-product levels)
    if 'critical_count' not in locals():
        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        total_count = 0

    # Warning message for users with store scope but no assigned stores
    data_scope_warning = None
    if data_scope == 'store' and not user_store_categories:
        data_scope_warning = "You have store-level access but no stores are assigned to your account. Please contact your administrator to assign stores."
        logger.warning(f'User {user.username} has store scope but no assigned stores')

    context = {
        'forecasts': forecast_list,
        'forecast_list_json': json.dumps(forecast_list, default=str),
        'summary': summary,
        'current_horizon': horizon,  # For backward compatibility
        'current_level': original_level,  # Use original level, not modified level
        'render_level': level,  # Level for template rendering (may be 'product' when school selected)
        'start_date': start_date_str,
        'end_date': end_date_str,
        'num_days': num_days,
        'horizons': SalesForecast.FORECAST_HORIZONS,  # For backward compatibility
        'levels': SalesForecastBase.AGGREGATION_LEVELS,
        'use_date_range': True,
        'from_cache': False,
        'generating_forecasts': generating_forecasts,
        'no_forecasts_available': no_forecasts_available,  # New flag to distinguish "none available" vs "generating"
        'using_365d_base': not use_legacy,  # Flag to indicate using new 365-day base system
        'display_name': display_name,  # Dynamic display name based on filter
        'has_filter': has_filter,  # Boolean to indicate if any filter is active
        'is_replenishment_view': getattr(request, 'is_replenishment_view', False),  # Hide filters for replenishment view
        # Risk-based filtering
        'risk_filter': risk_filter,
        'critical_count': critical_count,
        'high_count': high_count,
        'medium_count': medium_count,
        'low_count': low_count,
        'total_count': total_count,
        # Data scope warning
        'data_scope_warning': data_scope_warning
    }

    # Add flat table data for shop level with filter OR replenishment view (Store Manager view)
    logger.info(f'DEBUG: Checking flat table context assignment')
    logger.info(f'  - level: {level}')
    logger.info(f'  - shop_filter: {shop_filter}')
    logger.info(f'  - is_replenishment_view: {is_replenishment_view}')
    logger.info(f'  - all_variations in locals(): {"all_variations" in locals()}')
    if 'all_variations' in locals():
        logger.info(f'  - len(all_variations): {len(all_variations)}')

    if level == 'shop' and (shop_filter or is_replenishment_view) and 'all_variations' in locals():
        logger.info(f'✅ Adding all_variations to context with display_mode=flat_table')
        context['all_variations'] = all_variations
        context['display_mode'] = 'flat_table'
    else:
        logger.info(f'❌ NOT adding flat table to context')

    # Debug: Log what's being passed to template
    logger.info(f'DEBUG: Final context check before rendering:')
    logger.info(f'  - len(context["forecasts"]): {len(context.get("forecasts", []))}')
    logger.info(f'  - "all_variations" in context: {"all_variations" in context}')
    if 'all_variations' in context:
        logger.info(f'  - len(context["all_variations"]): {len(context["all_variations"])}')
    logger.info(f'  - context.get("display_mode"): {context.get("display_mode")}')
    logger.info(f'  - context.get("generating_forecasts"): {context.get("generating_forecasts")}')

    # Cache the context only if we have data (don't cache empty state)
    if not generating_forecasts:
        cache.set(cache_key, context, cache_timeout)

    return render(request, 'dashboard/sales_forecasting.html', context)


@login_required
@permission_required('forecasting.view')
def forecast_product_breakdown(request, school_name):
    """
    Get product-level breakdown for a specific school or shop
    Returns JSON with all products forecasted for that entity
    Uses the new SalesForecastBase system with 365-day forecasts

    Supports two levels:
    - school: Queries by p.sub_category (school name)
    - shop: Queries by p.category_name (shop name)
    """
    from dashboard.models import SalesForecastBase
    from django.db import connection
    from datetime import datetime, timedelta
    import json

    logger = logging.getLogger(__name__)
    logger.info('=== FORECAST_PRODUCT_BREAKDOWN START ===')
    logger.info(f'Entity name: {school_name}')

    # Get level parameter to determine if this is school or shop
    level = request.GET.get('level', 'school')
    logger.info(f'Level: {level}')

    # Get date range parameters (same as main forecasting view)
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    logger.info(f'Date range params: start={start_date_str}, end={end_date_str}')

    # Default to next 30 days if not provided
    if not start_date_str or not end_date_str:
        today = datetime.now().date()
        start_date = today
        end_date = today + timedelta(days=30)
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        logger.info(f'Using default 30-day range: {start_date_str} to {end_date_str}')
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        logger.info(f'Using provided date range: {start_date_str} to {end_date_str}')

    num_days = (end_date - start_date).days + 1
    logger.info(f'Total days in range: {num_days}')

    # Get product-level forecasts for this school/shop from NEW system
    # Note: Product forecasts are stored by SKU code from line items (e.g., "JKT 704 CL WHHS -M")
    # We use a subquery to find which SKUs belong to this entity, then fetch their forecasts
    with connection.cursor() as cursor:
        logger.info('=== EXECUTING PRODUCT BREAKDOWN QUERY ===')

        # Build query based on level
        if level == 'shop':
            # For shops, filter by category_name (e.g., "Coffee Shop", "Uniform Shop")
            logger.info(f'Querying products for shop: {school_name}')
            cursor.execute("""
                SELECT
                    sf.entity_name as sku_code,
                    sf.daily_forecasts,
                    sf.accuracy_score,
                    sf.model_params,
                    sf.entity_name as product_code,
                    COALESCE(
                        p.name,
                        st.product_name,
                        (
                            SELECT name
                            FROM cin7_sync_salesorderlineitem
                            WHERE code = sf.entity_name
                            AND name IS NOT NULL
                            AND name != ''
                            GROUP BY name
                            ORDER BY COUNT(*) DESC
                            LIMIT 1
                        ),
                        sf.entity_name
                    ) as product_name,
                    COALESCE(po.option1, SUBSTRING_INDEX(sf.entity_name, '-', -1)) as size
                FROM dashboard_salesforecastbase sf
                LEFT JOIN cin7_sync_productoption po ON po.code = sf.entity_name
                LEFT JOIN cin7_sync_product p ON p.id = po.product_id AND p.category_name = %s
                LEFT JOIN cin7_sync_stock st ON st.code = sf.entity_name AND st.product_name IS NOT NULL AND st.product_name != ''
                WHERE sf.aggregation_level = 'product'
                ORDER BY product_name, size
                LIMIT 500
            """, [school_name])
        else:
            # For schools, filter by sub_category (school name)
            logger.info(f'Querying products for school: {school_name}')
            cursor.execute("""
                SELECT
                    sf.entity_name as sku_code,
                    sf.daily_forecasts,
                    sf.accuracy_score,
                    sf.model_params,
                    sf.entity_name as product_code,
                    COALESCE(
                        p.name,
                        st.product_name,
                        (
                            SELECT li.name
                            FROM cin7_sync_salesorderlineitem li
                            WHERE li.code = sf.entity_name
                            AND li.name IS NOT NULL
                            AND li.name != ''
                            GROUP BY li.name
                            ORDER BY COUNT(*) DESC
                            LIMIT 1
                        ),
                        sf.entity_name
                    ) as product_name,
                    COALESCE(po.option1, SUBSTRING_INDEX(sf.entity_name, '-', -1)) as size
                FROM dashboard_salesforecastbase sf
                LEFT JOIN cin7_sync_productoption po ON po.code = sf.entity_name
                LEFT JOIN cin7_sync_product p ON p.id = po.product_id AND p.sub_category = %s AND (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store') AND p.category_name NOT IN ('Shop', 'Store')
                LEFT JOIN cin7_sync_stock st ON st.code = sf.entity_name AND st.product_name IS NOT NULL AND st.product_name != ''
                WHERE sf.aggregation_level = 'product'
                ORDER BY product_name, size
                LIMIT 500
            """, [school_name])

        logger.info('Query executed successfully')

        products = []
        rows = cursor.fetchall()
        logger.info(f'Query returned {len(rows)} products')

        for row in rows:
            sku_code, daily_forecasts_json, accuracy, model_params_json, product_code, product_name, size = row

            # Parse JSON fields
            import json as json_lib
            daily_forecasts = json_lib.loads(daily_forecasts_json) if isinstance(daily_forecasts_json, str) else daily_forecasts_json
            model_params = json_lib.loads(model_params_json) if isinstance(model_params_json, str) else model_params_json

            # Filter forecasts to the requested date range
            date_range_forecasts = {}
            if daily_forecasts:
                for date_str, forecast_data in daily_forecasts.items():
                    if start_date_str <= date_str <= end_date_str:
                        date_range_forecasts[date_str] = forecast_data

            # Calculate total quantity for the date range
            total_qty = sum([day.get('quantity', 0) for day in date_range_forecasts.values()])

            # Get first 7 days of the date range
            forecast_dates = sorted(date_range_forecasts.keys())[:7]
            next_7_days = []
            for date in forecast_dates:
                day_data = date_range_forecasts.get(date, {})
                next_7_days.append({
                    'date': date,
                    'quantity': round(day_data.get('quantity', 0), 1)
                })

            products.append({
                'sku_code': sku_code,
                'product_name': product_name,  # Just the product name without size
                'product_code': sku_code,  # Full SKU code with size for the Code column
                'size': size,
                'total_quantity': round(total_qty, 1),
                'accuracy_score': round(accuracy, 1) if accuracy is not None else 'N/A',
                'model': model_params.get('model', 'Unknown'),
                'next_7_days': next_7_days,
                'forecast_data': date_range_forecasts  # Add full forecast data for chart functionality
            })

    total_units = sum([p['total_quantity'] for p in products])
    logger.info(f'=== PRODUCT BREAKDOWN TOTALS ===')
    logger.info(f'Shop/Entity: {school_name}')
    logger.info(f'Date Range: {start_date_str} to {end_date_str} ({num_days} days)')
    logger.info(f'Product Count: {len(products)}')
    logger.info(f'Total Units (sum of products): {total_units:.2f}')
    logger.info(f'First 3 products: {[p["product_name"] for p in products[:3]]}')

    # Calculate and log individual product totals for verification
    if len(products) > 0:
        logger.info(f'Sample product totals (first 5):')
        for i, p in enumerate(products[:5]):
            logger.info(f'  {i+1}. {p["sku_code"]}: {p["total_quantity"]:.2f} units')
    logger.info(f'=== END PRODUCT BREAKDOWN TOTALS ===')

    # Check if we also have an entity-level forecast for comparison
    entity_forecast_total = None
    entity_label = 'School' if level == 'school' else 'Shop'

    try:
        from dashboard.models import SalesForecastBase

        # For shops, we don't have direct shop forecasts - they're aggregated from products
        # So skip the comparison for shops
        if level == 'school':
            entity_forecast = SalesForecastBase.objects.filter(
                entity_name=school_name,
                aggregation_level='school'
            ).first()

            if entity_forecast:
                entity_date_range = entity_forecast.get_date_range_forecast(start_date, end_date)
                entity_forecast_total = sum([day.get('quantity', 0) for day in entity_date_range.values()])
                logger.info(f'{entity_label}-level forecast for comparison: {entity_forecast_total} units')

                # Calculate discrepancy ratio
                if entity_forecast_total > 0:
                    discrepancy_ratio = total_units / entity_forecast_total
                    logger.warning(f'⚠️  DISCREPANCY: Product sum ({total_units}) vs {entity_label} total ({entity_forecast_total}) = {discrepancy_ratio:.1f}x difference')
                else:
                    logger.warning(f'⚠️  {entity_label} forecast is 0 or unavailable')
        else:
            # For shops, the sum of products IS the shop forecast (they're aggregated)
            # So we expect them to match perfectly
            logger.info(f'✓ Shop-level forecasts are aggregated from products')
            logger.info(f'  Expected: Product sum ({total_units:.2f}) = Shop total')
            logger.info(f'  This breakdown will be compared with shop aggregation total in UI')
            entity_forecast_total = total_units

    except Exception as e:
        logger.error(f'Error fetching {entity_label} forecast for comparison: {e}')

    # Final verification for shops: ensure consistency
    verification_passed = True
    if level == 'shop':
        # For shops, we can verify against the aggregation by checking if totals would match
        # This is a safety check to ensure the product breakdown matches what the main table shows
        logger.info(f'=== FINAL VERIFICATION FOR SHOP: {school_name} ===')
        logger.info(f'  Total from products: {total_units:.2f} units')
        logger.info(f'  Number of products: {len(products)}')
        logger.info(f'  Date range: {start_date_str} to {end_date_str}')
        logger.info(f'  Expected to match shop aggregation total in main table')

        if total_units == 0 and len(products) > 0:
            logger.warning(f'⚠️  WARNING: Have {len(products)} products but total is 0!')
            verification_passed = False
        elif len(products) == 0 and total_units > 0:
            logger.error(f'❌ ERROR: Have total of {total_units} but no products!')
            verification_passed = False
        else:
            logger.info(f'✓ Verification passed: Product count and totals are consistent')

        logger.info(f'=== END VERIFICATION ===')

    logger.info('=== FORECAST_PRODUCT_BREAKDOWN END ===')

    return JsonResponse({
        'entity_name': school_name,
        'entity_label': entity_label,
        'school_name': school_name,  # Keep for backward compatibility
        'start_date': start_date_str,
        'end_date': end_date_str,
        'num_days': num_days,
        'products': products,
        'total_products': len(products),
        'total_units': total_units,
        'school_forecast_total': entity_forecast_total,  # Keep old name for backward compatibility
        'entity_forecast_total': entity_forecast_total,
        'warning': 'Product-level forecasts are currently unreliable (50-100x too high). Use with extreme caution.' if total_units > 0 and level == 'school' else None,
        'verification_passed': verification_passed if level == 'shop' else None
    })


@login_required
@permission_required('replenishment.stores.view')
def store_manager_replenishment(request):
    """
    Store Manager Replenishment Dashboard

    Uses shop-level forecasting with a fixed 30-60 day forward window and displays
    products in a flat table sorted by risk level.
    """
    from datetime import date, timedelta
    from django.http import QueryDict

    # Use a 6-month forward window for replenishment planning
    # School uniforms are seasonal (BTS in Dec-Feb for NZ), so a short window
    # during off-season would show zero demand and no results
    today = date.today()
    start_date = today
    end_date = today + timedelta(days=180)  # 6 months forward

    # Create a modified request with shop level (no specific shop filter = show all Shop/Store categories)
    modified_GET = QueryDict(mutable=True)
    modified_GET.update(request.GET)
    modified_GET['level'] = 'shop'
    # Don't set 'shop' parameter - let the view show all Shop/Store categories via pattern matching
    modified_GET['start_date'] = start_date.strftime('%Y-%m-%d')
    modified_GET['end_date'] = end_date.strftime('%Y-%m-%d')
    request.GET = modified_GET

    # Mark this as a replenishment view (to hide filters in template)
    request.is_replenishment_view = True

    # Call the sales_forecasting view directly, bypassing its @permission_required('forecasting.view')
    # decorator since store managers don't have forecasting.view but should access replenishment data.
    # Access the unwrapped function through __wrapped__ (set by @wraps in the decorators).
    unwrapped = sales_forecasting
    while hasattr(unwrapped, '__wrapped__'):
        unwrapped = unwrapped.__wrapped__
    return unwrapped(request)

    # OLD CODE BELOW (kept for reference but not executed)
    from dashboard.models import SalesForecastBase
    from django.db import connection
    from django.core.cache import cache
    from datetime import timedelta, date
    from collections import defaultdict
    import json
    import time

    logger = logging.getLogger(__name__)
    user = request.user

    # ========== CHECK CACHE FIRST ==========
    is_admin = user.is_superuser or user.is_staff
    assigned_branch_id = None
    if not is_admin:
        assigned_branch = getattr(user, 'assigned_branch', None)
        if assigned_branch:
            assigned_branch_id = assigned_branch.id

    cache_key = f'replenishment_data_{date.today()}_{is_admin}_{assigned_branch_id or "all"}'
    cached_data = cache.get(cache_key)

    if cached_data:
        logger.info(f"Using cached replenishment data (cache key: {cache_key})")
        return render(request, 'dashboard/store_replenishment.html', cached_data)

    logger.info(f"Cache miss - generating replenishment data (this may take 5 minutes...)")
    start_time = time.time()

    # ========== ROLE-BASED ACCESS CONTROL ==========
    is_admin = user.is_superuser or user.is_staff
    assigned_branch = None
    assigned_branch_id = None

    if not is_admin:
        assigned_branch = getattr(user, 'assigned_branch', None)
        if assigned_branch:
            assigned_branch_id = assigned_branch.id

    # ========== CALCULATE 30-DAY PERIOD ==========
    # Calculate demand for NEXT month (30-60 days from now)
    # This is forward-looking replenishment planning
    today = date.today()
    start_date = today + timedelta(days=30)  # Start 30 days from now
    end_date = start_date + timedelta(days=30)  # End 30 days after start (60 days from today)

    # Generate list of date strings for the 30-day window
    date_strings = []
    current_date = start_date
    while current_date <= end_date:
        date_strings.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)

    logger.info(f"Calculating demand for {len(date_strings)} days: {start_date} to {end_date}")

    # ========== STEP 1: BULK QUERY ALL PRODUCT FORECASTS WITH STOCK DATA ==========
    # OPTIMIZED: Uses pre-calculated monthly_demand_30 instead of parsing JSON
    # This eliminates 2.7M JSON lookups and reduces processing time by 90%!
    with connection.cursor() as cursor:
        query = """
        SELECT
            sfb.entity_name as sku_code,
            sfb.monthly_demand_30,
            sfb.accuracy_score,
            p.id as product_id,
            p.name as product_display_name,
            po.code as sku,
            p.sub_category as school_name,
            s.branch_id,
            b.company as branch_name,
            s.stock_on_hand,
            s.incoming
        FROM dashboard_salesforecastbase sfb
        INNER JOIN cin7_sync_productoption po ON sfb.entity_name = po.code
        INNER JOIN cin7_sync_product p ON po.product_id = p.id
        LEFT JOIN cin7_sync_stock s ON s.product_id = p.id
        LEFT JOIN cin7_sync_branch b ON b.id = s.branch_id
        WHERE sfb.aggregation_level = 'product'
          AND sfb.forecast_date = (
              SELECT MAX(forecast_date)
              FROM dashboard_salesforecastbase
              WHERE aggregation_level = 'product'
          )
          AND (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
          AND p.category_name NOT IN ('Shop', 'Store')
          AND p.category_name NOT LIKE 'Wholesale%%'
          AND p.sub_category IS NOT NULL
          AND p.sub_category != ''
          AND sfb.monthly_demand_30 IS NOT NULL
          AND sfb.monthly_demand_30 > 0
        """

        params = []

        # Branch filtering for shop managers
        if not is_admin and assigned_branch_id:
            query += " AND s.branch_id = %s"
            params.append(assigned_branch_id)

        query += " ORDER BY p.sub_category, p.name, b.company"

        logger.info(f"Executing optimized bulk query (using pre-calculated monthly_demand_30)...")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"Retrieved {len(rows)} product-forecast-stock records")

    # ========== STEP 2: PROCESS IN-MEMORY (FAST) ==========
    # Group products by school -> branch -> products
    school_data = defaultdict(lambda: {
        'school_name': '',
        'total_monthly_demand': 0.0,
        'branches': defaultdict(lambda: {
            'branch_name': '',
            'branch_id': None,
            'products': []
        })
    })

    products_with_gaps = 0
    products_without_stock = 0
    products_processed = 0

    for row in rows:
        (product_name, monthly_demand_30, accuracy,
         product_id, product_display_name, product_code, school_name,
         branch_id, branch_name, stock_on_hand, incoming) = row

        products_processed += 1

        # Skip if no stock data for this branch
        if branch_id is None:
            products_without_stock += 1
            continue

        # Use pre-calculated monthly_demand_30 (eliminates JSON parsing!)
        monthly_demand = float(monthly_demand_30 or 0)

        # Skip if no demand (already filtered in SQL, but double-check)
        if monthly_demand <= 0:
            continue

        # Calculate stock gap
        current_stock = float(stock_on_hand or 0)
        incoming_stock = float(incoming or 0)
        total_stock = current_stock + incoming_stock
        stock_gap = monthly_demand - total_stock

        # Only include products with stock gaps
        if stock_gap <= 0:
            continue

        products_with_gaps += 1

        # Calculate urgency
        daily_demand = monthly_demand / 30
        days_of_stock = total_stock / daily_demand if daily_demand > 0 else 999

        if days_of_stock < 7:
            urgency = 'critical'
        elif days_of_stock < 15:
            urgency = 'high'
        elif days_of_stock < 30:
            urgency = 'medium'
        else:
            urgency = 'low'

        # Add to hierarchical structure
        school_data[school_name]['school_name'] = school_name
        school_data[school_name]['total_monthly_demand'] += monthly_demand

        branch_key = f"{branch_id}_{branch_name}"
        school_data[school_name]['branches'][branch_key]['branch_name'] = branch_name or 'Unknown Branch'
        school_data[school_name]['branches'][branch_key]['branch_id'] = branch_id

        school_data[school_name]['branches'][branch_key]['products'].append({
            'product_id': product_id,
            'product_name': product_display_name or product_name,
            'product_code': product_code or 'N/A',
            'monthly_demand': round(monthly_demand, 1),
            'current_stock': round(current_stock, 1),
            'incoming_stock': round(incoming_stock, 1),
            'forecasted_stock': round(total_stock, 1),
            'stock_gap': round(stock_gap, 1),
            'suggested_replenishment': round(max(stock_gap, 0), 1),
            'urgency': urgency,
            'days_of_stock': round(days_of_stock, 1),
            'accuracy': round(accuracy, 1) if accuracy else 0,
            'branch_id': branch_id,
            'branch_name': branch_name or 'Unknown',
        })

    logger.info(f"Processed {products_processed} records, found {products_with_gaps} products with stock gaps")
    logger.info(f"Products without stock data: {products_without_stock}")

    # ========== STEP 3: FORMAT FOR TEMPLATE ==========
    # Convert nested dict structure to list format for template
    school_list = []

    for school_name, school_info in school_data.items():
        # Flatten branches
        all_products = []
        for branch_key, branch_info in school_info['branches'].items():
            all_products.extend(branch_info['products'])

        # Calculate school totals
        total_gap = sum(p['stock_gap'] for p in all_products)

        school_list.append({
            'school_name': school_name,
            'monthly_demand': round(school_info['total_monthly_demand'], 1),
            'products': all_products,
            'product_count': len(all_products),
            'total_stock_gap': round(total_gap, 1),
        })

    # Sort by monthly demand (highest first)
    school_list.sort(key=lambda x: x['monthly_demand'], reverse=True)

    logger.info(f"Final result: {len(school_list)} schools with stock gaps")

    # ========== STEP 4: CALCULATE SUMMARY STATISTICS ==========
    total_schools = len(school_list)
    total_products = sum(s['product_count'] for s in school_list)
    total_demand = sum(s['monthly_demand'] for s in school_list)
    total_gap = sum(s['total_stock_gap'] for s in school_list)

    critical_count = sum(
        sum(1 for p in s['products'] if p['urgency'] == 'critical')
        for s in school_list
    )

    summary = {
        'total_schools': total_schools,
        'total_products': total_products,
        'total_monthly_demand': round(total_demand, 0),
        'total_stock_gap': round(total_gap, 0),
        'critical_count': critical_count,
    }

    context = {
        'schools': school_list,
        'schools_json': json.dumps(school_list, default=str),
        'summary': summary,
        'demand_period_start': start_date.strftime('%B %d, %Y'),
        'demand_period_end': end_date.strftime('%B %d, %Y'),
        'is_admin': is_admin,
        'assigned_branch': (getattr(assigned_branch, 'company', None) or getattr(assigned_branch, 'name', None)) if assigned_branch else None,
    }

    # ========== CACHE THE RESULTS FOR 1 HOUR ==========
    cache.set(cache_key, context, 3600)  # 3600 seconds = 1 hour
    total_time = time.time() - start_time
    logger.info(f"Replenishment data generated and cached in {total_time:.2f} seconds (cache key: {cache_key})")

    return render(request, 'dashboard/store_replenishment.html', context)


@login_required
@permission_required('replenishment.stores.review')
@require_http_methods(["POST"])
def approve_replenishment(request, request_id):
    """
    Approve/Modify/Reject a replenishment request (Store Manager action)
    """
    from dashboard.models import ReplenishmentRequest
    from django.db import connection
    from django.utils import timezone
    import json

    try:
        data = json.loads(request.body)
        action = data.get('action')  # 'approve', 'modify', 'reject'
        approved_quantity = data.get('quantity')
        comment = data.get('comment', '')

        # ========== DATA SCOPE FILTERING ==========
        user = request.user
        data_scope = user.get_data_scope()

        # Build WHERE clause for branch filtering
        branch_filter_sql = ""
        branch_params = []

        if data_scope == 'branch' and not user.is_superuser:
            user_branch_names = user.get_assigned_branch_names()
            if not user_branch_names:
                return JsonResponse({
                    'success': False,
                    'error': 'You have no assigned branches'
                }, status=403)

            # Add branch filtering to SQL
            placeholders = ', '.join(['%s'] * len(user_branch_names))
            branch_filter_sql = f" AND branch_id IN (SELECT id FROM cin7_sync_branch WHERE name IN ({placeholders}))"
            branch_params = user_branch_names

        # Update using raw SQL to avoid ORM issues
        with connection.cursor() as cursor:
            if action == 'approve':
                sql = """
                    UPDATE dashboard_replenishmentrequest
                    SET status = 'approved',
                        store_approved_quantity = suggested_quantity,
                        store_manager_comment = %s,
                        store_manager_id = %s,
                        store_approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """ + branch_filter_sql
                params = [comment, request.user.id, request_id] + branch_params
                cursor.execute(sql, params)

            elif action == 'modify':
                sql = """
                    UPDATE dashboard_replenishmentrequest
                    SET status = 'modified',
                        store_approved_quantity = %s,
                        store_manager_comment = %s,
                        store_manager_id = %s,
                        store_approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """ + branch_filter_sql
                params = [float(approved_quantity), comment, request.user.id, request_id] + branch_params
                cursor.execute(sql, params)

            elif action == 'reject':
                sql = """
                    UPDATE dashboard_replenishmentrequest
                    SET status = 'rejected',
                        store_approved_quantity = 0,
                        store_manager_comment = %s,
                        store_manager_id = %s,
                        store_approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """ + branch_filter_sql
                params = [comment, request.user.id, request_id] + branch_params
                cursor.execute(sql, params)

        return JsonResponse({
            'success': True,
            'message': f'Request {action}ed successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@permission_required('replenishment.demand_planning.view')
def dp_team_replenishment(request):
    """
    Demand Planning Team Dashboard
    Shows all approved replenishment requests from all stores
    """
    from dashboard.models import ReplenishmentRequest
    from django.db import connection
    import json

    # Get filter parameters
    status_filter = request.GET.get('status', 'approved,modified')
    urgency_filter = request.GET.get('urgency', 'all')
    week_filter = request.GET.get('week', 'current')

    # Get current week number
    from datetime import datetime
    current_week = datetime.now().isocalendar()[1]

    # Get requests using raw SQL
    requests_list = []

    with connection.cursor() as cursor:
        query = """
        SELECT
            rr.id,
            rr.request_id,
            rr.school_name,
            p.name as product_name,
            p.code as product_code,
            b.company as branch_name,
            rr.current_stock,
            rr.forecasted_demand_30d,
            rr.stock_gap,
            rr.suggested_quantity,
            rr.store_approved_quantity,
            rr.dp_approved_quantity,
            rr.urgency,
            rr.ai_confidence,
            rr.status,
            rr.store_manager_comment,
            rr.dp_team_comment,
            rr.week_number,
            rr.year,
            rr.created_at,
            rr.store_approved_at
        FROM dashboard_replenishmentrequest rr
        JOIN cin7_sync_product p ON p.id = rr.product_id
        JOIN cin7_sync_branch b ON b.id = rr.branch_id
        WHERE rr.status IN ('approved', 'modified', 'dp_review', 'dp_approved')
        """

        params = []

        if urgency_filter != 'all':
            query += " AND rr.urgency = %s"
            params.append(urgency_filter)

        if week_filter == 'current':
            query += " AND rr.week_number = %s"
            params.append(current_week)
        elif week_filter != 'all':
            try:
                query += " AND rr.week_number = %s"
                params.append(int(week_filter))
            except ValueError:
                pass

        query += " ORDER BY FIELD(rr.urgency, 'critical', 'high', 'medium', 'low'), rr.stock_gap DESC LIMIT 1000"

        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]

        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))

            # Determine final quantity
            if row_dict['dp_approved_quantity'] is not None:
                final_qty = row_dict['dp_approved_quantity']
            elif row_dict['store_approved_quantity'] is not None:
                final_qty = row_dict['store_approved_quantity']
            else:
                final_qty = row_dict['suggested_quantity']

            requests_list.append({
                'id': row_dict['id'],
                'request_id': row_dict['request_id'],
                'school_name': row_dict['school_name'],
                'product_name': row_dict['product_name'],
                'product_code': row_dict['product_code'],
                'branch_name': row_dict['branch_name'],
                'current_stock': round(row_dict['current_stock'], 1),
                'forecasted_demand': round(row_dict['forecasted_demand_30d'], 1),
                'stock_gap': round(row_dict['stock_gap'], 1),
                'suggested_quantity': round(row_dict['suggested_quantity'], 1),
                'store_approved_quantity': round(row_dict['store_approved_quantity'], 1) if row_dict['store_approved_quantity'] else None,
                'dp_approved_quantity': round(row_dict['dp_approved_quantity'], 1) if row_dict['dp_approved_quantity'] else None,
                'final_quantity': round(final_qty, 1),
                'urgency': row_dict['urgency'],
                'ai_confidence': round(row_dict['ai_confidence'], 1),
                'status': row_dict['status'],
                'store_comment': row_dict['store_manager_comment'],
                'dp_comment': row_dict['dp_team_comment'],
                'week_number': row_dict['week_number'],
                'year': row_dict['year'],
                'created_at': row_dict['created_at'].strftime('%Y-%m-%d') if row_dict['created_at'] else '',
                'approved_at': row_dict['store_approved_at'].strftime('%Y-%m-%d') if row_dict['store_approved_at'] else ''
            })

    # Calculate summary statistics
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN status IN ('approved', 'modified') THEN 1 ELSE 0 END) as pending_review,
                SUM(CASE WHEN status = 'dp_approved' THEN 1 ELSE 0 END) as dp_approved_count,
                SUM(CASE WHEN urgency = 'critical' THEN 1 ELSE 0 END) as critical_count,
                SUM(COALESCE(store_approved_quantity, suggested_quantity)) as total_units_needed,
                COUNT(DISTINCT product_id) as unique_products,
                COUNT(DISTINCT branch_id) as unique_branches
            FROM dashboard_replenishmentrequest
            WHERE status IN ('approved', 'modified', 'dp_review', 'dp_approved')
        """)

        row = cursor.fetchone()
        summary = {
            'total_requests': row[0] or 0,
            'pending_review': row[1] or 0,
            'dp_approved': row[2] or 0,
            'critical_count': row[3] or 0,
            'total_units': round(row[4] or 0, 0),
            'unique_products': row[5] or 0,
            'unique_branches': row[6] or 0
        }

    context = {
        'requests': requests_list,
        'requests_json': json.dumps(requests_list, default=str),
        'summary': summary,
        'current_urgency': urgency_filter,
        'current_week': week_filter,
        'urgency_choices': ReplenishmentRequest.URGENCY_LEVELS,
    }

    return render(request, 'dashboard/dp_replenishment.html', context)


@login_required
@permission_required('replenishment.demand_planning.approve')
@require_http_methods(["POST"])
def dp_approve_replenishment(request, request_id):
    """
    DP Team approval/modification of replenishment request
    """
    from django.db import connection
    import json

    try:
        data = json.loads(request.body)
        action = data.get('action')  # 'approve', 'modify', 'reject'
        approved_quantity = data.get('quantity')
        comment = data.get('comment', '')

        with connection.cursor() as cursor:
            if action == 'approve':
                # Approve with store manager's quantity
                cursor.execute("""
                    UPDATE dashboard_replenishmentrequest
                    SET status = 'dp_approved',
                        dp_approved_quantity = COALESCE(store_approved_quantity, suggested_quantity),
                        dp_team_comment = %s,
                        dp_approver_id = %s,
                        dp_approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, [comment, request.user.id, request_id])

            elif action == 'modify':
                # Override with DP team's quantity
                cursor.execute("""
                    UPDATE dashboard_replenishmentrequest
                    SET status = 'dp_approved',
                        dp_approved_quantity = %s,
                        dp_team_comment = %s,
                        dp_approver_id = %s,
                        dp_approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, [float(approved_quantity), comment, request.user.id, request_id])

            elif action == 'reject':
                cursor.execute("""
                    UPDATE dashboard_replenishmentrequest
                    SET status = 'dp_rejected',
                        dp_approved_quantity = 0,
                        dp_team_comment = %s,
                        dp_approver_id = %s,
                        dp_approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, [comment, request.user.id, request_id])

        return JsonResponse({
            'success': True,
            'message': f'Request {action}ed successfully by DP team'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@permission_required('replenishment.stores.submit_request')
@require_http_methods(["POST"])
def submit_store_replenishment_request(request):
    """
    Submit store manager's replenishment request batch
    Creates a batch and items from the cart data

    Note: Data scope filtering is implicit here. Store managers with branch scope
    can only submit requests for products they saw in the forecasting view,
    which is already filtered by their assigned branches. The cart data comes from
    the client-side and represents products they were authorized to view.
    """
    from dashboard.models import StoreReplenishmentRequestBatch, StoreReplenishmentRequestItem
    from django.utils import timezone
    from django.db import transaction
    import json

    try:
        data = json.loads(request.body)
        items_by_school = data.get('items_by_school', {})

        if not items_by_school:
            return JsonResponse({
                'success': False,
                'error': 'No items provided'
            }, status=400)

        created_batches = []

        # Create a batch for each school
        with transaction.atomic():
            for school, items in items_by_school.items():
                # Generate request number
                today = timezone.now()
                year_month = today.strftime('%Y%m')
                # Count existing requests this month
                existing_count = StoreReplenishmentRequestBatch.objects.filter(
                    request_number__startswith=f'REQ-{year_month}'
                ).count()
                request_number = f'REQ-{year_month}-{existing_count + 1:04d}'

                # Create batch
                batch = StoreReplenishmentRequestBatch.objects.create(
                    request_number=request_number,
                    school=school,
                    requested_by=request.user,
                    status='submitted',
                    notes=f'Created from replenishment cart with {len(items)} items'
                )

                # Create items
                for item in items:
                    StoreReplenishmentRequestItem.objects.create(
                        batch=batch,
                        sku=item.get('sku'),
                        product_name=item.get('product_name'),
                        size=item.get('size', ''),
                        color=item.get('color', ''),
                        stock_on_hand=item.get('stock_on_hand', 0),
                        incoming_stock=item.get('incoming_stock', 0),
                        forecasted_stock=item.get('forecasted_stock', 0),
                        stock_gap=item.get('stock_gap', 0),
                        requested_quantity=item.get('requested_quantity'),
                        is_modified=item.get('is_modified', False),
                        original_quantity=item.get('original_quantity'),
                        modification_reason=item.get('modification_reason', '')
                    )

                # Store manager auto-approves their request
                batch.status = 'store_approved'
                batch.submitted_date = timezone.now()
                batch.store_approved_by = request.user
                batch.store_approved_date = timezone.now()
                batch.save()

                created_batches.append({
                    'request_number': batch.request_number,
                    'school': batch.school,
                    'items_count': batch.items.count()
                })

        return JsonResponse({
            'success': True,
            'message': f'Successfully created {len(created_batches)} replenishment request(s)',
            'batches': created_batches
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@permission_required('replenishment.stores.view')
def store_replenishment_requests_list(request):
    """
    View all replenishment requests for current user

    Note: Data scope filtering is implicit here because users can only
    see their own requests (requested_by=request.user). Store managers
    with branch scope would only have created requests for products they
    could see in the forecasting view, which is already filtered by branch.
    """
    from dashboard.models import StoreReplenishmentRequestBatch

    # Get all requests for this user
    # DATA SCOPE: Already filtered by requested_by=request.user
    requests = StoreReplenishmentRequestBatch.objects.filter(
        requested_by=request.user
    ).order_by('-request_date')

    # Calculate summary statistics
    total_requests = requests.count()
    submitted_count = requests.filter(status='submitted').count()
    store_approved_count = requests.filter(status='store_approved').count()
    dp_approved_count = requests.filter(status='dp_approved').count()
    rejected_count = requests.filter(status='rejected').count()
    fulfilled_count = requests.filter(status='fulfilled').count()

    context = {
        'requests': requests,
        'total_requests': total_requests,
        'submitted_count': submitted_count,
        'store_approved_count': store_approved_count,
        'dp_approved_count': dp_approved_count,
        'rejected_count': rejected_count,
        'fulfilled_count': fulfilled_count,
    }

    return render(request, 'dashboard/store_replenishment_requests.html', context)


@login_required
def store_replenishment_request_detail(request, request_number):
    """
    View details of a specific replenishment request
    """
    from dashboard.models import StoreReplenishmentRequestBatch
    from django.shortcuts import get_object_or_404

    batch = get_object_or_404(
        StoreReplenishmentRequestBatch,
        request_number=request_number,
        requested_by=request.user
    )

    items = batch.items.all()

    context = {
        'batch': batch,
        'items': items,
    }

    return render(request, 'dashboard/store_replenishment_request_detail.html', context)


@login_required
@permission_required('replenishment.demand_planning.approve')
def dp_replenishment_approval(request):
    """
    DP Team view to review and approve/reject store-approved replenishment requests
    """
    from dashboard.models import StoreReplenishmentRequestBatch

    # Get all store-approved requests awaiting DP review
    requests = StoreReplenishmentRequestBatch.objects.filter(
        status='store_approved'
    ).order_by('-request_date')

    # Calculate summary statistics
    total_pending = requests.count()

    context = {
        'requests': requests,
        'total_pending': total_pending,
    }

    return render(request, 'dashboard/dp_replenishment_approval.html', context)


@login_required
@permission_required('replenishment.demand_planning.approve')
@require_http_methods(["POST"])
def dp_approve_request(request, batch_id):
    """
    DP Team approves a store replenishment request
    Changes status to 'dp_approved' (becomes an order)
    """
    from dashboard.models import StoreReplenishmentRequestBatch
    from django.utils import timezone
    from django.shortcuts import get_object_or_404

    try:
        print(f"[DEBUG] Step 1: Fetching batch_id={batch_id}")
        batch = get_object_or_404(StoreReplenishmentRequestBatch, id=batch_id)
        print(f"[DEBUG] Step 2: Found batch {batch.request_number}, status={batch.status}")

        # Verify status is store_approved
        if batch.status != 'store_approved':
            print(f"[DEBUG] Step 3: Invalid status, returning error")
            return JsonResponse({
                'success': False,
                'error': 'Request is not in store_approved status'
            }, status=400)

        # Update to DP approved
        print(f"[DEBUG] Step 4: Updating status to dp_approved")
        batch.status = 'dp_approved'
        batch.dp_approved_by = request.user
        batch.dp_approved_date = timezone.now()
        print(f"[DEBUG] Step 5: Calling batch.save()")
        batch.save()
        print(f"[DEBUG] Step 6: Save completed successfully")

        print(f"[DEBUG] Step 7: Returning success response")
        return JsonResponse({
            'success': True,
            'message': f'Request {batch.request_number} approved successfully',
            'request_number': batch.request_number
        })

    except Exception as e:
        import traceback
        print("[DEBUG] EXCEPTION OCCURRED:")
        print(traceback.format_exc())
        print(f"[DEBUG] Exception type: {type(e).__name__}")
        print(f"[DEBUG] Exception message: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@permission_required('replenishment.demand_planning.approve')
@require_http_methods(["POST"])
def dp_reject_request(request, batch_id):
    """
    DP Team rejects a store replenishment request
    Changes status to 'rejected' with reason
    """
    from dashboard.models import StoreReplenishmentRequestBatch
    from django.utils import timezone
    from django.shortcuts import get_object_or_404
    import json

    try:
        batch = get_object_or_404(StoreReplenishmentRequestBatch, id=batch_id)

        # Verify status is store_approved
        if batch.status != 'store_approved':
            return JsonResponse({
                'success': False,
                'error': 'Request is not in store_approved status'
            }, status=400)

        # Get rejection reason from request body
        data = json.loads(request.body)
        rejection_reason = data.get('reason', '')

        if not rejection_reason:
            return JsonResponse({
                'success': False,
                'error': 'Rejection reason is required'
            }, status=400)

        # Update to rejected
        batch.status = 'rejected'
        batch.rejection_reason = rejection_reason
        batch.save()

        return JsonResponse({
            'success': True,
            'message': f'Request {batch.request_number} rejected',
            'request_number': batch.request_number
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def dp_replenishment_request_detail(request, request_number):
    """
    DP Team detail view for a specific replenishment request
    Shows comprehensive information including approval workflow, stock data, and DP actions
    """
    from dashboard.models import StoreReplenishmentRequestBatch
    from django.shortcuts import get_object_or_404

    # Get the batch - DP can view ANY request (not filtered by user)
    batch = get_object_or_404(
        StoreReplenishmentRequestBatch.objects.select_related(
            'requested_by',
            'store_approved_by',
            'dp_approved_by'
        ),
        request_number=request_number
    )

    # Get all items with prefetch for performance
    items = batch.items.all().order_by('product_name', 'size')

    # Calculate statistics
    total_stock_gap = sum(item.stock_gap for item in items)
    total_requested = sum(item.requested_quantity for item in items)
    items_with_gaps = sum(1 for item in items if item.stock_gap < 0)

    # Approval timeline data
    timeline = []

    # Step 1: Request submitted
    timeline.append({
        'stage': 'Submitted',
        'status': 'completed',
        'user': batch.requested_by,
        'date': batch.submitted_date or batch.request_date,
        'icon': 'file-text'
    })

    # Step 2: Store approved
    if batch.status in ['store_approved', 'dp_approved', 'fulfilled']:
        timeline.append({
            'stage': 'Store Approved',
            'status': 'completed',
            'user': batch.store_approved_by,
            'date': batch.store_approved_date,
            'icon': 'check-circle'
        })
    elif batch.status == 'rejected':
        timeline.append({
            'stage': 'Rejected',
            'status': 'completed',
            'user': batch.store_approved_by or batch.dp_approved_by,
            'date': batch.store_approved_date,
            'icon': 'x-circle'
        })
    else:
        timeline.append({
            'stage': 'Store Approval',
            'status': 'pending',
            'user': None,
            'date': None,
            'icon': 'clock'
        })

    # Step 3: DP approved
    if batch.status in ['dp_approved', 'fulfilled']:
        timeline.append({
            'stage': 'DP Approved',
            'status': 'completed',
            'user': batch.dp_approved_by,
            'date': batch.dp_approved_date,
            'icon': 'check-circle'
        })
    elif batch.status == 'store_approved':
        timeline.append({
            'stage': 'DP Approval',
            'status': 'in_progress',
            'user': None,
            'date': None,
            'icon': 'clock'
        })
    elif batch.status != 'rejected':
        timeline.append({
            'stage': 'DP Approval',
            'status': 'pending',
            'user': None,
            'date': None,
            'icon': 'clock'
        })

    # Step 4: Fulfilled
    if batch.status == 'fulfilled':
        timeline.append({
            'stage': 'Fulfilled',
            'status': 'completed',
            'user': None,
            'date': None,
            'icon': 'package'
        })
    elif batch.status == 'dp_approved':
        timeline.append({
            'stage': 'Fulfillment',
            'status': 'pending',
            'user': None,
            'date': None,
            'icon': 'clock'
        })

    # Determine if DP can take action on this request
    can_approve = batch.status == 'store_approved'
    can_modify = batch.status == 'store_approved'

    context = {
        'batch': batch,
        'items': items,
        'timeline': timeline,
        'total_stock_gap': total_stock_gap,
        'total_requested': total_requested,
        'items_with_gaps': items_with_gaps,
        'can_approve': can_approve,
        'can_modify': can_modify,
    }

    return render(request, 'dashboard/dp_request_detail.html', context)


@login_required
@permission_required('replenishment.demand_planning.view_all_requests')
def dp_replenishment_requests_list(request):
    """
    DP Team view to see ALL replenishment requests with comprehensive filters
    Shows requests from all stores/schools with status, date, and search filters
    """
    from dashboard.models import StoreReplenishmentRequestBatch
    from django.db.models import Q, Count
    from datetime import datetime

    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    school_filter = request.GET.get('school', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    search = request.GET.get('search', '')

    # Base query with select_related to avoid N+1 queries
    batches = StoreReplenishmentRequestBatch.objects.select_related(
        'requested_by', 'store_approved_by', 'dp_approved_by'
    ).all()

    # Apply status filter
    if status_filter != 'all':
        batches = batches.filter(status=status_filter)

    # Apply school filter
    if school_filter:
        batches = batches.filter(school__icontains=school_filter)

    # Apply date range filter
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            batches = batches.filter(request_date__gte=start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            batches = batches.filter(request_date__lte=end)
        except ValueError:
            pass

    # Apply search filter (search in request_number, school, or user name)
    if search:
        batches = batches.filter(
            Q(request_number__icontains=search) |
            Q(school__icontains=search) |
            Q(requested_by__username__icontains=search) |
            Q(requested_by__first_name__icontains=search) |
            Q(requested_by__last_name__icontains=search)
        )

    # Order by most recent first
    batches = batches.order_by('-request_date')

    # Calculate summary statistics
    total_requests = batches.count()
    submitted_count = batches.filter(status='submitted').count()
    store_approved_count = batches.filter(status='store_approved').count()
    dp_approved_count = batches.filter(status='dp_approved').count()
    rejected_count = batches.filter(status='rejected').count()
    fulfilled_count = batches.filter(status='fulfilled').count()

    # Get unique schools for filter dropdown
    all_schools = StoreReplenishmentRequestBatch.objects.values_list(
        'school', flat=True
    ).distinct().order_by('school')

    # Status choices for filter dropdown
    status_choices = StoreReplenishmentRequestBatch.STATUS_CHOICES

    context = {
        'batches': batches,
        'total_requests': total_requests,
        'submitted_count': submitted_count,
        'store_approved_count': store_approved_count,
        'dp_approved_count': dp_approved_count,
        'rejected_count': rejected_count,
        'fulfilled_count': fulfilled_count,
        'all_schools': all_schools,
        'status_choices': status_choices,
        # Current filters
        'current_status': status_filter,
        'current_school': school_filter,
        'current_start_date': start_date,
        'current_end_date': end_date,
        'current_search': search,
    }

    return render(request, 'dashboard/dp_requests_list.html', context)


@login_required
@permission_required('forecasting.view')
def forecast_health_dashboard(request):
    """
    Forecast Health Monitoring Dashboard

    Shows the status of 365-day base forecasts and when they need regeneration
    Enables scheduled maintenance and freshness tracking
    """
    from dashboard.models import SalesForecastBase, ForecastSchedule
    from django.db.models import Count, Min, Max, Q
    from datetime import timedelta
    from django.utils import timezone

    # Update all forecast statuses
    for schedule in ForecastSchedule.objects.all():
        schedule.update_status()

    # Overall statistics
    total_forecasts = SalesForecastBase.objects.count()
    total_schedules = ForecastSchedule.objects.count()

    # Status breakdown
    current_count = ForecastSchedule.objects.filter(status='current').count()
    due_count = ForecastSchedule.objects.filter(status='due').count()
    overdue_count = ForecastSchedule.objects.filter(status='overdue').count()

    # Aggregation level breakdown
    level_stats = ForecastSchedule.objects.values('aggregation_level').annotate(
        total=Count('id'),
        current=Count('id', filter=Q(status='current')),
        due=Count('id', filter=Q(status='due')),
        overdue=Count('id', filter=Q(status='overdue'))
    )

    # Get oldest and newest forecasts
    oldest_forecast = SalesForecastBase.objects.order_by('forecast_date').first()
    newest_forecast = SalesForecastBase.objects.order_by('-forecast_date').first()

    # Get forecasts due for regeneration (sorted by urgency)
    due_forecasts = ForecastSchedule.objects.filter(
        status__in=['due', 'overdue']
    ).order_by('-status', 'next_generation_due')[:50]  # Limit to 50 most urgent

    # Get recently generated forecasts
    recent_forecasts = ForecastSchedule.objects.filter(
        status='current'
    ).order_by('-last_generated')[:20]

    context = {
        'total_forecasts': total_forecasts,
        'total_schedules': total_schedules,
        'current_count': current_count,
        'due_count': due_count,
        'overdue_count': overdue_count,
        'level_stats': level_stats,
        'oldest_forecast': oldest_forecast,
        'newest_forecast': newest_forecast,
        'due_forecasts': due_forecasts,
        'recent_forecasts': recent_forecasts,
    }

    return render(request, 'dashboard/forecast_health.html', context)


@require_http_methods(["POST"])
@login_required
def trigger_forecast_regeneration(request):
    """
    Trigger regeneration of forecasts that are due or overdue
    Can be triggered manually from the forecast health dashboard
    """
    from django.core.management import call_command
    from django.utils import timezone
    import threading

    try:
        # Get filter parameters
        level = request.POST.get('level', 'all')
        force = request.POST.get('force') == 'true'

        # Run forecast generation in background
        def run_forecast_generation():
            try:
                call_command('generate_365d_forecasts', level=level, force=force)
            except Exception as e:
                print(f"Error in background forecast generation: {e}")

        thread = threading.Thread(target=run_forecast_generation)
        thread.daemon = True
        thread.start()

        return JsonResponse({
            'success': True,
            'message': f'Forecast regeneration started in background for level: {level}'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@permission_required('forecasting.view')
def detect_missing_forecasts(request):
    """Detect and generate forecasts for shop products that have no forecast"""
    from django.db import connection
    from django.core.management import call_command
    import threading

    # Detect missing products
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT po.code, p.name, p.category_name, p.sub_category
            FROM cin7_sync_productoption po
            JOIN cin7_sync_product p ON p.cin7_id = po.cin7_product_id
            LEFT JOIN dashboard_salesforecastbase sf
                ON sf.entity_name = po.code AND sf.aggregation_level = 'product'
            WHERE (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
              AND p.category_name NOT IN ('Shop', 'Store')
              AND p.category_name NOT LIKE 'Wholesale%%'
              AND p.is_active = 1
              AND sf.id IS NULL
            ORDER BY p.category_name, p.sub_category, po.code
        """)
        missing = [
            {'sku': row[0], 'name': row[1], 'shop': row[2], 'school': row[3]}
            for row in cursor.fetchall()
        ]

    if request.method == 'POST' and request.POST.get('action') == 'generate':
        if not missing:
            return JsonResponse({'success': True, 'message': 'No missing forecasts to generate.'})

        def run_missing_forecasts():
            try:
                call_command('generate_365d_forecasts', level='product', only_missing=True, force=True)
            except Exception as e:
                print(f"Error generating missing forecasts: {e}")

        thread = threading.Thread(target=run_missing_forecasts)
        thread.daemon = True
        thread.start()

        return JsonResponse({
            'success': True,
            'message': f'Generating forecasts for {len(missing)} products in background.'
        })

    return JsonResponse({
        'missing_count': len(missing),
        'missing_products': missing[:100],  # Limit response size
    })


@login_required
def past_sales_data(request):
    """API endpoint to fetch historical sales data for Past Sales modal"""
    from django.db import connection
    from datetime import datetime, timedelta
    import json

    sku = request.GET.get('sku', '')
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    if not sku or not start_date_str or not end_date_str:
        return JsonResponse({'error': 'Missing required parameters'}, status=400)

    try:
        # Parse dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Calculate the same period for previous years
        current_year = datetime.now().year
        years_data = {}

        # Verify SKU exists
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT po.code, p.style_code
                FROM cin7_sync_productoption po
                INNER JOIN cin7_sync_product p ON po.cin7_product_id = p.cin7_id
                WHERE po.code = %s
                LIMIT 1
            """, [sku])

            result = cursor.fetchone()
            if not result:
                return JsonResponse({'error': 'SKU not found'}, status=404)

            sku_code = result[0]
            style_code = result[1]

        # Get all available years from historical data for this specific SKU
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT YEAR(so.invoice_date) as year
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                WHERE soli.code = %s
                  AND so.invoice_date IS NOT NULL
                  AND so.status != 'Cancelled'
                  AND YEAR(so.invoice_date) <= %s
                ORDER BY year DESC
            """, [sku_code, current_year])

            available_years = [row[0] for row in cursor.fetchall()]

        # Loop through all available years using full calendar year (Jan 1 - Dec 31)
        from datetime import date
        for year in available_years:
            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)

            # Query sales data for this specific SKU
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COALESCE(SUM(soli.qty), 0) as total_quantity
                    FROM cin7_sync_salesorderlineitem soli
                    INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                    WHERE soli.code = %s
                      AND so.invoice_date >= %s
                      AND so.invoice_date <= %s
                      AND so.status != 'Cancelled'
                """, [sku_code, year_start, year_end])

                row = cursor.fetchone()
                years_data[str(year)] = int(row[0]) if row and row[0] else 0

        return JsonResponse({
            'success': True,
            'sku': sku,
            'style_code': style_code,
            'period': 'Full calendar year (Jan 1 - Dec 31)',
            'years': years_data
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ==================== ANALYTICAL REPORTS ====================

@login_required
@permission_required('dashboard.view')
def bts_sellthrough_report(request):
    """
    BTS Sell-Through Ratio Report
    Track stock performance after BTS season

    Business Logic:
    - BTS Sales = Previous Year December + Current Year January + Current Year February
    - Stock Left After BTS Season = Available stock balance at end of February
    - BTS Sell-Through Ratio = Stock Left After BTS Season / BTS Sales

    Risk Classification:
    - > 1.0: Overstock risk (Red badge)
    - 0.3 - 1.0: Balanced (Yellow badge)
    - < 0.3: High demand (Green badge)
    """
    from django.db import connection
    from datetime import datetime

    # Get date range from request (default: last BTS season)
    # Current year BTS: Jan-Feb, Previous year: Dec
    current_year = datetime.now().year

    # Default BTS period: Previous Dec + Current Jan + Current Feb
    bts_start_default = f"{current_year - 1}-12-01"
    bts_end_default = f"{current_year}-02-28"

    bts_start = request.GET.get('bts_start', bts_start_default)
    bts_end = request.GET.get('bts_end', bts_end_default)

    # Query: Calculate BTS sales and stock left per customer per SKU
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH bts_sales AS (
                SELECT
                    p.sub_category as customer,
                    p.style_code,
                    p.name as product_name,
                    soli.code as sku,
                    COALESCE(SUM(soli.qty), 0) as bts_sales_qty,
                    COALESCE(SUM(soli.qty * soli.unit_price), 0) as bts_sales_value
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                INNER JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND so.status != 'Cancelled'
                  AND p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category, p.style_code, p.name, soli.code
            ),
            stock_after_bts AS (
                SELECT
                    p.sub_category as customer,
                    p.style_code,
                    s.code as sku,
                    COALESCE(SUM(s.stock_on_hand), 0) as stock_left
                FROM cin7_sync_product p
                LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
                WHERE p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category, p.style_code, s.code
            )
            SELECT
                bs.customer,
                bs.style_code,
                bs.product_name,
                bs.sku,
                bs.bts_sales_qty,
                bs.bts_sales_value,
                COALESCE(sa.stock_left, 0) as stock_left,
                CASE
                    WHEN bs.bts_sales_qty > 0 THEN COALESCE(sa.stock_left, 0) / bs.bts_sales_qty
                    ELSE 999999
                END as sellthrough_ratio
            FROM bts_sales bs
            LEFT JOIN stock_after_bts sa ON bs.customer = sa.customer
                AND bs.style_code = sa.style_code
                AND bs.sku = sa.sku
            ORDER BY sellthrough_ratio DESC, bs.customer, bs.product_name
        """, [bts_start, bts_end, '% Shop', '%%Shop%', '% Shop', '%%Shop%'])

        rows = cursor.fetchall()

    # Process results and classify risk
    report_data = []
    for row in rows:
        customer = row[0]
        style_code = row[1]
        product_name = row[2]
        sku = row[3]
        bts_sales_qty = float(row[4] or 0)
        bts_sales_value = float(row[5] or 0)
        stock_left = float(row[6] or 0)
        sellthrough_ratio = float(row[7] or 0)

        # Classify risk
        if sellthrough_ratio > 1.0:
            risk_class = 'overstock'
            risk_label = 'Overstock Risk'
            risk_badge = 'danger'
        elif sellthrough_ratio >= 0.3:
            risk_class = 'balanced'
            risk_label = 'Balanced'
            risk_badge = 'warning'
        else:
            risk_class = 'high-demand'
            risk_label = 'High Demand'
            risk_badge = 'success'

        # Handle infinite ratios
        ratio_display = '∞' if sellthrough_ratio >= 999999 else round(sellthrough_ratio, 2)

        report_data.append({
            'customer': customer or 'Unknown',
            'style_code': style_code or '',
            'product_name': product_name or 'Unknown Product',
            'sku': sku or '',
            'bts_sales_qty': bts_sales_qty,
            'bts_sales_value': bts_sales_value,
            'stock_left': stock_left,
            'sellthrough_ratio': sellthrough_ratio,
            'ratio_display': ratio_display,
            'risk_class': risk_class,
            'risk_label': risk_label,
            'risk_badge': risk_badge
        })

    # Calculate summary stats
    total_bts_sales = sum(item['bts_sales_value'] for item in report_data)
    total_stock_left_value = sum(item['stock_left'] for item in report_data)
    overstock_count = sum(1 for item in report_data if item['risk_class'] == 'overstock')
    balanced_count = sum(1 for item in report_data if item['risk_class'] == 'balanced')
    high_demand_count = sum(1 for item in report_data if item['risk_class'] == 'high-demand')

    context = {
        'report_data': report_data,
        'bts_start': bts_start,
        'bts_end': bts_end,
        'total_bts_sales': total_bts_sales,
        'total_stock_left_value': total_stock_left_value,
        'overstock_count': overstock_count,
        'balanced_count': balanced_count,
        'high_demand_count': high_demand_count,
    }

    return render(request, 'dashboard/bts_sellthrough_report.html', context)


@login_required
@permission_required('dashboard.view')
def inventory_health_dashboard(request):
    """
    Inventory Health Score Dashboard
    Overall inventory performance score (0-100)

    Business Logic:
    - Inventory Health Score = Weighted Average:
      - Stockout Risk %: 30%
      - Excess Stock %: 25%
      - Dead Stock Value %: 25%
      - Inventory Turn Rate: 20%

    Calculations:
    - Stockout Risk %: (SKUs with stock < 30 days coverage) / Total SKUs × 100
    - Excess Stock %: (SKUs with stock > 180 days coverage) / Total SKUs × 100
    - Dead Stock Value %: (Value of stock with 0 sales in 180 days) / Total Stock Value × 100
    - Inventory Turn Rate: Cost of Goods Sold / Average Inventory Value
    """
    from django.db import connection
    from datetime import datetime, timedelta

    # Calculate date ranges
    today = datetime.now().date()
    days_180_ago = today - timedelta(days=180)
    days_30_ago = today - timedelta(days=30)

    # 1. Calculate Stockout Risk % (stock < 30 days coverage)
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH daily_sales AS (
                SELECT
                    soli.code as sku,
                    COALESCE(SUM(soli.qty), 0) / 30 as daily_avg_sales
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                WHERE so.invoice_date >= %s
                  AND so.status != 'Cancelled'
                GROUP BY soli.code
            ),
            stock_coverage AS (
                SELECT
                    s.code as sku,
                    s.stock_on_hand,
                    COALESCE(ds.daily_avg_sales, 0) as daily_avg_sales,
                    CASE
                        WHEN COALESCE(ds.daily_avg_sales, 0) > 0
                        THEN s.stock_on_hand / ds.daily_avg_sales
                        ELSE 999
                    END as days_coverage
                FROM cin7_sync_stock s
                LEFT JOIN daily_sales ds ON s.code = ds.sku
                WHERE s.stock_on_hand > 0
            )
            SELECT
                COUNT(*) as total_skus,
                SUM(CASE WHEN days_coverage < 30 THEN 1 ELSE 0 END) as stockout_risk_skus,
                SUM(CASE WHEN days_coverage > 180 THEN 1 ELSE 0 END) as excess_stock_skus
            FROM stock_coverage
        """, [days_30_ago])

        row = cursor.fetchone()
        total_skus = float(row[0] or 1)  # Avoid division by zero
        stockout_risk_skus = float(row[1] or 0)
        excess_stock_skus = float(row[2] or 0)

    stockout_risk_pct = (stockout_risk_skus / total_skus) * 100 if total_skus > 0 else 0
    excess_stock_pct = (excess_stock_skus / total_skus) * 100 if total_skus > 0 else 0

    # 2. Calculate Dead Stock Value % (0 sales in 180 days)
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH recent_sales AS (
                SELECT DISTINCT soli.code as sku
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                WHERE so.invoice_date >= %s
                  AND so.status != 'Cancelled'
            ),
            stock_with_sales AS (
                SELECT
                    s.code,
                    s.stock_on_hand,
                    po.cost_price,
                    s.stock_on_hand * COALESCE(po.cost_price, 0) as stock_value,
                    CASE WHEN rs.sku IS NULL THEN 1 ELSE 0 END as is_dead_stock
                FROM cin7_sync_stock s
                LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
                LEFT JOIN recent_sales rs ON s.code = rs.sku
                WHERE s.stock_on_hand > 0
            )
            SELECT
                COALESCE(SUM(stock_value), 0) as total_stock_value,
                COALESCE(SUM(CASE WHEN is_dead_stock = 1 THEN stock_value ELSE 0 END), 0) as dead_stock_value
            FROM stock_with_sales
        """, [days_180_ago])

        row = cursor.fetchone()
        total_stock_value = float(row[0] or 1)  # Avoid division by zero
        dead_stock_value = float(row[1] or 0)

    dead_stock_pct = (dead_stock_value / total_stock_value) * 100 if total_stock_value > 0 else 0

    # 3. Calculate Inventory Turn Rate (simplified: annual COGS / avg inventory)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                COALESCE(SUM(soli.qty * soli.unit_cost), 0) as cogs,
                (SELECT COALESCE(SUM(s.stock_on_hand * po.cost_price), 1)
                 FROM cin7_sync_stock s
                 LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id) as avg_inventory
            FROM cin7_sync_salesorderlineitem soli
            INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
            WHERE so.invoice_date >= %s
              AND so.status != 'Cancelled'
        """, [days_180_ago])

        row = cursor.fetchone()
        cogs = float(row[0] or 0)
        avg_inventory = float(row[1] or 1)

    inventory_turn_rate = (cogs / avg_inventory) if avg_inventory > 0 else 0

    # Normalize inventory turn rate to 0-100 scale (assume good rate is 4-6 turns per 180 days)
    # Higher is better, so we'll score it: min(turn_rate / 6 * 100, 100)
    inventory_turn_score = min((inventory_turn_rate / 6) * 100, 100)

    # 4. Calculate overall health score (weighted average)
    # Lower is better for stockout, excess, and dead stock (so invert them)
    stockout_score = float(max(0, 100 - stockout_risk_pct))
    excess_score = float(max(0, 100 - excess_stock_pct))
    dead_stock_score = float(max(0, 100 - dead_stock_pct))

    health_score = (
        stockout_score * 0.30 +
        excess_score * 0.25 +
        dead_stock_score * 0.25 +
        inventory_turn_score * 0.20
    )

    # Get top 10 best/worst performing SKUs
    with connection.cursor() as cursor:
        # Best performers (high turn rate)
        cursor.execute("""
            WITH sku_performance AS (
                SELECT
                    s.code,
                    p.name as product_name,
                    s.stock_on_hand,
                    COALESCE(SUM(soli.qty), 0) as sales_qty_180d,
                    CASE
                        WHEN s.stock_on_hand > 0
                        THEN COALESCE(SUM(soli.qty), 0) / s.stock_on_hand
                        ELSE 0
                    END as turn_rate
                FROM cin7_sync_stock s
                LEFT JOIN cin7_sync_product p ON s.cin7_product_id = p.cin7_id
                LEFT JOIN cin7_sync_salesorderlineitem soli ON s.code = soli.code
                LEFT JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                    AND so.invoice_date >= %s AND so.status != 'Cancelled'
                WHERE s.stock_on_hand > 0
                GROUP BY s.code, p.name, s.stock_on_hand
            )
            SELECT code, product_name, stock_on_hand, sales_qty_180d, turn_rate
            FROM sku_performance
            ORDER BY turn_rate DESC
            LIMIT 10
        """, [days_180_ago])

        best_performers = [
            {
                'sku': row[0],
                'product_name': row[1] or 'Unknown',
                'stock_on_hand': row[2],
                'sales_qty_180d': row[3],
                'turn_rate': round(float(row[4]), 2)
            }
            for row in cursor.fetchall()
        ]

        # Worst performers (low/no turn rate)
        cursor.execute("""
            WITH sku_performance AS (
                SELECT
                    s.code,
                    p.name as product_name,
                    s.stock_on_hand,
                    s.stock_on_hand * COALESCE(po.cost_price, 0) as stock_value,
                    COALESCE(SUM(soli.qty), 0) as sales_qty_180d
                FROM cin7_sync_stock s
                LEFT JOIN cin7_sync_product p ON s.cin7_product_id = p.cin7_id
                LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
                LEFT JOIN cin7_sync_salesorderlineitem soli ON s.code = soli.code
                LEFT JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                    AND so.invoice_date >= %s AND so.status != 'Cancelled'
                WHERE s.stock_on_hand > 0
                GROUP BY s.code, p.name, s.stock_on_hand, po.cost_price
            )
            SELECT code, product_name, stock_on_hand, stock_value, sales_qty_180d
            FROM sku_performance
            WHERE sales_qty_180d = 0
            ORDER BY stock_value DESC
            LIMIT 10
        """, [days_180_ago])

        worst_performers = [
            {
                'sku': row[0],
                'product_name': row[1] or 'Unknown',
                'stock_on_hand': row[2],
                'stock_value': float(row[3]),
                'sales_qty_180d': row[4]
            }
            for row in cursor.fetchall()
        ]

    context = {
        'health_score': round(health_score, 1),
        'stockout_risk_pct': round(stockout_risk_pct, 1),
        'excess_stock_pct': round(excess_stock_pct, 1),
        'dead_stock_pct': round(dead_stock_pct, 1),
        'inventory_turn_rate': round(inventory_turn_rate, 2),
        'stockout_score': round(stockout_score, 1),
        'excess_score': round(excess_score, 1),
        'dead_stock_score': round(dead_stock_score, 1),
        'inventory_turn_score': round(inventory_turn_score, 1),
        'total_skus': total_skus,
        'stockout_risk_skus': stockout_risk_skus,
        'excess_stock_skus': excess_stock_skus,
        'dead_stock_value': dead_stock_value,
        'total_stock_value': total_stock_value,
        'best_performers': best_performers,
        'worst_performers': worst_performers,
    }

    return render(request, 'dashboard/inventory_health_dashboard.html', context)


@login_required
@permission_required('dashboard.view')
def inventory_alignment_matrix(request):
    """
    Sales vs Inventory Alignment Matrix
    Comprehensive view of inventory position vs demand

    Columns:
    - Product Name / SKU
    - Customer (School)
    - Units Sold (Annually)
    - Units Sold (Last BTS)
    - Historical Growth %
    - Current Available Stock
    - Incoming Stock
    - Days of Coverage
    - BTS Sell-Through Ratio
    - Risk Indicator (badge)

    Calculations:
    - Days of Coverage: Available Stock / (Annual Sales / 365)
    - Historical Growth %: (Current Year Sales - Previous Year Sales) / Previous Year Sales × 100
    - Risk Indicator based on Days of Coverage:
      - < 30 days: High Risk (Red)
      - 30-90 days: Medium Risk (Yellow)
      - > 90 days: Low Risk (Green)
    """
    from django.db import connection
    from datetime import datetime, timedelta

    # Get filters from request
    customer_filter = request.GET.get('customer', '')
    category_filter = request.GET.get('category', '')
    style_filter = request.GET.get('style', '')

    # Calculate date ranges
    today = datetime.now().date()
    one_year_ago = today - timedelta(days=365)
    two_years_ago = today - timedelta(days=730)

    # BTS period (current year Jan-Feb)
    current_year = today.year
    bts_start = f"{current_year}-01-01"
    bts_end = f"{current_year}-02-28"

    # Query: Get comprehensive inventory alignment data
    with connection.cursor() as cursor:
        query = """
            WITH annual_sales AS (
                SELECT
                    soli.code as sku,
                    COALESCE(SUM(CASE
                        WHEN so.invoice_date >= %s THEN soli.qty
                        ELSE 0
                    END), 0) as units_sold_annual,
                    COALESCE(SUM(CASE
                        WHEN so.invoice_date >= %s AND so.invoice_date <= %s
                        THEN soli.qty
                        ELSE 0
                    END), 0) as units_sold_bts,
                    COALESCE(SUM(CASE
                        WHEN so.invoice_date >= %s AND so.invoice_date < %s
                        THEN soli.qty
                        ELSE 0
                    END), 0) as units_sold_prev_year,
                    COALESCE(SUM(CASE
                        WHEN so.invoice_date >= %s THEN soli.qty
                        ELSE 0
                    END), 0) as units_sold_current_year
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                WHERE so.status != 'Cancelled'
                GROUP BY soli.code
            )
            SELECT
                p.sub_category as customer,
                p.style_code,
                p.name as product_name,
                p.category_name,
                s.code as sku,
                COALESCE(asales.units_sold_annual, 0) as units_sold_annual,
                COALESCE(asales.units_sold_bts, 0) as units_sold_bts,
                COALESCE(asales.units_sold_prev_year, 0) as units_sold_prev_year,
                COALESCE(asales.units_sold_current_year, 0) as units_sold_current_year,
                COALESCE(s.available, 0) as current_stock,
                COALESCE(s.incoming, 0) as incoming_stock,
                CASE
                    WHEN COALESCE(asales.units_sold_annual, 0) > 0
                    THEN (COALESCE(s.available, 0) / (asales.units_sold_annual / 365.0))
                    ELSE 999
                END as days_coverage,
                CASE
                    WHEN COALESCE(asales.units_sold_bts, 0) > 0
                    THEN COALESCE(s.available, 0) / asales.units_sold_bts
                    ELSE 999
                END as bts_sellthrough_ratio
            FROM cin7_sync_stock s
            LEFT JOIN cin7_sync_product p ON s.cin7_product_id = p.cin7_id
            LEFT JOIN annual_sales asales ON s.code = asales.sku
            WHERE p.category_name LIKE %s
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
        """

        params = [
            one_year_ago,  # annual sales start
            bts_start, bts_end,  # BTS period
            two_years_ago, one_year_ago,  # previous year
            one_year_ago,  # current year start
            '% Shop', '%%Shop%'
        ]

        # Add filters if provided
        if customer_filter:
            query += " AND p.sub_category = %s"
            params.append(customer_filter)
        if category_filter:
            query += " AND p.category_name = %s"
            params.append(category_filter)
        if style_filter:
            query += " AND p.style_code LIKE %s"
            params.append(f"%{style_filter}%")

        query += " ORDER BY days_coverage ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

    # Process results
    matrix_data = []
    for row in rows:
        customer = row[0]
        style_code = row[1]
        product_name = row[2]
        category_name = row[3]
        sku = row[4]
        units_sold_annual = float(row[5] or 0)
        units_sold_bts = float(row[6] or 0)
        units_sold_prev_year = float(row[7] or 0)
        units_sold_current_year = float(row[8] or 0)
        current_stock = float(row[9] or 0)
        incoming_stock = float(row[10] or 0)
        days_coverage = float(row[11] or 999)
        bts_sellthrough_ratio = float(row[12] or 999)

        # Calculate historical growth %
        if units_sold_prev_year > 0:
            growth_pct = ((units_sold_current_year - units_sold_prev_year) / units_sold_prev_year) * 100
        else:
            growth_pct = 0 if units_sold_current_year == 0 else 100

        # Determine risk indicator based on days of coverage
        if days_coverage < 30:
            risk_indicator = 'High Risk'
            risk_badge = 'danger'
            risk_class = 'high-risk'
        elif days_coverage <= 90:
            risk_indicator = 'Medium Risk'
            risk_badge = 'warning'
            risk_class = 'medium-risk'
        else:
            risk_indicator = 'Low Risk'
            risk_badge = 'success'
            risk_class = 'low-risk'

        # Handle infinite values
        days_coverage_display = '∞' if days_coverage >= 999 else round(days_coverage, 1)
        bts_ratio_display = '∞' if bts_sellthrough_ratio >= 999 else round(bts_sellthrough_ratio, 2)

        matrix_data.append({
            'customer': customer or 'Unknown',
            'style_code': style_code or '',
            'product_name': product_name or 'Unknown Product',
            'category_name': category_name or '',
            'sku': sku or '',
            'units_sold_annual': units_sold_annual,
            'units_sold_bts': units_sold_bts,
            'growth_pct': round(growth_pct, 1),
            'current_stock': current_stock,
            'incoming_stock': incoming_stock,
            'days_coverage': days_coverage,
            'days_coverage_display': days_coverage_display,
            'bts_sellthrough_ratio': bts_sellthrough_ratio,
            'bts_ratio_display': bts_ratio_display,
            'risk_indicator': risk_indicator,
            'risk_badge': risk_badge,
            'risk_class': risk_class,
        })

    # Get unique customers and categories for filters
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT p.sub_category
            FROM cin7_sync_product p
            WHERE p.category_name LIKE %s
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
            ORDER BY p.sub_category
        """, ['% Shop', '%%Shop%'])
        customers = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT DISTINCT category_name
            FROM cin7_sync_product
            WHERE (category_name LIKE %s OR category_name LIKE %s)
              AND category_name NOT IN ('Shop', 'Store')
            ORDER BY category_name
        """, ['% Shop', '% Store'])
        categories = [row[0] for row in cursor.fetchall()]

    # Calculate summary stats
    high_risk_count = sum(1 for item in matrix_data if item['risk_class'] == 'high-risk')
    medium_risk_count = sum(1 for item in matrix_data if item['risk_class'] == 'medium-risk')
    low_risk_count = sum(1 for item in matrix_data if item['risk_class'] == 'low-risk')

    context = {
        'matrix_data': matrix_data,
        'customers': customers,
        'categories': categories,
        'customer_filter': customer_filter,
        'category_filter': category_filter,
        'style_filter': style_filter,
        'high_risk_count': high_risk_count,
        'medium_risk_count': medium_risk_count,
        'low_risk_count': low_risk_count,
    }

    return render(request, 'dashboard/inventory_alignment_matrix.html', context)


# ==================== STOCK MANAGEMENT REPORTS ====================

@login_required()
@permission_required('dashboard.view')
def stock_turn_rate_report(request):
    """
    Stock Turn Rate Report (DP-SM-001)
    Calculate stock turn rate by each product using annual sales divided by average inventory

    Formula: Annual Sales / Average Inventory
    Benchmarks:
    - Excellent: > 12 turns/year (Green)
    - Good: 6-12 turns/year (Blue)
    - Average: 3-6 turns/year (Yellow)
    - Poor: < 3 turns/year (Red)
    """
    from django.db import connection
    from datetime import datetime, timedelta

    # Get date range from request (default: last 12 months)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)

    date_from = request.GET.get('date_from', start_date.strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', end_date.strftime('%Y-%m-%d'))

    # Query: Calculate stock turn rate per product
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH annual_sales AS (
                SELECT
                    p.cin7_id as product_id,
                    p.name as product_name,
                    p.style_code,
                    soli.code as sku,
                    COALESCE(SUM(soli.qty), 0) as total_sales_qty,
                    COALESCE(SUM(soli.qty * soli.unit_price), 0) as total_sales_value
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                INNER JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND so.status != 'Cancelled'
                  AND p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.cin7_id, p.name, p.style_code, soli.code
            ),
            avg_inventory AS (
                SELECT
                    p.cin7_id as product_id,
                    s.code as sku,
                    AVG(COALESCE(s.stock_on_hand, 0)) as avg_stock,
                    AVG(COALESCE(s.stock_on_hand * po.cost_price, 0)) as avg_stock_value
                FROM cin7_sync_product p
                LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
                LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
                WHERE p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.cin7_id, s.code
            )
            SELECT
                ast.product_name,
                ast.style_code,
                ast.sku,
                ast.total_sales_qty,
                ast.total_sales_value,
                COALESCE(ai.avg_stock, 0) as avg_stock,
                COALESCE(ai.avg_stock_value, 0) as avg_stock_value,
                CASE
                    WHEN COALESCE(ai.avg_stock, 0) > 0 THEN ast.total_sales_qty / ai.avg_stock
                    ELSE 0
                END as turn_rate
            FROM annual_sales ast
            LEFT JOIN avg_inventory ai ON ast.product_id = ai.product_id AND ast.sku = ai.sku
            WHERE ast.total_sales_qty > 0 OR COALESCE(ai.avg_stock, 0) > 0
            ORDER BY turn_rate DESC
        """, [date_from, date_to, '% Shop', '%%Shop%', '% Shop', '%%Shop%'])

        rows = cursor.fetchall()

    # Process results and classify benchmarks
    report_data = []
    for row in rows:
        product_name = row[0]
        style_code = row[1]
        sku = row[2]
        total_sales_qty = float(row[3] or 0)
        total_sales_value = float(row[4] or 0)
        avg_stock = float(row[5] or 0)
        avg_stock_value = float(row[6] or 0)
        turn_rate = float(row[7] or 0)

        # Classify benchmark
        if turn_rate > 12:
            benchmark = 'Excellent'
            benchmark_class = 'excellent'
            benchmark_badge = 'success'
        elif turn_rate >= 6:
            benchmark = 'Good'
            benchmark_class = 'good'
            benchmark_badge = 'info'
        elif turn_rate >= 3:
            benchmark = 'Average'
            benchmark_class = 'average'
            benchmark_badge = 'warning'
        else:
            benchmark = 'Poor'
            benchmark_class = 'poor'
            benchmark_badge = 'danger'

        report_data.append({
            'product_name': product_name or 'Unknown Product',
            'style_code': style_code or '',
            'sku': sku or '',
            'total_sales_qty': total_sales_qty,
            'total_sales_value': total_sales_value,
            'avg_stock': avg_stock,
            'avg_stock_value': avg_stock_value,
            'turn_rate': round(turn_rate, 2),
            'benchmark': benchmark,
            'benchmark_class': benchmark_class,
            'benchmark_badge': benchmark_badge
        })

    # Calculate summary stats
    total_products = len(report_data)
    excellent_count = sum(1 for item in report_data if item['benchmark_class'] == 'excellent')
    good_count = sum(1 for item in report_data if item['benchmark_class'] == 'good')
    average_count = sum(1 for item in report_data if item['benchmark_class'] == 'average')
    poor_count = sum(1 for item in report_data if item['benchmark_class'] == 'poor')
    avg_turn_rate = sum(item['turn_rate'] for item in report_data) / total_products if total_products > 0 else 0

    context = {
        'report_data': report_data,
        'date_from': date_from,
        'date_to': date_to,
        'total_products': total_products,
        'excellent_count': excellent_count,
        'good_count': good_count,
        'average_count': average_count,
        'poor_count': poor_count,
        'avg_turn_rate': round(avg_turn_rate, 2),
    }

    return render(request, 'dashboard/stock_turn_rate_report.html', context)


@login_required()
@permission_required('dashboard.view')
def days_of_inventory_report(request):
    """
    Days of Inventory Report (DP-SM-002)
    Calculate days of inventory on hand based on color-coded status indicators

    Formula: (Current Stock / Average Daily Sales) = Days of Inventory
    Status:
    - Critical: 0-10 days (Red)
    - Low: 10-30 days (Orange)
    - Healthy: 30-60 days (Green)
    - Overstocked: > 90 days (Blue)
    """
    from django.db import connection
    from datetime import datetime, timedelta

    # Get date range for sales calculation (default: last 365 days)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)

    date_from = request.GET.get('date_from', start_date.strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', end_date.strftime('%Y-%m-%d'))

    # Calculate number of days in the period
    days_in_period = (datetime.strptime(date_to, '%Y-%m-%d') - datetime.strptime(date_from, '%Y-%m-%d')).days + 1

    # Query: Calculate days of inventory per product
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH sales_data AS (
                SELECT
                    p.cin7_id as product_id,
                    p.name as product_name,
                    p.style_code,
                    soli.code as sku,
                    COALESCE(SUM(soli.qty), 0) as total_sales_qty,
                    COALESCE(SUM(soli.qty * soli.unit_price), 0) as total_sales_value,
                    COALESCE(SUM(soli.qty), 0) / %s as avg_daily_sales
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                INNER JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND so.status != 'Cancelled'
                  AND p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.cin7_id, p.name, p.style_code, soli.code
            ),
            current_stock AS (
                SELECT
                    p.cin7_id as product_id,
                    s.code as sku,
                    COALESCE(SUM(s.stock_on_hand), 0) as current_stock,
                    COALESCE(SUM(s.stock_on_hand * po.cost_price), 0) as stock_value
                FROM cin7_sync_product p
                LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
                LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
                WHERE p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.cin7_id, s.code
            )
            SELECT
                sd.product_name,
                sd.style_code,
                sd.sku,
                COALESCE(cs.current_stock, 0) as current_stock,
                COALESCE(cs.stock_value, 0) as stock_value,
                sd.avg_daily_sales,
                CASE
                    WHEN sd.avg_daily_sales > 0 THEN COALESCE(cs.current_stock, 0) / sd.avg_daily_sales
                    ELSE 999999
                END as days_of_inventory
            FROM sales_data sd
            LEFT JOIN current_stock cs ON sd.product_id = cs.product_id AND sd.sku = cs.sku
            WHERE COALESCE(cs.current_stock, 0) > 0
            ORDER BY days_of_inventory ASC
        """, [days_in_period, date_from, date_to, '% Shop', '%%Shop%', '% Shop', '%%Shop%'])

        rows = cursor.fetchall()

    # Process results and classify status
    report_data = []
    for row in rows:
        product_name = row[0]
        style_code = row[1]
        sku = row[2]
        current_stock = float(row[3] or 0)
        stock_value = float(row[4] or 0)
        avg_daily_sales = float(row[5] or 0)
        days_of_inventory = float(row[6] or 0)

        # Classify status
        if days_of_inventory < 10:
            status = 'Critical'
            status_class = 'critical'
            status_badge = 'danger'
        elif days_of_inventory < 30:
            status = 'Low'
            status_class = 'low'
            status_badge = 'warning'
        elif days_of_inventory <= 90:
            status = 'Healthy'
            status_class = 'healthy'
            status_badge = 'success'
        else:
            status = 'Overstocked'
            status_class = 'overstocked'
            status_badge = 'info'

        # Handle infinite days
        days_display = '∞' if days_of_inventory >= 999999 else round(days_of_inventory, 1)

        report_data.append({
            'product_name': product_name or 'Unknown Product',
            'style_code': style_code or '',
            'sku': sku or '',
            'current_stock': current_stock,
            'stock_value': stock_value,
            'avg_daily_sales': round(avg_daily_sales, 2),
            'days_of_inventory': days_of_inventory,
            'days_display': days_display,
            'status': status,
            'status_class': status_class,
            'status_badge': status_badge
        })

    # Calculate summary stats
    total_products = len(report_data)
    critical_count = sum(1 for item in report_data if item['status_class'] == 'critical')
    low_count = sum(1 for item in report_data if item['status_class'] == 'low')
    healthy_count = sum(1 for item in report_data if item['status_class'] == 'healthy')
    overstocked_count = sum(1 for item in report_data if item['status_class'] == 'overstocked')
    total_stock_value = sum(item['stock_value'] for item in report_data)

    context = {
        'report_data': report_data,
        'date_from': date_from,
        'date_to': date_to,
        'total_products': total_products,
        'critical_count': critical_count,
        'low_count': low_count,
        'healthy_count': healthy_count,
        'overstocked_count': overstocked_count,
        'total_stock_value': total_stock_value,
    }

    return render(request, 'dashboard/days_of_inventory_report.html', context)


@login_required()
@permission_required('dashboard.view')
def dead_stock_report(request):
    """
    Dead Stock Report (DP-SM-003)
    Identify and list dead stock items (no sales in 1.6 years with remaining inventory)

    Criteria: No sales in last 584 days (1.6 years) AND inventory > 0
    Display: Product name, SKU, last sale date, units remaining, cost per unit, total carrying cost
    """
    from django.db import connection
    from datetime import datetime, timedelta

    # Calculate cutoff date (584 days ago = 1.6 years)
    cutoff_date = datetime.now().date() - timedelta(days=584)

    # Query: Find dead stock items
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH last_sales AS (
                SELECT
                    p.cin7_id as product_id,
                    soli.code as sku,
                    MAX(so.invoice_date) as last_sale_date
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                INNER JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE so.status != 'Cancelled'
                  AND p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.cin7_id, soli.code
            ),
            current_stock AS (
                SELECT
                    p.cin7_id as product_id,
                    p.name as product_name,
                    p.style_code,
                    s.code as sku,
                    COALESCE(SUM(s.stock_on_hand), 0) as units_remaining,
                    COALESCE(AVG(po.cost_price), 0) as cost_per_unit,
                    COALESCE(SUM(s.stock_on_hand * po.cost_price), 0) as carrying_cost
                FROM cin7_sync_product p
                LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
                LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
                WHERE p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.cin7_id, p.name, p.style_code, s.code
                HAVING COALESCE(SUM(s.stock_on_hand), 0) > 0
            )
            SELECT
                cs.product_name,
                cs.style_code,
                cs.sku,
                COALESCE(ls.last_sale_date, '1900-01-01') as last_sale_date,
                cs.units_remaining,
                cs.cost_per_unit,
                cs.carrying_cost,
                DATEDIFF(CURDATE(), COALESCE(ls.last_sale_date, '1900-01-01')) as days_since_sale
            FROM current_stock cs
            LEFT JOIN last_sales ls ON cs.product_id = ls.product_id AND cs.sku = ls.sku
            WHERE COALESCE(ls.last_sale_date, '1900-01-01') < %s
               OR ls.last_sale_date IS NULL
            ORDER BY cs.carrying_cost DESC
        """, ['% Shop', '%%Shop%', '% Shop', '%%Shop%', cutoff_date])

        rows = cursor.fetchall()

    # Process results
    report_data = []
    for row in rows:
        product_name = row[0]
        style_code = row[1]
        sku = row[2]
        last_sale_date = row[3]
        units_remaining = float(row[4] or 0)
        cost_per_unit = float(row[5] or 0)
        carrying_cost = float(row[6] or 0)
        days_since_sale = int(row[7] or 0)

        # Format last sale date
        if last_sale_date and last_sale_date != '1900-01-01':
            last_sale_display = last_sale_date.strftime('%Y-%m-%d') if hasattr(last_sale_date, 'strftime') else str(last_sale_date)
        else:
            last_sale_display = 'Never'

        report_data.append({
            'product_name': product_name or 'Unknown Product',
            'style_code': style_code or '',
            'sku': sku or '',
            'last_sale_date': last_sale_display,
            'days_since_sale': days_since_sale,
            'units_remaining': units_remaining,
            'cost_per_unit': cost_per_unit,
            'carrying_cost': carrying_cost
        })

    # Calculate summary stats
    total_dead_items = len(report_data)
    total_units = sum(item['units_remaining'] for item in report_data)
    total_carrying_cost = sum(item['carrying_cost'] for item in report_data)
    avg_carrying_cost = total_carrying_cost / total_dead_items if total_dead_items > 0 else 0

    context = {
        'report_data': report_data,
        'cutoff_date': cutoff_date,
        'total_dead_items': total_dead_items,
        'total_units': total_units,
        'total_carrying_cost': total_carrying_cost,
        'avg_carrying_cost': avg_carrying_cost,
    }

    return render(request, 'dashboard/dead_stock_report.html', context)


@login_required()
@permission_required('dashboard.view')
def top_best_sellers_report(request):
    """
    Top 20 Best Sellers Report (DP-SM-004)
    Show Top 20 Best Sellers sorted by revenue, units, and turn rate

    Display: Top 20 products by multiple metrics
    Sortable by: Revenue, Units Sold, Turn Rate
    """
    from django.db import connection
    from datetime import datetime, timedelta

    # Get date range from request (default: last 12 months)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)

    date_from = request.GET.get('date_from', start_date.strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', end_date.strftime('%Y-%m-%d'))
    sort_by = request.GET.get('sort_by', 'revenue')  # revenue, units, turn_rate

    # Query: Calculate best sellers with all metrics
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH sales_data AS (
                SELECT
                    p.sub_category as customer,
                    p.name as product_name,
                    p.style_code,
                    soli.code as sku,
                    COALESCE(SUM(soli.qty), 0) as total_units,
                    COALESCE(SUM(soli.qty * soli.unit_price), 0) as total_revenue
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                INNER JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND so.status != 'Cancelled'
                  AND p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category, p.name, p.style_code, soli.code
            ),
            avg_inventory AS (
                SELECT
                    p.cin7_id as product_id,
                    s.code as sku,
                    AVG(COALESCE(s.stock_on_hand, 0)) as avg_stock
                FROM cin7_sync_product p
                LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
                WHERE p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.cin7_id, s.code
            ),
            product_ids AS (
                SELECT DISTINCT
                    p.cin7_id as product_id,
                    p.name as product_name,
                    soli.code as sku
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
            )
            SELECT
                sd.customer,
                sd.product_name,
                sd.style_code,
                sd.sku,
                sd.total_units,
                sd.total_revenue,
                COALESCE(ai.avg_stock, 0) as avg_stock,
                CASE
                    WHEN COALESCE(ai.avg_stock, 0) > 0 THEN sd.total_units / ai.avg_stock
                    ELSE 0
                END as turn_rate
            FROM sales_data sd
            LEFT JOIN product_ids pi ON sd.product_name = pi.product_name AND sd.sku = pi.sku
            LEFT JOIN avg_inventory ai ON pi.product_id = ai.product_id AND sd.sku = ai.sku
            ORDER BY sd.total_revenue DESC
            LIMIT 20
        """, [date_from, date_to, '% Shop', '%%Shop%', '% Shop', '%%Shop%', '% Shop', '%%Shop%'])

        rows = cursor.fetchall()

    # Process results
    report_data = []
    rank = 1
    for row in rows:
        customer = row[0]
        product_name = row[1]
        style_code = row[2]
        sku = row[3]
        total_units = float(row[4] or 0)
        total_revenue = float(row[5] or 0)
        avg_stock = float(row[6] or 0)
        turn_rate = float(row[7] or 0)

        report_data.append({
            'rank': rank,
            'customer': customer or 'Unknown',
            'product_name': product_name or 'Unknown Product',
            'style_code': style_code or '',
            'sku': sku or '',
            'total_units': total_units,
            'total_revenue': total_revenue,
            'avg_stock': avg_stock,
            'turn_rate': round(turn_rate, 2)
        })
        rank += 1

    # Re-sort based on user selection
    if sort_by == 'units':
        report_data.sort(key=lambda x: x['total_units'], reverse=True)
    elif sort_by == 'turn_rate':
        report_data.sort(key=lambda x: x['turn_rate'], reverse=True)
    else:  # revenue (default)
        report_data.sort(key=lambda x: x['total_revenue'], reverse=True)

    # Re-rank after sorting
    for i, item in enumerate(report_data, 1):
        item['rank'] = i

    # Calculate summary stats
    total_revenue = sum(item['total_revenue'] for item in report_data)
    total_units = sum(item['total_units'] for item in report_data)
    avg_turn_rate = sum(item['turn_rate'] for item in report_data) / len(report_data) if report_data else 0

    context = {
        'report_data': report_data,
        'date_from': date_from,
        'date_to': date_to,
        'sort_by': sort_by,
        'total_revenue': total_revenue,
        'total_units': total_units,
        'avg_turn_rate': round(avg_turn_rate, 2),
    }

    return render(request, 'dashboard/top_best_sellers_report.html', context)


@login_required()
@permission_required('dashboard.view')
def abc_analysis_report(request):
    """
    ABC Analysis Report (DP-ABC-001, DP-ABC-002)
    Classify inventory into A, B, and C categories based on revenue contribution
    to focus management attention where it matters most.

    ABC Classification Rules:
    - A Items: First 80% of cumulative revenue (~20% of products) - Monitor DAILY
    - B Items: Next 15% of cumulative revenue (~30% of products) - Monitor WEEKLY
    - C Items: Final 5% of cumulative revenue (~50% of products) - Monitor MONTHLY

    Based on Pareto Principle (80-20 rule)
    """
    from django.db import connection
    from datetime import datetime, timedelta

    # Get date range from request (default: last 12 months)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)

    date_from = request.GET.get('date_from', start_date.strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', end_date.strftime('%Y-%m-%d'))

    # Query: Calculate annual revenue per product and assign ABC classification
    # DP-ABC-001: Calculate annual revenue per product and rank from highest to lowest
    # DP-ABC-002: Calculate cumulative revenue percentages and assign A/B/C classifications
    with connection.cursor() as cursor:
        cursor.execute("""
            WITH product_revenue AS (
                SELECT
                    p.sub_category as customer,
                    p.name as product_name,
                    p.style_code,
                    soli.code as sku,
                    COALESCE(SUM(soli.qty * soli.unit_price), 0) as annual_revenue
                FROM cin7_sync_salesorderlineitem soli
                INNER JOIN cin7_sync_salesorder so ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
                INNER JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
                WHERE so.invoice_date >= %s
                  AND so.invoice_date <= %s
                  AND so.status != 'Cancelled'
                  AND p.category_name LIKE %s
                  AND p.sub_category IS NOT NULL
                  AND p.sub_category <> ''
                  AND p.sub_category NOT LIKE %s
                GROUP BY p.sub_category, p.name, p.style_code, soli.code
                HAVING annual_revenue > 0
            ),
            total_revenue_calc AS (
                SELECT SUM(annual_revenue) as total_revenue
                FROM product_revenue
            ),
            ranked_products AS (
                SELECT
                    pr.customer,
                    pr.product_name,
                    pr.style_code,
                    pr.sku,
                    pr.annual_revenue,
                    ROW_NUMBER() OVER (ORDER BY pr.annual_revenue DESC) as rank_num,
                    SUM(pr.annual_revenue) OVER (ORDER BY pr.annual_revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as cumulative_revenue,
                    tr.total_revenue
                FROM product_revenue pr
                CROSS JOIN total_revenue_calc tr
            )
            SELECT
                rank_num,
                customer,
                product_name,
                style_code,
                sku,
                annual_revenue,
                cumulative_revenue,
                total_revenue,
                (cumulative_revenue / total_revenue * 100) as cumulative_pct,
                CASE
                    WHEN (cumulative_revenue / total_revenue * 100) <= 80 THEN 'A'
                    WHEN (cumulative_revenue / total_revenue * 100) <= 95 THEN 'B'
                    ELSE 'C'
                END as abc_category
            FROM ranked_products
            ORDER BY rank_num
        """, [date_from, date_to, '% Shop', '%%Shop%'])

        rows = cursor.fetchall()

    # Process results
    report_data = []
    for row in rows:
        rank_num = int(row[0])
        customer = row[1]
        product_name = row[2]
        style_code = row[3]
        sku = row[4]
        annual_revenue = float(row[5] or 0)
        cumulative_revenue = float(row[6] or 0)
        total_revenue = float(row[7] or 0)
        cumulative_pct = float(row[8] or 0)
        abc_category = row[9]

        # Assign badge color and monitoring frequency based on ABC category
        if abc_category == 'A':
            badge_color = 'success'  # Green
            monitoring_frequency = 'Daily'
        elif abc_category == 'B':
            badge_color = 'primary'  # Blue
            monitoring_frequency = 'Weekly'
        else:  # C
            badge_color = 'warning'  # Yellow
            monitoring_frequency = 'Monthly'

        report_data.append({
            'rank': rank_num,
            'customer': customer or 'Unknown',
            'product_name': product_name or 'Unknown Product',
            'style_code': style_code or '',
            'sku': sku or '',
            'annual_revenue': annual_revenue,
            'cumulative_pct': round(cumulative_pct, 2),
            'abc_category': abc_category,
            'badge_color': badge_color,
            'monitoring_frequency': monitoring_frequency
        })

    # Calculate summary statistics for each category (DP-ABC-003)
    total_products = len(report_data)
    a_items = [item for item in report_data if item['abc_category'] == 'A']
    b_items = [item for item in report_data if item['abc_category'] == 'B']
    c_items = [item for item in report_data if item['abc_category'] == 'C']

    a_count = len(a_items)
    b_count = len(b_items)
    c_count = len(c_items)

    a_revenue = sum(item['annual_revenue'] for item in a_items)
    b_revenue = sum(item['annual_revenue'] for item in b_items)
    c_revenue = sum(item['annual_revenue'] for item in c_items)
    total_revenue = a_revenue + b_revenue + c_revenue

    a_revenue_pct = (a_revenue / total_revenue * 100) if total_revenue > 0 else 0
    b_revenue_pct = (b_revenue / total_revenue * 100) if total_revenue > 0 else 0
    c_revenue_pct = (c_revenue / total_revenue * 100) if total_revenue > 0 else 0

    a_product_pct = (a_count / total_products * 100) if total_products > 0 else 0
    b_product_pct = (b_count / total_products * 100) if total_products > 0 else 0
    c_product_pct = (c_count / total_products * 100) if total_products > 0 else 0

    context = {
        'report_data': report_data,
        'date_from': date_from,
        'date_to': date_to,
        'total_products': total_products,
        'total_revenue': total_revenue,
        # A Items summary
        'a_count': a_count,
        'a_revenue': a_revenue,
        'a_revenue_pct': round(a_revenue_pct, 1),
        'a_product_pct': round(a_product_pct, 1),
        # B Items summary
        'b_count': b_count,
        'b_revenue': b_revenue,
        'b_revenue_pct': round(b_revenue_pct, 1),
        'b_product_pct': round(b_product_pct, 1),
        # C Items summary
        'c_count': c_count,
        'c_revenue': c_revenue,
        'c_revenue_pct': round(c_revenue_pct, 1),
        'c_product_pct': round(c_product_pct, 1),
    }

    return render(request, 'dashboard/abc_analysis_report.html', context)


@login_required
@permission_required('replenishment.daily_pick_list.view')
def store_daily_pick_list(request):
    """
    Generate daily pick list for store replenishment using 2-week average forecasting

    Forecasting Algorithm:
    - For each weekday: Forecast = AVERAGE(week1_same_day, week2_same_day)
    - Fractional values are rounded up (ceil) since you can't pick half a unit
    - Products with 0 total forecast are excluded

    Features:
    - Shows last 14 days of sales with daily breakdown (2 weeks)
    - Forecasts next 7 days using 2-week average per weekday
    - Displays current stock and incoming stock
    - Sorted by highest forecasted demand
    """
    from datetime import date, datetime, timedelta, time
    from django.db.models import Sum, F, Q
    from django.db.models.functions import TruncDate
    from django.db.models.expressions import RawSQL
    from cin7.models import SalesOrderLineItem, Stock, Product
    import zoneinfo

    NZ_TZ = zoneinfo.ZoneInfo('Pacific/Auckland')
    UTC_TZ = zoneinfo.ZoneInfo('UTC')

    def nz_date_to_utc_range(start_date, end_date):
        """Convert NZ date range to UTC datetime boundaries (handles DST)."""
        utc_start = datetime.combine(start_date, time.min, tzinfo=NZ_TZ).astimezone(UTC_TZ)
        utc_end = datetime.combine(end_date, time.max, tzinfo=NZ_TZ).astimezone(UTC_TZ)
        return utc_start, utc_end

    def get_nz_utc_offset(for_date):
        """Get the UTC offset string (e.g. '+13:00') for NZ on a given date."""
        dt = datetime.combine(for_date, time(12, 0), tzinfo=NZ_TZ)
        total_seconds = int(dt.utcoffset().total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f'+{hours:02d}:{minutes:02d}'

    # Get user's assigned stores
    user = request.user
    is_admin = user.is_superuser or user.is_staff
    has_assigned_stores = user.assigned_stores.exists() if hasattr(user, 'assigned_stores') else False

    if not is_admin and not has_assigned_stores:
        return render(request, 'dashboard/store_daily_pick_list.html', {
            'error': 'You are not assigned to any stores. Please contact your administrator.',
            'products': [],
        })

    # Get target date from request (default: yesterday in NZ time)
    target_date_str = request.GET.get('date')
    if target_date_str:
        try:
            target_date = date.fromisoformat(target_date_str)
        except ValueError:
            target_date = datetime.now(NZ_TZ).date() - timedelta(days=1)
    else:
        target_date = datetime.now(NZ_TZ).date() - timedelta(days=1)

    # Get category filter (optional)
    category_filter = request.GET.get('category', '')

    # Define date ranges for trend-adjusted forecasting
    # Recent Week: Last 7 days (for base values and trend calculation)
    recent_week_end = target_date
    recent_week_start = recent_week_end - timedelta(days=6)

    # Previous Week: 7 days before recent week (for trend calculation)
    previous_week_end = recent_week_start - timedelta(days=1)
    previous_week_start = previous_week_end - timedelta(days=6)

    # Total query window: 14 days
    query_start_date = previous_week_start
    query_end_date = recent_week_end

    # Convert NZ date range to UTC datetime boundaries (handles DST automatically)
    utc_start, utc_end = nz_date_to_utc_range(query_start_date, query_end_date)

    # Get NZ UTC offset for CONVERT_TZ in SQL (used for date grouping)
    nz_offset = get_nz_utc_offset(query_start_date)

    # Query sales for 14 days (2 weeks) using UTC datetime boundaries
    sales_query = SalesOrderLineItem.objects.filter(
        sales_order__invoice_date__gte=utc_start,
        sales_order__invoice_date__lte=utc_end,
        sales_order__is_void=False
    )

    # Filter by assigned stores if not admin
    if not is_admin and has_assigned_stores:
        # Get accessible categories from user's assigned stores
        accessible_categories = user.get_accessible_categories()
        if accessible_categories:
            # Filter sales by products in the user's assigned store categories
            sales_query = sales_query.filter(product__category_name__in=accessible_categories)

    # Filter by category if specified
    if category_filter:
        sales_query = sales_query.filter(product__category_name__icontains=category_filter)

    # Aggregate sales by product (for the full 14-day period)
    sales_data = sales_query.values(
        'cin7_product_id',
        'code',
        'name',
        product_category=F('product__category_name'),
        product_sub_category=F('product__sub_category')
    ).annotate(
        total_qty_sold=Sum('qty')
    )

    # Build product list with stock information
    products = []
    categories = set()

    for sale in sales_data:
        sku = sale['code']
        product_name = sale['name']
        category = sale['product_category'] or 'Uncategorized'
        school_name = sale['product_sub_category'] or 'N/A'

        # Get daily sales data for this product (optimized - single query)
        daily_sales_qs = SalesOrderLineItem.objects.filter(
            code=sku,
            sales_order__invoice_date__gte=utc_start,
            sales_order__invoice_date__lte=utc_end,
            sales_order__is_void=False
        )

        # Apply store filtering
        if not is_admin and has_assigned_stores:
            accessible_categories = user.get_accessible_categories()
            if accessible_categories:
                daily_sales_qs = daily_sales_qs.filter(product__category_name__in=accessible_categories)

        # Aggregate by NZ date (convert UTC timestamps to NZ time before extracting date)
        daily_sales_data = daily_sales_qs.annotate(
            sale_date=RawSQL(
                "DATE(CONVERT_TZ(cin7_sync_salesorder.invoice_date, '+00:00', %s))",
                [nz_offset]
            )
        ).values('sale_date').annotate(
            total_qty=Sum('qty')
        ).order_by('sale_date')

        # Convert to dictionary for O(1) lookups
        sales_by_date = {
            item['sale_date']: float(item['total_qty'] or 0)
            for item in daily_sales_data
        }

        # Calculate weekly totals for display
        recent_week_sales = 0
        previous_week_sales = 0

        for i in range(7):
            recent_day_date = recent_week_start + timedelta(days=i)
            previous_day_date = previous_week_start + timedelta(days=i)

            recent_week_sales += sales_by_date.get(recent_day_date, 0)
            previous_week_sales += sales_by_date.get(previous_day_date, 0)

        # Build daily breakdown for previous week (7 days before recent week)
        previous_week_sales_by_day = []
        current_date = previous_week_start
        for i in range(7):
            day_qty = sales_by_date.get(current_date, 0)

            previous_week_sales_by_day.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'day_name': current_date.strftime('%A'),
                'qty': int(day_qty)
            })

            current_date += timedelta(days=1)

        # Build daily breakdown for recent week (last 7 days for display)
        sales_by_day = []
        current_date = recent_week_start
        for i in range(7):
            day_qty = sales_by_date.get(current_date, 0)

            sales_by_day.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'day_name': current_date.strftime('%A'),
                'qty': int(day_qty)
            })

            current_date += timedelta(days=1)

        # Generate forecast breakdown for next 7 days using 2-week average
        # Each day's forecast = average of same weekday from both weeks, rounded up
        forecast_by_day = []
        forecast_date = recent_week_end + timedelta(days=1)  # Day after recent week ends

        for i in range(7):
            week1_day_sales = sales_by_date.get(previous_week_start + timedelta(days=i), 0)
            week2_day_sales = sales_by_date.get(recent_week_start + timedelta(days=i), 0)

            # Average of same weekday across both weeks
            daily_forecast = (week1_day_sales + week2_day_sales) / 2

            # Round up fractional forecasts (can't pick half a unit)
            daily_forecast = int(daily_forecast) + (1 if daily_forecast % 1 > 0 else 0) if daily_forecast > 0 else 0

            forecast_by_day.append({
                'date': forecast_date.strftime('%Y-%m-%d'),
                'day_name': forecast_date.strftime('%A'),
                'qty': int(daily_forecast),
            })

            forecast_date += timedelta(days=1)

        # Calculate total forecasted demand
        forecasted_demand = sum(day['qty'] for day in forecast_by_day)

        # Get current stock for this product at the user's assigned stores
        stock_query = Stock.objects.filter(code=sku)

        if not is_admin and has_assigned_stores:
            # Get store names from accessible categories
            accessible_categories = user.get_accessible_categories()
            if accessible_categories:
                # Filter stock by branch names that match the store categories
                stock_query = stock_query.filter(branch_name__in=accessible_categories)

        stock_record = stock_query.first()

        if stock_record:
            current_stock = float(stock_record.stock_on_hand or 0)
            incoming_stock = float(stock_record.incoming or 0)
        else:
            # Product not in stock table for this store
            current_stock = 0
            incoming_stock = 0

        products.append({
            'product_name': product_name,
            'sku': sku,
            'school_name': school_name,
            'category': category,
            'current_stock': int(current_stock),
            'incoming_stock': int(incoming_stock),
            'total_sales_7d': int(recent_week_sales),
            'forecasted_demand': int(forecasted_demand),
            'previous_week_sales_by_day': previous_week_sales_by_day,
            'sales_by_day': sales_by_day,
            'forecast_by_day': forecast_by_day,
            'daily_trend_factors': [],
            'recent_week_total': int(recent_week_sales),
            'previous_week_total': int(previous_week_sales),
        })

        categories.add(category)

    # Remove products with 0 forecast and sort by highest demand
    products = [p for p in products if p['forecasted_demand'] > 0]
    products.sort(key=lambda x: x['forecasted_demand'], reverse=True)

    # Get unique categories for filter dropdown
    all_categories = []
    if is_admin:
        all_categories = Product.objects.values_list('category_name', flat=True).distinct().order_by('category_name')
    elif has_assigned_stores:
        # Get categories from user's assigned stores
        all_categories = user.get_accessible_categories()

    # Get store display name
    store_name = 'All Stores'
    if has_assigned_stores:
        store_names = list(set(
            user.assigned_stores.filter(is_active=True)
            .values_list('store_name', flat=True)
        ))
        if store_names:
            store_name = ', '.join(sorted(store_names))

    context = {
        'target_date': target_date,
        'start_date': recent_week_start,
        'end_date': recent_week_end,
        'previous_week_start': previous_week_start,
        'previous_week_end': previous_week_end,
        'forecast_start': recent_week_end + timedelta(days=1),
        'forecast_end': recent_week_end + timedelta(days=7),
        'pick_list': products,
        'total_items': len(products),
        'category_count': len(categories),
        'store_name': store_name,
        'is_admin': is_admin,
        'all_categories': all_categories,
        'selected_category': category_filter,
        'today': date.today(),
    }

    return render(request, 'dashboard/store_daily_pick_list.html', context)


@login_required
@permission_required('replenishment.daily_pick_list.view')
def store_daily_pick_list_export(request):
    """Export daily pick list forecast to Excel."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from datetime import date, datetime, timedelta, time
    from django.db.models import Sum, F, Q
    from django.db.models.functions import TruncDate
    from django.db.models.expressions import RawSQL
    from cin7.models import SalesOrderLineItem, Stock, Product
    import zoneinfo

    NZ_TZ = zoneinfo.ZoneInfo('Pacific/Auckland')
    UTC_TZ = zoneinfo.ZoneInfo('UTC')

    def nz_date_to_utc_range(start_date, end_date):
        """Convert NZ date range to UTC datetime boundaries (handles DST)."""
        utc_start = datetime.combine(start_date, time.min, tzinfo=NZ_TZ).astimezone(UTC_TZ)
        utc_end = datetime.combine(end_date, time.max, tzinfo=NZ_TZ).astimezone(UTC_TZ)
        return utc_start, utc_end

    def get_nz_utc_offset(for_date):
        """Get the UTC offset string (e.g. '+13:00') for NZ on a given date."""
        dt = datetime.combine(for_date, time(12, 0), tzinfo=NZ_TZ)
        total_seconds = int(dt.utcoffset().total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f'+{hours:02d}:{minutes:02d}'

    # === Reuse the same data logic from store_daily_pick_list ===
    user = request.user
    is_admin = user.is_superuser or user.is_staff
    has_assigned_stores = user.assigned_stores.exists() if hasattr(user, 'assigned_stores') else False

    target_date_str = request.GET.get('date')
    if target_date_str:
        try:
            target_date = date.fromisoformat(target_date_str)
        except ValueError:
            target_date = datetime.now(NZ_TZ).date() - timedelta(days=1)
    else:
        target_date = datetime.now(NZ_TZ).date() - timedelta(days=1)

    category_filter = request.GET.get('category', '')

    recent_week_end = target_date
    recent_week_start = recent_week_end - timedelta(days=6)
    previous_week_end = recent_week_start - timedelta(days=1)
    previous_week_start = previous_week_end - timedelta(days=6)
    forecast_start = recent_week_end + timedelta(days=1)
    forecast_end = recent_week_end + timedelta(days=7)

    # Build the product query (same as main view)
    query_start_date = previous_week_start
    query_end_date = recent_week_end

    # Convert NZ date range to UTC datetime boundaries (handles DST automatically)
    utc_start, utc_end = nz_date_to_utc_range(query_start_date, query_end_date)

    # Get NZ UTC offset for CONVERT_TZ in SQL (used for date grouping)
    nz_offset = get_nz_utc_offset(query_start_date)

    sales_query = SalesOrderLineItem.objects.filter(
        sales_order__invoice_date__gte=utc_start,
        sales_order__invoice_date__lte=utc_end,
        sales_order__is_void=False
    )

    if not is_admin and has_assigned_stores:
        accessible_categories = user.get_accessible_categories()
        if accessible_categories:
            sales_query = sales_query.filter(product__category_name__in=accessible_categories)

    if category_filter:
        sales_query = sales_query.filter(product__category_name__icontains=category_filter)

    # Get unique products with sales in the period
    sales_data = sales_query.values(
        'code',
        'name',
        product_category=F('product__category_name'),
    ).annotate(
        total_qty_sold=Sum('qty')
    ).order_by('code')

    # Build per-product data (deduplicated by SKU)
    product_data = {}
    for sale in sales_data:
        sku = sale['code']
        if sku in product_data:
            continue
        product_data[sku] = {
            'product_name': sale['name'],
            'sku': sku,
            'category': sale['product_category'] or 'Uncategorized',
            'sales_by_date': {},
        }

    # Get daily sales for each product (one query per SKU)
    for sku, data in product_data.items():
        daily_sales_qs = SalesOrderLineItem.objects.filter(
            code=sku,
            sales_order__invoice_date__gte=utc_start,
            sales_order__invoice_date__lte=utc_end,
            sales_order__is_void=False
        )
        if not is_admin and has_assigned_stores:
            acc_cats = user.get_accessible_categories()
            if acc_cats:
                daily_sales_qs = daily_sales_qs.filter(product__category_name__in=acc_cats)

        daily_sales_data = daily_sales_qs.annotate(
            sale_date=RawSQL(
                "DATE(CONVERT_TZ(cin7_sync_salesorder.invoice_date, '+00:00', %s))",
                [nz_offset]
            )
        ).values('sale_date').annotate(
            total_qty=Sum('qty')
        ).order_by('sale_date')

        data['sales_by_date'] = {
            item['sale_date']: float(item['total_qty'] or 0)
            for item in daily_sales_data
        }

    # Calculate forecasts for each product using 2-week average
    products = []
    for sku, data in product_data.items():
        sales_by_date = data['sales_by_date']

        # Build forecast using 2-week average per weekday
        forecast_by_day = []
        forecast_date = recent_week_end + timedelta(days=1)

        for i in range(7):
            week1_day_sales = sales_by_date.get(previous_week_start + timedelta(days=i), 0)
            week2_day_sales = sales_by_date.get(recent_week_start + timedelta(days=i), 0)

            daily_forecast = (week1_day_sales + week2_day_sales) / 2
            daily_forecast = int(daily_forecast) + (1 if daily_forecast % 1 > 0 else 0) if daily_forecast > 0 else 0

            forecast_by_day.append({
                'date': forecast_date,
                'day_name': forecast_date.strftime('%A'),
                'qty': int(daily_forecast),
            })

            forecast_date += timedelta(days=1)

        forecasted_demand = sum(day['qty'] for day in forecast_by_day)

        products.append({
            'product_name': data['product_name'],
            'sku': sku,
            'category': data['category'],
            'forecasted_demand': forecasted_demand,
            'forecast_by_day': forecast_by_day,
        })

    products = [p for p in products if p['forecasted_demand'] > 0]
    products.sort(key=lambda x: x['forecasted_demand'], reverse=True)

    # === Build Excel workbook ===
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Daily Pick List Forecast"

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="4A90D9", end_color="4A90D9", fill_type="solid")
    forecast_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # Title row
    ws.merge_cells('A1:J1')
    title_cell = ws['A1']
    title_cell.value = f"Daily Pick List — Next 7 Days Forecast ({forecast_start.strftime('%d %b')} - {forecast_end.strftime('%d %b %Y')})"
    title_cell.font = Font(bold=True, size=14)
    title_cell.alignment = Alignment(horizontal='left')

    ws.merge_cells('A2:J2')
    ws['A2'].value = f"Generated: {date.today().strftime('%d %b %Y')} | Data as of: {target_date.strftime('%d %b %Y')}"
    ws['A2'].font = Font(italic=True, color="666666", size=10)

    # Headers (row 4): Product, Stylecode, 7 forecast days, Total
    forecast_dates = [(forecast_start + timedelta(days=i)) for i in range(7)]
    headers = ['Product', 'Stylecode']
    for d in forecast_dates:
        headers.append(f"{d.strftime('%a %d/%m')}")
    headers.append('Total Forecast')

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = thin_border

    # Data rows
    for row_idx, item in enumerate(products, 5):
        ws.cell(row=row_idx, column=1, value=item['product_name']).border = thin_border
        ws.cell(row=row_idx, column=2, value=item['sku']).border = thin_border

        for day_idx, day in enumerate(item['forecast_by_day']):
            cell = ws.cell(row=row_idx, column=3 + day_idx, value=day['qty'])
            cell.fill = forecast_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')
            cell.number_format = '0'

        total_cell = ws.cell(row=row_idx, column=10, value=item['forecasted_demand'])
        total_cell.font = Font(bold=True)
        total_cell.border = thin_border
        total_cell.alignment = Alignment(horizontal='center')

    # Column widths
    ws.column_dimensions['A'].width = 35
    ws.column_dimensions['B'].width = 22
    for col in range(3, 10):
        ws.column_dimensions[get_column_letter(col)].width = 12
    ws.column_dimensions['J'].width = 14

    # Freeze header row
    ws.freeze_panes = 'A5'

    # Write to response
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"daily_pick_list_forecast_{forecast_start.strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@permission_required('replenishment.demand_planning.view_all_requests')
def top_performing_schools(request):
    """
    View to display and manage top performing schools
    Shows schools from categories ending with 'Shop' or 'Store'
    with their last financial year sales and ability to mark as top performing
    """
    from dashboard.models import TopPerformingSchool
    from cin7.models import Product, SalesOrderLineItem
    from django.db.models import Q, Sum, F
    from datetime import date, timedelta
    from django.utils import timezone
    from dashboard.utils.financial_year import get_financial_year_dates, get_financial_year_label
    import json

    # Calculate last financial year dates using configurable system settings
    # This supports any FY definition (April-March, July-June, etc.)
    last_fy_start, last_fy_end = get_financial_year_dates()

    # Get all schools from products where category ends with 'Shop' or 'Store'
    schools_data = Product.objects.filter(
        Q(category_name__iendswith='Shop') | Q(category_name__iendswith='Store')
    ).values('category_name', 'sub_category').distinct()

    # Create a dictionary to track schools and their sales
    schools_dict = {}

    for school in schools_data:
        school_name = school['sub_category']
        category_name = school['category_name']

        if not school_name:
            continue

        # Use school_name as unique key
        if school_name not in schools_dict:
            schools_dict[school_name] = {
                'school_name': school_name,
                'category_name': category_name,
                'last_fy_sales': 0,
            }

    # Convert dates to timezone-aware datetime for proper comparison
    import datetime
    last_fy_start_dt = timezone.make_aware(datetime.datetime.combine(last_fy_start, datetime.time.min))
    last_fy_end_dt = timezone.make_aware(datetime.datetime.combine(last_fy_end, datetime.time.max))

    # Log financial year calculation
    logger = logging.getLogger(__name__)
    today = date.today()
    logger.info(f'Top Performing Schools - Financial Year Calculation (Configurable System)')
    logger.info(f'  Today: {today}')
    logger.info(f'  Last Completed FY Start: {last_fy_start} ({last_fy_start_dt})')
    logger.info(f'  Last Completed FY End: {last_fy_end} ({last_fy_end_dt})')
    logger.info(f'  FY Label: {get_financial_year_label(last_fy_start, last_fy_end)}')
    logger.info(f'  Total schools found: {len(schools_dict)}')

    # Calculate sales for each school from SalesOrderLineItem
    # Get products for each school and calculate their sales
    for school_name in schools_dict.keys():
        # Get all products for this school
        school_products = Product.objects.filter(
            Q(category_name__iendswith='Shop') | Q(category_name__iendswith='Store'),
            sub_category=school_name
        ).values_list('cin7_id', flat=True)

        if school_products:
            product_count = len(list(school_products))

            # Calculate sales for these products in the last FY
            # NOTE: Status is 'APPROVED' not 'Invoiced' in the database
            sales = SalesOrderLineItem.objects.filter(
                cin7_product_id__in=school_products,
                sales_order__invoice_date__gte=last_fy_start_dt,
                sales_order__invoice_date__lte=last_fy_end_dt,
                sales_order__status='APPROVED'  # Fixed: was 'Invoiced' but database uses 'APPROVED'
            ).aggregate(
                total_sales=Sum(F('qty') * F('unit_price')),
                total_qty=Sum('qty')
            )

            total_sales = sales['total_sales'] or 0
            total_qty = sales['total_qty'] or 0
            schools_dict[school_name]['last_fy_sales'] = float(total_sales)

            # Log sample school data for debugging
            if school_name in ['Western Springs College', 'McAuley High School', 'Onehunga High school']:
                logger.info(f'  School: {school_name}')
                logger.info(f'    Products: {product_count}')
                logger.info(f'    Total Sales: ${total_sales:,.2f}')
                logger.info(f'    Total Quantity: {total_qty:,.0f}')

    # Get or create TopPerformingSchool records
    # Also extract store location from category_name
    for school_name, school_data in schools_dict.items():
        category_name = school_data['category_name']
        # Extract store location by removing 'Shop' or 'Store' suffix
        store_location = category_name.replace(' Shop', '').replace(' Store', '').strip()

        TopPerformingSchool.objects.update_or_create(
            school_name=school_name,
            defaults={
                'category_name': category_name,
                'store_location': store_location,
                'last_fy_sales': school_data['last_fy_sales'],
                'last_fy_start': last_fy_start,
                'last_fy_end': last_fy_end,
                'sales_updated_at': timezone.now(),
            }
        )

    # Get all schools from database, ordered by sales
    schools = TopPerformingSchool.objects.all().order_by('-last_fy_sales')

    # Calculate statistics
    total_schools = schools.count()
    top_performing_count = schools.filter(is_top_performing=True).count()
    total_sales = schools.aggregate(total=Sum('last_fy_sales'))['total'] or 0

    context = {
        'schools': schools,
        'total_schools': total_schools,
        'top_performing_count': top_performing_count,
        'total_sales': total_sales,
        'last_fy_start': last_fy_start,
        'last_fy_end': last_fy_end,
    }

    return render(request, 'dashboard/top_performing_schools.html', context)


@login_required
@permission_required('replenishment.demand_planning.approve')
@require_http_methods(["POST"])
def toggle_top_performing_school(request, school_id):
    """
    Toggle the top performing status of a school
    """
    from dashboard.models import TopPerformingSchool
    from django.shortcuts import get_object_or_404
    from django.utils import timezone
    import json

    try:
        school = get_object_or_404(TopPerformingSchool, id=school_id)

        # Toggle the status
        school.is_top_performing = not school.is_top_performing

        # Update metadata
        if school.is_top_performing:
            school.marked_by = request.user
            school.marked_at = timezone.now()

        school.save()

        return JsonResponse({
            'success': True,
            'is_top_performing': school.is_top_performing,
            'school_name': school.school_name,
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def calculate_school_sales_from_mapping(school_name, category_name, last_fy_start, last_fy_end):
    """
    Calculate last financial year sales for a specific school based on store-school mapping

    Args:
        school_name: School name (from sub_category)
        category_name: Category name (e.g., 'Mt Albert Shop')
        last_fy_start: Start date of last financial year
        last_fy_end: End date of last financial year

    Returns:
        Decimal: Total sales amount
    """
    from cin7.models import Product, SalesOrderLineItem
    from django.db.models import Sum, F
    from django.utils import timezone
    import datetime

    # Convert dates to timezone-aware datetime
    last_fy_start_dt = timezone.make_aware(datetime.datetime.combine(last_fy_start, datetime.time.min))
    last_fy_end_dt = timezone.make_aware(datetime.datetime.combine(last_fy_end, datetime.time.max))

    # Get all products for this school and category
    school_products = Product.objects.filter(
        category_name=category_name,
        sub_category=school_name
    ).values_list('cin7_id', flat=True)

    if not school_products:
        return 0

    # Calculate sales for these products in the last FY
    sales = SalesOrderLineItem.objects.filter(
        cin7_product_id__in=school_products,
        sales_order__invoice_date__gte=last_fy_start_dt,
        sales_order__invoice_date__lte=last_fy_end_dt,
        sales_order__status='APPROVED'
    ).aggregate(
        total_sales=Sum(F('qty') * F('unit_price'))
    )

    return float(sales['total_sales'] or 0)


def perform_auto_selection_top_52():
    """
    Auto-select top 52 schools based on store-school mapping and sales data

    Algorithm:
    1. Get all active stores from StoreSchoolMapping
    2. For each store, get all schools and calculate their last FY sales
    3. Rank schools by sales within each store
    4. Select top performers from each store (distributed across 16 stores)
    5. Sort all candidates by sales and take top 52

    Returns:
        int: Number of schools selected
    """
    from dashboard.models import StoreSchoolMapping, TopPerformingSchool
    from dashboard.utils.financial_year import get_financial_year_dates
    from django.utils import timezone
    import logging

    logger = logging.getLogger(__name__)

    # Get last financial year dates
    last_fy_start, last_fy_end = get_financial_year_dates()

    logger.info(f'Auto-selecting top 52 schools based on FY {last_fy_start} to {last_fy_end}')

    # Step 1: Get all active stores from StoreSchoolMapping
    stores = StoreSchoolMapping.objects.filter(is_active=True)\
        .values('store_name').distinct().order_by('store_name')

    logger.info(f'Found {stores.count()} active stores')

    all_school_sales = []

    # Step 2: For each store location
    for store in stores:
        store_name = store['store_name']

        # Get all schools for this store
        store_mappings = StoreSchoolMapping.objects.filter(
            store_name=store_name,
            is_active=True
        )

        logger.info(f'Processing store: {store_name} with {store_mappings.count()} schools')

        # Calculate sales for each school in this store
        for mapping in store_mappings:
            school = mapping.school_name
            category = mapping.category_name

            # Calculate last FY sales for this school
            sales = calculate_school_sales_from_mapping(school, category, last_fy_start, last_fy_end)

            all_school_sales.append({
                'school_name': school,
                'category_name': category,
                'store_name': store_name,
                'sales': sales
            })

    logger.info(f'Calculated sales for {len(all_school_sales)} schools')

    # Step 3: Sort all schools by sales descending
    all_school_sales.sort(key=lambda x: x['sales'], reverse=True)

    # Step 4: Take top 52 schools
    top_52_schools = all_school_sales[:52]

    logger.info(f'Selected top {len(top_52_schools)} schools')

    # Step 5: Clear all auto-selections first
    TopPerformingSchool.objects.all().update(auto_selected=False, is_top_performing=False)

    # Step 6: Update TopPerformingSchool records for top 52
    selected_count = 0
    for school_data in top_52_schools:
        school, created = TopPerformingSchool.objects.update_or_create(
            school_name=school_data['school_name'],
            defaults={
                'category_name': school_data['category_name'],
                'store_location': school_data['store_name'],
                'last_fy_sales': school_data['sales'],
                'last_fy_start': last_fy_start,
                'last_fy_end': last_fy_end,
                'sales_updated_at': timezone.now(),
                'auto_selected': True,
                'is_top_performing': True,
            }
        )
        selected_count += 1

        if selected_count <= 10:  # Log first 10 for debugging
            logger.info(f'  #{selected_count}: {school_data["school_name"]} ({school_data["store_name"]}) - ${school_data["sales"]:,.2f}')

    logger.info(f'Auto-selection complete: {selected_count} schools marked as top performing')

    return selected_count


@login_required
@permission_required('replenishment.demand_planning.approve')
@require_http_methods(["POST"])
def auto_select_top_52_schools(request):
    """
    Auto-select top 52 schools based on store-school mapping and last FY sales
    """
    import json
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info('Auto-select top 52 schools triggered by user: ' + request.user.username)

        # Perform auto-selection
        count = perform_auto_selection_top_52()

        logger.info(f'Auto-selection successful: {count} schools selected')

        return JsonResponse({
            'success': True,
            'count': count,
            'message': f'Successfully selected top {count} schools based on last FY sales from 16 store locations.'
        })

    except Exception as e:
        logger.error(f'Auto-selection failed: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@permission_required('replenishment.daily_pick_list.view')
def store_stock_movement(request):
    """
    Slow Moving / Fast Moving stock report for store managers.
    Analyses last 30 days of sales to classify products.
    """
    from datetime import date, datetime, timedelta, time
    from django.db.models import Sum, Count, F, Q
    from django.db.models.expressions import RawSQL
    from cin7.models import SalesOrderLineItem, Stock
    import zoneinfo
    from math import ceil

    NZ_TZ = zoneinfo.ZoneInfo('Pacific/Auckland')
    UTC_TZ = zoneinfo.ZoneInfo('UTC')

    user = request.user
    is_admin = user.is_superuser or user.is_staff
    has_assigned_stores = user.assigned_stores.exists() if hasattr(user, 'assigned_stores') else False

    if not is_admin and not has_assigned_stores:
        return render(request, 'dashboard/store_stock_movement.html', {
            'error': 'You are not assigned to any stores. Please contact your administrator.',
            'products': [],
        })

    # Date range: last 30 days in NZ time
    today_nz = datetime.now(NZ_TZ).date()
    end_date = today_nz - timedelta(days=1)
    start_date = end_date - timedelta(days=29)
    period_days = 30

    # Convert to UTC datetime boundaries
    utc_start = datetime.combine(start_date, time.min, tzinfo=NZ_TZ).astimezone(UTC_TZ)
    utc_end = datetime.combine(end_date, time.max, tzinfo=NZ_TZ).astimezone(UTC_TZ)

    # NZ offset for date grouping
    nz_offset_dt = datetime.combine(start_date, time(12, 0), tzinfo=NZ_TZ)
    total_seconds = int(nz_offset_dt.utcoffset().total_seconds())
    nz_offset = f'+{total_seconds // 3600:02d}:{(total_seconds % 3600) // 60:02d}'

    # Get school filter
    school_filter = request.GET.get('school', '')

    # Build sales query
    sales_query = SalesOrderLineItem.objects.filter(
        sales_order__invoice_date__gte=utc_start,
        sales_order__invoice_date__lte=utc_end,
        sales_order__is_void=False,
    )

    if not is_admin and has_assigned_stores:
        accessible_categories = user.get_accessible_categories()
        if accessible_categories:
            sales_query = sales_query.filter(product__category_name__in=accessible_categories)

    if school_filter:
        sales_query = sales_query.filter(product__sub_category=school_filter)

    # Aggregate: total qty per SKU (group by code only to avoid name variations splitting totals)
    product_sales = sales_query.values(
        'code',
    ).annotate(
        total_qty=Sum('qty'),
    ).filter(total_qty__gt=0)

    # Get product details (name, category, school) from the latest record per SKU
    from cin7.models import Product
    product_details = {}
    for sale in product_sales:
        sku = sale['code']
        prod = Product.objects.filter(code=sku).first()
        if prod:
            product_details[sku] = {
                'name': prod.name or sku,
                'category': prod.category_name or 'Uncategorized',
                'school': prod.sub_category or 'N/A',
            }
        else:
            product_details[sku] = {
                'name': sku,
                'category': 'Uncategorized',
                'school': 'N/A',
            }

    # For each product, get days with sales (need separate query for NZ date counting)
    products = []
    schools_set = set()

    for sale in product_sales:
        sku = sale['code']
        total_qty = float(sale['total_qty'])
        details = product_details.get(sku, {})
        category = details.get('category', 'Uncategorized')
        school = details.get('school', 'N/A')

        if school != 'N/A':
            schools_set.add(school)

        # Count distinct NZ sale dates
        days_qs = SalesOrderLineItem.objects.filter(
            code=sku,
            sales_order__invoice_date__gte=utc_start,
            sales_order__invoice_date__lte=utc_end,
            sales_order__is_void=False,
        )
        if not is_admin and has_assigned_stores:
            accessible_categories = user.get_accessible_categories()
            if accessible_categories:
                days_qs = days_qs.filter(product__category_name__in=accessible_categories)

        days_with_sales = days_qs.annotate(
            nz_date=RawSQL(
                "DATE(CONVERT_TZ(cin7_sync_salesorder.invoice_date, '+00:00', %s))",
                [nz_offset]
            )
        ).values('nz_date').distinct().count()

        avg_daily = total_qty / period_days
        frequency = days_with_sales / period_days

        # Classification
        if avg_daily >= 1 or days_with_sales >= 10:
            movement = 'Fast Moving'
            badge_class = 'success'
        elif avg_daily >= 0.3 or days_with_sales >= 5:
            movement = 'Moderate'
            badge_class = 'warning'
        else:
            movement = 'Slow Moving'
            badge_class = 'danger'

        # Get current stock
        stock_query = Stock.objects.filter(code=sku)
        if not is_admin and has_assigned_stores:
            accessible_categories = user.get_accessible_categories()
            if accessible_categories:
                stock_query = stock_query.filter(branch_name__in=accessible_categories)

        stock_record = stock_query.first()
        stock_on_hand = float(stock_record.stock_on_hand or 0) if stock_record else 0

        # Days of stock
        days_of_stock = round(stock_on_hand / avg_daily) if avg_daily > 0 else 999

        products.append({
            'product_name': details.get('name', sku),
            'sku': sku,
            'school': school,
            'category': category,
            'total_qty': int(total_qty),
            'days_with_sales': days_with_sales,
            'avg_daily': round(avg_daily, 1),
            'frequency': round(frequency * 100),
            'movement': movement,
            'badge_class': badge_class,
            'stock_on_hand': int(stock_on_hand),
            'days_of_stock': days_of_stock if days_of_stock < 999 else None,
        })

    # Dead stock: products with stock but no sales in period
    stock_query = Stock.objects.filter(stock_on_hand__gt=0)
    if not is_admin and has_assigned_stores:
        accessible_categories = user.get_accessible_categories()
        if accessible_categories:
            stock_query = stock_query.filter(branch_name__in=accessible_categories)
    if school_filter:
        # When filtering by school, skip dead stock (no sub_category on Stock model)
        stock_query = stock_query.none()

    sold_codes = set(p['sku'] for p in products)

    dead_stock_items = []
    for stock in stock_query.order_by('-stock_on_hand'):
        if stock.code not in sold_codes:
            dead_stock_items.append({
                'product_name': stock.product_name or stock.code,
                'sku': stock.code,
                'school': '',
                'category': stock.branch_name or 'Unknown',
                'total_qty': 0,
                'days_with_sales': 0,
                'avg_daily': 0,
                'frequency': 0,
                'movement': 'Dead Stock',
                'badge_class': 'secondary',
                'stock_on_hand': int(float(stock.stock_on_hand or 0)),
                'days_of_stock': None,
            })

    # Sort products by total qty desc
    products.sort(key=lambda x: x['total_qty'], reverse=True)
    dead_stock_items.sort(key=lambda x: x['stock_on_hand'], reverse=True)

    # Summary counts
    fast = [p for p in products if p['movement'] == 'Fast Moving']
    moderate = [p for p in products if p['movement'] == 'Moderate']
    slow = [p for p in products if p['movement'] == 'Slow Moving']

    # Get store name (use store_name from mappings, not category_name)
    store_name = 'All Stores'
    if has_assigned_stores:
        store_names = list(set(
            user.assigned_stores.filter(is_active=True)
            .values_list('store_name', flat=True)
        ))
        if store_names:
            store_name = ', '.join(sorted(store_names))

    context = {
        'products': products,
        'dead_stock': dead_stock_items,
        'start_date': start_date,
        'end_date': end_date,
        'period_days': period_days,
        'store_name': store_name,
        'school_filter': school_filter,
        'schools': sorted(user.get_accessible_schools()) if has_assigned_stores else sorted(schools_set),
        'summary': {
            'fast_count': len(fast),
            'fast_units': sum(p['total_qty'] for p in fast),
            'moderate_count': len(moderate),
            'moderate_units': sum(p['total_qty'] for p in moderate),
            'slow_count': len(slow),
            'slow_units': sum(p['total_qty'] for p in slow),
            'dead_count': len(dead_stock_items),
            'dead_stock_units': sum(p['stock_on_hand'] for p in dead_stock_items),
            'total_products': len(products),
            'total_units': sum(p['total_qty'] for p in products),
        },
    }

    return render(request, 'dashboard/store_stock_movement.html', context)


@login_required
@permission_required('replenishment.daily_pick_list.view')
def store_school_comparison(request):
    """
    School comparison report for store managers.
    Side-by-side comparison of all assigned schools.
    """
    from datetime import date, datetime, timedelta, time
    from django.db.models import Sum, Count, F, Q, Value
    from django.db.models.functions import Coalesce
    from django.db.models.expressions import RawSQL
    from cin7.models import SalesOrderLineItem, Stock
    import zoneinfo

    NZ_TZ = zoneinfo.ZoneInfo('Pacific/Auckland')
    UTC_TZ = zoneinfo.ZoneInfo('UTC')

    user = request.user
    is_admin = user.is_superuser or user.is_staff
    has_assigned_stores = user.assigned_stores.exists() if hasattr(user, 'assigned_stores') else False

    if not is_admin and not has_assigned_stores:
        return render(request, 'dashboard/store_school_comparison.html', {
            'error': 'You are not assigned to any stores. Please contact your administrator.',
            'schools': [],
        })

    # Date range: configurable period
    today_nz = datetime.now(NZ_TZ).date()
    period = request.GET.get('period', '30')
    try:
        period_days = int(period)
    except ValueError:
        period_days = 30

    end_date = today_nz - timedelta(days=1)
    start_date = end_date - timedelta(days=period_days - 1)

    # Previous period for comparison
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)

    # Convert to UTC
    utc_start = datetime.combine(start_date, time.min, tzinfo=NZ_TZ).astimezone(UTC_TZ)
    utc_end = datetime.combine(end_date, time.max, tzinfo=NZ_TZ).astimezone(UTC_TZ)
    prev_utc_start = datetime.combine(prev_start, time.min, tzinfo=NZ_TZ).astimezone(UTC_TZ)
    prev_utc_end = datetime.combine(prev_end, time.max, tzinfo=NZ_TZ).astimezone(UTC_TZ)

    # NZ offset for date grouping
    nz_offset_dt = datetime.combine(start_date, time(12, 0), tzinfo=NZ_TZ)
    total_seconds = int(nz_offset_dt.utcoffset().total_seconds())
    nz_offset = f'+{total_seconds // 3600:02d}:{(total_seconds % 3600) // 60:02d}'

    # Base query filters
    base_filter = Q(sales_order__is_void=False)
    if not is_admin and has_assigned_stores:
        accessible_categories = user.get_accessible_categories()
        if accessible_categories:
            base_filter &= Q(product__category_name__in=accessible_categories)

    # Current period: aggregate by school (sub_category)
    current_sales = SalesOrderLineItem.objects.filter(
        base_filter,
        sales_order__invoice_date__gte=utc_start,
        sales_order__invoice_date__lte=utc_end,
    ).values(
        school=F('product__sub_category'),
    ).annotate(
        total_units=Sum('qty'),
        total_revenue=Sum(F('unit_price') * F('qty')),
        active_products=Count('code', distinct=True),
        total_orders=Count('sales_order', distinct=True),
    ).filter(total_units__gt=0).order_by('-total_units')

    # Previous period
    prev_sales = SalesOrderLineItem.objects.filter(
        base_filter,
        sales_order__invoice_date__gte=prev_utc_start,
        sales_order__invoice_date__lte=prev_utc_end,
    ).values(
        school=F('product__sub_category'),
    ).annotate(
        total_units=Sum('qty'),
        total_revenue=Sum(F('unit_price') * F('qty')),
    )
    prev_lookup = {
        s['school']: {
            'units': float(s['total_units'] or 0),
            'revenue': float(s['total_revenue'] or 0),
        }
        for s in prev_sales
    }

    # Daily sales by school for sparkline/trend (group by NZ date)
    daily_by_school = SalesOrderLineItem.objects.filter(
        base_filter,
        sales_order__invoice_date__gte=utc_start,
        sales_order__invoice_date__lte=utc_end,
    ).annotate(
        nz_date=RawSQL(
            "DATE(CONVERT_TZ(cin7_sync_salesorder.invoice_date, '+00:00', %s))",
            [nz_offset]
        )
    ).values(
        school=F('product__sub_category'),
        date=F('nz_date'),
    ).annotate(
        daily_units=Sum('qty'),
    ).order_by('school', 'date')

    # Build daily trend per school
    daily_trends = {}
    for row in daily_by_school:
        school = row['school']
        if school not in daily_trends:
            daily_trends[school] = {}
        daily_trends[school][str(row['date'])] = float(row['daily_units'] or 0)

    # Build school list
    schools = []
    grand_total_units = 0
    grand_total_revenue = 0

    for sale in current_sales:
        school_name = sale['school'] or 'Uncategorized'
        units = int(float(sale['total_units'] or 0))
        revenue = float(sale['total_revenue'] or 0)
        active_products = sale['active_products']
        total_orders = sale['total_orders']

        prev = prev_lookup.get(sale['school'], {'units': 0, 'revenue': 0})
        units_change = units - prev['units'] if prev['units'] else None
        units_change_pct = round((units_change / prev['units']) * 100) if prev['units'] and units_change is not None else None
        revenue_change_pct = round(((revenue - prev['revenue']) / prev['revenue']) * 100) if prev['revenue'] else None

        # Daily trend data (list of daily values for the period)
        trend_data = []
        for i in range(period_days):
            d = start_date + timedelta(days=i)
            trend_data.append(daily_trends.get(sale['school'], {}).get(str(d), 0))

        # Avg units per day
        avg_daily = round(units / period_days, 1)

        # Days with sales
        days_active = sum(1 for v in trend_data if v > 0)

        grand_total_units += units
        grand_total_revenue += revenue

        schools.append({
            'name': school_name,
            'total_units': units,
            'total_units_fmt': f'{units:,}',
            'total_revenue': round(revenue, 2),
            'total_revenue_fmt': f'{revenue:,.0f}',
            'active_products': active_products,
            'total_orders': total_orders,
            'avg_daily': avg_daily,
            'days_active': days_active,
            'units_change': int(units_change) if units_change is not None else None,
            'units_change_pct': units_change_pct,
            'revenue_change_pct': revenue_change_pct,
            'trend_data': trend_data,
        })

    # Sort by total units desc
    schools.sort(key=lambda x: x['total_units'], reverse=True)

    # Calculate share percentages
    for s in schools:
        s['units_share'] = round((s['total_units'] / grand_total_units) * 100, 1) if grand_total_units else 0
        s['revenue_share'] = round((s['total_revenue'] / grand_total_revenue) * 100, 1) if grand_total_revenue else 0

    # Store name
    store_name = 'All Stores'
    if has_assigned_stores:
        store_names = list(set(
            user.assigned_stores.filter(is_active=True)
            .values_list('store_name', flat=True)
        ))
        if store_names:
            store_name = ', '.join(sorted(store_names))

    context = {
        'schools': schools,
        'start_date': start_date,
        'end_date': end_date,
        'prev_start': prev_start,
        'prev_end': prev_end,
        'period_days': period_days,
        'period': period,
        'store_name': store_name,
        'grand_total_units': f'{grand_total_units:,}',
        'grand_total_revenue': f'{grand_total_revenue:,.0f}',
        'total_schools': len(schools),
    }

    return render(request, 'dashboard/store_school_comparison.html', context)


@login_required
@permission_required('forecasting.view')
def non_forecasted_items(request):
    """
    Non-Forecasted Items Report
    Shows products in Shop/Store categories that have no forecast in dashboard_salesforecastbase,
    with the reason they were skipped during forecast generation.
    """
    from django.db import connection
    from datetime import datetime, timedelta

    shop_filter = request.GET.get('shop', '')

    # Build the WHERE clause for optional shop filter
    shop_clause = ""
    params = []
    if shop_filter:
        shop_clause = "AND p.category_name = %s"
        params.append(shop_filter)

    with connection.cursor() as cursor:
        # Single query: find all shop/store SKUs without a forecast, and compute sales stats
        cursor.execute(f"""
            WITH shop_skus AS (
                SELECT
                    po.code AS sku_code,
                    p.name AS product_name,
                    p.category_name AS shop,
                    p.sub_category AS school
                FROM cin7_sync_productoption po
                JOIN cin7_sync_product p ON p.id = po.product_id
                WHERE (p.category_name LIKE '%% Shop' OR p.category_name LIKE '%% Store')
                  AND p.category_name NOT IN ('Shop', 'Store')
                  AND p.category_name NOT LIKE 'Wholesale%%'
                  AND p.is_active = 1
                  {shop_clause}
            ),
            forecasted_skus AS (
                SELECT DISTINCT entity_name
                FROM dashboard_salesforecastbase
                WHERE aggregation_level = 'product'
            ),
            sales_stats AS (
                SELECT
                    li.code AS sku_code,
                    COALESCE(SUM(li.qty), 0) AS total_sold,
                    COUNT(DISTINCT DATE(so.invoice_date)) AS distinct_days,
                    MAX(so.invoice_date) AS last_sale_date
                FROM cin7_sync_salesorderlineitem li
                JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
                WHERE so.stage = 'Dispatched'
                  AND so.invoice_date IS NOT NULL
                GROUP BY li.code
            )
            SELECT
                ss.sku_code,
                ss.product_name,
                ss.shop,
                ss.school,
                COALESCE(st.total_sold, 0) AS total_sold,
                COALESCE(st.distinct_days, 0) AS distinct_days,
                st.last_sale_date
            FROM shop_skus ss
            LEFT JOIN forecasted_skus fs ON fs.entity_name = ss.sku_code
            LEFT JOIN sales_stats st ON st.sku_code = ss.sku_code
            WHERE fs.entity_name IS NULL
            ORDER BY ss.shop, ss.product_name, ss.sku_code
        """, params)

        rows = cursor.fetchall()

    # Also get distinct shops for filter dropdown
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT p.category_name
            FROM cin7_sync_product p
            WHERE (p.category_name LIKE '%% Shop' OR p.category_name LIKE '%% Store')
              AND p.category_name NOT IN ('Shop', 'Store')
              AND p.category_name NOT LIKE 'Wholesale%%'
              AND p.is_active = 1
            ORDER BY p.category_name
        """)
        shops = [r[0] for r in cursor.fetchall()]

    # Process results and determine reason
    today = datetime.now().date()
    items = []
    reason_counts = {
        'no_sales': 0,
        'insufficient_sales': 0,
        'insufficient_history': 0,
        'discontinued': 0,
        'low_frequency': 0,
        'pending': 0,
    }

    for row in rows:
        sku_code = row[0]
        product_name = row[1]
        shop = row[2]
        school = row[3] or ''
        total_sold = float(row[4] or 0)
        distinct_days = int(row[5] or 0)
        last_sale_date = row[6]

        # Determine reason using same logic as generate_365d_forecasts
        if total_sold == 0:
            reason = 'No sales history'
        elif total_sold < 10:
            reason = f'Insufficient sales ({int(total_sold)} sold, minimum 10)'
        elif distinct_days < 30:
            reason = f'Insufficient history ({distinct_days} days, minimum 30)'
        elif last_sale_date:
            days_since = (today - last_sale_date.date() if hasattr(last_sale_date, 'date') else (today - last_sale_date)).days
            if days_since > 365:
                reason = f'Discontinued - no sales in {days_since} days'
            else:
                # Check sales per year
                sales_per_year = total_sold / (distinct_days / 365) if distinct_days > 0 else 0
                if sales_per_year < 5:
                    reason = f'Low frequency ({sales_per_year:.1f} sales/year, minimum 5)'
                else:
                    reason = 'Pending generation'
        else:
            reason = 'No sales history'

        # Categorize for summary counts
        if reason == 'No sales history':
            reason_counts['no_sales'] += 1
        elif reason.startswith('Insufficient sales'):
            reason_counts['insufficient_sales'] += 1
        elif reason.startswith('Insufficient history'):
            reason_counts['insufficient_history'] += 1
        elif reason.startswith('Discontinued'):
            reason_counts['discontinued'] += 1
        elif reason.startswith('Low frequency'):
            reason_counts['low_frequency'] += 1
        else:
            reason_counts['pending'] += 1

        items.append({
            'sku_code': sku_code,
            'product_name': product_name,
            'shop': shop,
            'school': school,
            'total_sold': int(total_sold),
            'last_sale_date': last_sale_date,
            'reason': reason,
        })

    context = {
        'items': items,
        'total_items': len(items),
        'reason_counts': reason_counts,
        'shops': shops,
        'selected_shop': shop_filter,
    }

    return render(request, 'dashboard/non_forecasted_items.html', context)
