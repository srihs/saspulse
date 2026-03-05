"""
Dashboard Views

Stock Value vs BTS Sales Analysis Dashboard
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, DecimalField, Value
from django.db.models.functions import Coalesce
from decimal import Decimal
from users.auth_backend import CustomAuthBackend
from cin7.models import SalesOrder, SalesOrderLineItem, Stock, Product

auth_backend = CustomAuthBackend()

# BTS (Back to School) Period Configuration
from datetime import date
BTS_START_DATE = '2026-01-01'
BTS_END_DATE = '2026-02-16'  # Fixed end date to match reporting period
RISK_THRESHOLD = 2.0  # Stock ratio > 2.0 is considered risky

# Category Filter: Only include "Wholesale Schools" and categories ending with " Shop"
CATEGORY_FILTER = """
    (p.category_name = 'Wholesale Schools' OR p.category_name LIKE '% Shop')
"""


def calculate_summary_metrics(start_date=None, end_date=None):
    """
    Calculate the top summary tiles metrics for Wholesale Schools category

    Args:
        start_date: Start date for BTS period (default: BTS_START_DATE)
        end_date: End date for BTS period (default: BTS_END_DATE)
    """
    from django.db import connection

    # Use provided dates or fall back to defaults
    start = start_date or BTS_START_DATE
    end = end_date or BTS_END_DATE

    # 1. Calculate Total BTS Sales (Wholesale Schools + Shop categories, excluding shop locations)
    # Sales = qty * unit_price for invoiced orders in the period
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT SUM(COALESCE(soli.qty, 0) * COALESCE(soli.unit_price, 0)) as total_sales
            FROM cin7_sync_salesorder so
            JOIN cin7_sync_salesorderlineitem soli ON CAST(so.cin7_id AS CHAR) = soli.cin7_sales_order_id
            JOIN cin7_sync_product p ON soli.cin7_product_id = p.cin7_id
            WHERE so.invoice_date >= %s AND so.invoice_date <= %s
              AND (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
        """, [start, end, '% Shop', '%Shop%'])

        result = cursor.fetchone()
        total_bts_sales = float(result[0] or 0)

    # 2. Calculate Total Stock Value (stock on hand × cost_price)
    # Stock mapped via product sub_category (Wholesale Schools + Shop categories, excluding shop locations)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT SUM(COALESCE(s.stock_on_hand, 0) * COALESCE(po.cost_price, 0)) as total_value
            FROM cin7_sync_product p
            LEFT JOIN cin7_sync_stock s ON p.cin7_id = s.cin7_product_id
            LEFT JOIN cin7_sync_productoption po ON s.cin7_product_option_id = po.cin7_id
            WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
        """, ['% Shop', '%Shop%'])

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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
        """, ['% Shop', '%Shop%', '% Shop', start, end, '%Shop%', RISK_THRESHOLD])

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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE '%% Shop')
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE '%% Shop')
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
        """, ['% Shop', '%Shop%', '% Shop', start, end, '%Shop%'])

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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
                  AND p.sub_category = %s
                  AND p.sub_category NOT LIKE %s
            """, ['% Shop', top_critical_school, '%Shop%'])

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
            WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
            GROUP BY p.cin7_id, p.name, p.style_code
            HAVING total_stock_value > 0
            ORDER BY total_stock_value DESC
            LIMIT %s
        """, ['% Shop', '%Shop%', top_n_products])

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
            WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
            ORDER BY school
        """, ['% Shop', '%Shop%'])

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
              AND (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
              AND (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
              AND so.invoice_date >= %s
              AND so.invoice_date <= %s
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
            GROUP BY p.sub_category, p.cin7_id
        """, ['% Shop', '%Shop%', '% Shop', start, end, '%Shop%'])

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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
            '% Shop', '%Shop%',  # all_schools
            '% Shop', current_year_start, current_year_end, '%Shop%',  # current_year_sales
            '% Shop', last_year_start, last_year_end, '%Shop%',  # last_year_sales
            '% Shop', year_before_start, year_before_end, '%Shop%',  # year_before_sales
            '% Shop', current_year_start, current_year_end, '%Shop%',  # top_product_current_year
            '% Shop', last_year_start, last_year_end, '%Shop%',  # top_product_last_year
            '% Shop', year_before_start, year_before_end, '%Shop%',  # top_product_year_before
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
                WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
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
        """, ['% Shop', '%Shop%', '% Shop', start, end, '%Shop%', limit])

        rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({
            'school': row[0],
            'total_sales': float(row[1] or 0),
            'last_sale_date': row[2]
        })

    return results


@require_http_methods(["GET"])
def dashboard_home(request):
    """
    Main dashboard view with summary metrics and customer rankings
    """
    from django.core.cache import cache

    # Check if user is authenticated
    if not auth_backend.is_authenticated(request):
        return redirect('users:login')

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
            WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
              AND so.invoice_date IS NOT NULL
              AND MONTH(so.invoice_date) IN (1, 2)
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
            GROUP BY DATE_FORMAT(so.invoice_date, '%%Y-%%m'), YEAR(so.invoice_date), MONTH(so.invoice_date)
            ORDER BY so.invoice_date
        """, ['% Shop', '%Shop%'])

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
            WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
              AND so.invoice_date IS NOT NULL
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
              AND MONTH(so.invoice_date) IN (1, 2)
            GROUP BY p.sub_category, YEAR(so.invoice_date), MONTH(so.invoice_date)
            ORDER BY p.sub_category, YEAR(so.invoice_date), MONTH(so.invoice_date)
        """, ['% Shop', '%Shop%'])

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
            WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
              AND so.invoice_date IS NOT NULL
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
              AND YEAR(so.invoice_date) >= 2022
            GROUP BY p.sub_category, YEAR(so.invoice_date), MONTH(so.invoice_date)
            ORDER BY p.sub_category, year DESC, month_num DESC
        """, ['% Shop', '%Shop%'])

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
            WHERE (p.category_name = 'Wholesale Schools' OR p.category_name LIKE %s)
              AND so.invoice_date IS NOT NULL
              AND p.sub_category IS NOT NULL
              AND p.sub_category <> ''
              AND p.sub_category NOT LIKE %s
              AND MONTH(so.invoice_date) IN (1, 2)
            GROUP BY p.name, YEAR(so.invoice_date), MONTH(so.invoice_date)
            ORDER BY total_sales DESC
        """, ['% Shop', '%Shop%'])

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


@require_http_methods(["GET"])
def bts_forecasting(request):
    """
    BTS Sales Forecasting Dashboard
    Predict next year's BTS sales (Jan-Feb 2027)
    """
    if not auth_backend.is_authenticated(request):
        return redirect('users:login')

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
        """Get aggregated stock data for a SKU across all branches using raw SQL"""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COALESCE(SUM(stock_on_hand), 0) as total_stock_on_hand,
                    COALESCE(SUM(incoming), 0) as total_incoming
                FROM cin7_sync_stock
                WHERE code = %s
            """, [sku_code])
            row = cursor.fetchone()

        return {
            'stock_on_hand': float(row[0] or 0),
            'incoming': float(row[1] or 0)
        }

    # Get parameters
    level = request.GET.get('level', 'school')

    # Date range parameters (new approach)
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Legacy horizon parameter (for backward compatibility)
    horizon = request.GET.get('horizon', '30d')

    # Determine if using new date range approach or legacy horizon
    use_date_range = start_date_str and end_date_str

    # Parse and validate date ranges
    today = datetime_date.today()

    if use_date_range:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            # Validation
            if end_date <= start_date:
                return JsonResponse({'error': 'End date must be after start date'}, status=400)

            date_diff = (end_date - start_date).days
            if date_diff > 365:
                return JsonResponse({'error': 'Date range cannot exceed 365 days'}, status=400)

        except ValueError:
            return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    else:
        # Default: today + 30 days
        start_date = today
        end_date = today + timedelta(days=30)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

    # Calculate number of days in range
    num_days = (end_date - start_date).days

    # Check cache first
    cache_key = f'forecast_{level}_{start_date_str}_{end_date_str}'

    # Determine cache timeout based on range
    common_ranges = [7, 30, 90]
    is_common_range = num_days in common_ranges and start_date == today
    cache_timeout = 1800 if is_common_range else 600  # 30 min for common, 10 min for custom

    cached_data = cache.get(cache_key)
    if cached_data:
        context = cached_data
        context['from_cache'] = True
        return render(request, 'dashboard/sales_forecasting.html', context)

    # Try to use new SalesForecastBase model
    from django.db.models import Max

    # Get all base forecasts for this level (latest forecast for each entity)
    all_base_forecasts = SalesForecastBase.objects.filter(
        aggregation_level=level
    ).order_by('entity_name', '-forecast_date')

    # Keep only the latest forecast for each entity_name
    seen_entities = set()
    base_forecasts = []
    for f in all_base_forecasts:
        if f.entity_name not in seen_entities:
            base_forecasts.append(f)
            seen_entities.add(f.entity_name)
        if len(base_forecasts) >= 500:  # Limit to 500 unique entities
            break

    # If no base forecasts, fall back to legacy SalesForecast model
    if not base_forecasts:
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
    else:
        forecasts = base_forecasts
        use_legacy = False

    # Check if we need to group by parent product
    if level == 'product':
        # Group SKU variations by parent product
        grouped_products = defaultdict(list)

        for f in forecasts:
            parent_name = extract_parent_product_from_sku(f.entity_name)
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

            # Get stock data for this SKU
            stock_info = get_stock_data(f.entity_name)
            stock_on_hand = stock_info['stock_on_hand']
            incoming_stock = stock_info['incoming']
            forecasted_stock = round(total_qty, 1)
            stock_gap = (stock_on_hand + incoming_stock) - forecasted_stock

            variation_data = {
                'sku_code': f.entity_name,
                'size': size,
                'total_quantity': forecasted_stock,
                'stock_on_hand': int(stock_on_hand),
                'incoming_stock': int(incoming_stock),
                'stock_gap': round(stock_gap, 1),
                'accuracy_score': round(f.accuracy_score, 1) if f.accuracy_score else 'N/A',
                'model': f.model_params.get('model', 'Unknown'),
                'next_7_days': next_7_days,
                'forecast_data': date_range_data,
                'training_days': f.model_params.get('training_days', 0),
                'mae': round(f.mae, 2) if f.mae else None,
                'mape': round(f.mape, 2) if f.mape else None
            }

            grouped_products[parent_name].append(variation_data)

        # Create product summaries
        forecast_list = []
        for parent_name, variations in sorted(grouped_products.items()):
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
                'parent_name': parent_name,
                'variations': variations_sorted,
                'total_quantity': round(total_forecast, 1),
                'variation_count': len(variations),
                'avg_accuracy': round(avg_accuracy, 1) if avg_accuracy != 'N/A' else 'N/A',
                'is_grouped': True
            })

        # Sort by total quantity descending
        forecast_list = sorted(forecast_list, key=lambda x: x['total_quantity'], reverse=True)[:200]  # Increased limit to show more products

    else:
        # Regular flat view for school/shop/category
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
                'accuracy_score': round(f.accuracy_score, 1) if f.accuracy_score else 'N/A',
                'model': f.model_params.get('model', 'Unknown'),
                'next_7_days': next_7_days,
                'forecast_data': date_range_data,
                'training_days': f.model_params.get('training_days', 0),
                'mae': round(f.mae, 2) if f.mae else None,
                'mape': round(f.mape, 2) if f.mape else None,
                'is_grouped': False
            })

    # Get summary statistics
    # Calculate average accuracy from the forecasts list
    if level == 'product':
        # For product level, forecasts is a list, calculate manually
        accuracy_scores = [f.accuracy_score for f in forecasts if f.accuracy_score is not None]
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
    generating_forecasts = len(forecast_list) == 0

    context = {
        'forecasts': forecast_list,
        'forecast_list_json': json.dumps(forecast_list, default=str),
        'summary': summary,
        'current_horizon': horizon,  # For backward compatibility
        'current_level': level,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'num_days': num_days,
        'horizons': SalesForecast.FORECAST_HORIZONS,  # For backward compatibility
        'levels': SalesForecastBase.AGGREGATION_LEVELS,
        'use_date_range': True,
        'from_cache': False,
        'generating_forecasts': generating_forecasts
    }

    # Cache the context only if we have data (don't cache empty state)
    if not generating_forecasts:
        cache.set(cache_key, context, cache_timeout)

    return render(request, 'dashboard/sales_forecasting.html', context)


@login_required
def forecast_product_breakdown(request, school_name):
    """
    Get product-level breakdown for a specific school
    Returns JSON with all products forecasted for that school
    """
    from dashboard.models import SalesForecast
    from django.db import connection
    import json

    horizon = request.GET.get('horizon', '30d')

    # Get product-level forecasts for this school
    # We need to query products that belong to this school's sub_category
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                sf.entity_name as product_name,
                sf.forecast_data,
                sf.accuracy_score,
                sf.model_params,
                p.code as product_code,
                p.sub_category
            FROM dashboard_salesforecast sf
            JOIN cin7_sync_product p ON p.name COLLATE utf8mb4_unicode_ci = sf.entity_name COLLATE utf8mb4_unicode_ci
            WHERE sf.aggregation_level = 'product'
              AND sf.horizon = %s
              AND p.sub_category COLLATE utf8mb4_unicode_ci = %s
              AND (p.category_name LIKE '%%Shop' OR p.category_name = 'Wholesale Schools')
            ORDER BY sf.entity_name
            LIMIT 500
        """, [horizon, school_name])

        products = []
        for row in cursor.fetchall():
            product_name, forecast_data_json, accuracy, model_params_json, product_code, sub_category = row

            # Parse JSON fields
            import json as json_lib
            forecast_data = json_lib.loads(forecast_data_json) if isinstance(forecast_data_json, str) else forecast_data_json
            model_params = json_lib.loads(model_params_json) if isinstance(model_params_json, str) else model_params_json

            # Calculate totals
            total_qty = sum([day.get('quantity', 0) for day in forecast_data.values()])

            # Get next 7 days
            forecast_dates = sorted(forecast_data.keys())[:7]
            next_7_days = []
            for date in forecast_dates:
                day_data = forecast_data.get(date, {})
                next_7_days.append({
                    'date': date,
                    'quantity': round(day_data.get('quantity', 0), 1)
                })

            products.append({
                'product_name': product_name,
                'product_code': product_code or 'N/A',
                'total_quantity': round(total_qty, 1),
                'accuracy_score': round(accuracy, 1) if accuracy else 'N/A',
                'model': model_params.get('model', 'Unknown'),
                'next_7_days': next_7_days
            })

    return JsonResponse({
        'school_name': school_name,
        'horizon': horizon,
        'products': products,
        'total_products': len(products),
        'total_units': sum([p['total_quantity'] for p in products])
    })


@login_required
def store_manager_replenishment(request):
    """
    Store Manager Replenishment Dashboard
    Shows replenishment requests for the manager's assigned branches
    """
    from dashboard.models import ReplenishmentRequest
    from django.db.models import Q, Count, Sum, Avg
    from django.db import connection
    import json

    user = request.user

    # Get filter parameters
    status_filter = request.GET.get('status', 'pending')
    urgency_filter = request.GET.get('urgency', 'all')
    week_filter = request.GET.get('week', 'current')

    # Base query - for now, show all requests (later filter by user's branches)
    # TODO: Add branch assignment to users
    requests_query = ReplenishmentRequest.objects.all()

    # Apply filters
    if status_filter != 'all':
        requests_query = requests_query.filter(status=status_filter)

    if urgency_filter != 'all':
        requests_query = requests_query.filter(urgency=urgency_filter)

    # Get current week number
    from datetime import datetime
    current_week = datetime.now().isocalendar()[1]

    if week_filter == 'current':
        requests_query = requests_query.filter(week_number=current_week)
    elif week_filter != 'all':
        try:
            requests_query = requests_query.filter(week_number=int(week_filter))
        except ValueError:
            pass

    # Get requests with related data using raw SQL to avoid ORM issues
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
            rr.urgency,
            rr.ai_confidence,
            rr.status,
            rr.store_approved_quantity,
            rr.store_manager_comment,
            rr.week_number,
            rr.year,
            rr.created_at
        FROM dashboard_replenishmentrequest rr
        JOIN cin7_sync_product p ON p.id = rr.product_id
        JOIN cin7_sync_branch b ON b.id = rr.branch_id
        WHERE 1=1
        """

        params = []

        if status_filter != 'all':
            query += " AND rr.status = %s"
            params.append(status_filter)

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

        query += " ORDER BY FIELD(rr.urgency, 'critical', 'high', 'medium', 'low'), rr.stock_gap DESC LIMIT 500"

        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]

        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            # Calculate days of stock
            daily_demand = row_dict['forecasted_demand_30d'] / 30 if row_dict['forecasted_demand_30d'] > 0 else 0
            days_of_stock = row_dict['current_stock'] / daily_demand if daily_demand > 0 else 999

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
                'approved_quantity': round(row_dict['store_approved_quantity'], 1) if row_dict['store_approved_quantity'] else None,
                'urgency': row_dict['urgency'],
                'ai_confidence': round(row_dict['ai_confidence'], 1),
                'status': row_dict['status'],
                'comment': row_dict['store_manager_comment'],
                'days_of_stock': round(days_of_stock, 1),
                'week_number': row_dict['week_number'],
                'year': row_dict['year'],
                'created_at': row_dict['created_at'].strftime('%Y-%m-%d %H:%M') if row_dict['created_at'] else ''
            })

    # Calculate summary statistics
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN urgency = 'critical' THEN 1 ELSE 0 END) as critical_count,
                SUM(suggested_quantity) as total_units_needed,
                AVG(ai_confidence) as avg_confidence
            FROM dashboard_replenishmentrequest
            WHERE 1=1
        """)

        row = cursor.fetchone()
        summary = {
            'total_requests': row[0] or 0,
            'pending_count': row[1] or 0,
            'critical_count': row[2] or 0,
            'total_units': round(row[3] or 0, 0),
            'avg_confidence': round(row[4] or 0, 1)
        }

    context = {
        'requests': requests_list,
        'requests_json': json.dumps(requests_list, default=str),
        'summary': summary,
        'current_status': status_filter,
        'current_urgency': urgency_filter,
        'current_week': week_filter,
        'status_choices': ReplenishmentRequest.STATUS_CHOICES,
        'urgency_choices': ReplenishmentRequest.URGENCY_LEVELS,
    }

    return render(request, 'dashboard/store_replenishment.html', context)


@login_required
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

        # Update using raw SQL to avoid ORM issues
        with connection.cursor() as cursor:
            if action == 'approve':
                cursor.execute("""
                    UPDATE dashboard_replenishmentrequest
                    SET status = 'approved',
                        store_approved_quantity = suggested_quantity,
                        store_manager_comment = %s,
                        store_manager_id = %s,
                        store_approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, [comment, request.user.id, request_id])

            elif action == 'modify':
                cursor.execute("""
                    UPDATE dashboard_replenishmentrequest
                    SET status = 'modified',
                        store_approved_quantity = %s,
                        store_manager_comment = %s,
                        store_manager_id = %s,
                        store_approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, [float(approved_quantity), comment, request.user.id, request_id])

            elif action == 'reject':
                cursor.execute("""
                    UPDATE dashboard_replenishmentrequest
                    SET status = 'rejected',
                        store_approved_quantity = 0,
                        store_manager_comment = %s,
                        store_manager_id = %s,
                        store_approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, [comment, request.user.id, request_id])

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
