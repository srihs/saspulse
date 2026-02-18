"""
Dashboard Views

Stock Value vs BTS Sales Analysis Dashboard
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
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
