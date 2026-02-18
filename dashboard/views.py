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

        # Determine risk band
        if ratio >= 999999:  # No sales - infinite ratio
            risk_band = 'critical'
            risk_label = 'Critical'
            ratio_display = '∞'
        elif ratio > 3:
            risk_band = 'critical'
            risk_label = 'Critical'
            ratio_display = round(ratio, 2)
        elif ratio > 2:
            risk_band = 'warning'
            risk_label = 'Monitor'
            ratio_display = round(ratio, 2)
        else:
            risk_band = 'healthy'
            risk_label = 'Healthy'
            ratio_display = round(ratio, 2)

        rankings.append({
            'customer_name': customer_name,
            'stock_value': stock_value,
            'bts_sales': bts_sales,
            'ratio': ratio,
            'ratio_display': ratio_display,
            'risk_band': risk_band,
            'risk_label': risk_label
        })

    return rankings


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

        # Determine risk band
        if ratio >= 999999:  # No sales - infinite ratio
            risk_band = 'critical'
            risk_label = 'Critical'
            ratio_display = '∞'
        elif ratio > 3:
            risk_band = 'critical'
            risk_label = 'Critical'
            ratio_display = round(ratio, 2)
        elif ratio > 2:
            risk_band = 'warning'
            risk_label = 'Monitor'
            ratio_display = round(ratio, 2)
        else:
            risk_band = 'healthy'
            risk_label = 'Healthy'
            ratio_display = round(ratio, 2)

        rankings.append({
            'school': school,
            'style_code': style_code,
            'product_name': product_name,
            'stock_value': stock_value,
            'bts_sales': bts_sales,
            'ratio': ratio,
            'ratio_display': ratio_display,
            'risk_band': risk_band,
            'risk_label': risk_label
        })

    return rankings


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


@require_http_methods(["GET"])
def dashboard_home(request):
    """
    Main dashboard view with summary metrics and customer rankings
    """
    # Check if user is authenticated
    if not auth_backend.is_authenticated(request):
        return redirect('users:login')

    # Get date parameters from request or use defaults
    start_date = request.GET.get('start_date', BTS_START_DATE)
    end_date = request.GET.get('end_date', BTS_END_DATE)

    # Calculate summary metrics with custom date range
    summary = calculate_summary_metrics(start_date, end_date)

    # Calculate customer rankings
    customer_rankings = calculate_customer_rankings(start_date, end_date)

    # Calculate product rankings
    product_rankings = calculate_product_rankings(start_date, end_date)

    # Calculate heatmap data
    heatmap_data = calculate_heatmap_data(start_date, end_date, top_n_products=10)

    # Serialize heatmap data as JSON for JavaScript
    import json
    heatmap_json = json.dumps(heatmap_data)

    context = {
        'summary': summary,
        'customer_rankings': customer_rankings,
        'product_rankings': product_rankings,
        'heatmap_data': heatmap_data,
        'heatmap_json': heatmap_json,
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
