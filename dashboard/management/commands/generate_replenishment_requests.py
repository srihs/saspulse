"""
Generate automated replenishment requests based on AI forecast vs current stock

This command:
1. Gets the latest forecasts for school products
2. Compares forecasted demand vs current stock levels
3. Identifies stock gaps (where stock < forecast)
4. Creates replenishment requests for store managers to review
5. Assigns urgency based on days of stock remaining
"""

import pandas as pd
from datetime import datetime, date
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone
from dashboard.models import SalesForecast, ReplenishmentRequest
from cin7.models import Product, Stock, Branch
import warnings
warnings.filterwarnings('ignore')


class Command(BaseCommand):
    help = 'Generate replenishment requests based on AI forecasts vs stock levels'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-gap',
            type=int,
            default=10,
            help='Minimum stock gap to create request (default: 10 units)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate without creating requests'
        )
        parser.add_argument(
            '--week',
            type=int,
            default=None,
            help='Week number (default: current week)'
        )

    def handle(self, *args, **options):
        min_gap = options['min_gap']
        dry_run = options['dry_run']
        week_number = options['week'] or datetime.now().isocalendar()[1]
        year = datetime.now().year

        if dry_run:
            self.stdout.write(self.style.WARNING('=' * 80))
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No requests will be created'))
            self.stdout.write(self.style.WARNING('=' * 80))

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('REPLENISHMENT REQUEST GENERATOR'))
        self.stdout.write(self.style.SUCCESS(f'Week {week_number}, {year} - Min Gap: {min_gap} units'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        # Get latest forecasts by product
        self.stdout.write('\nFetching latest product forecasts...')
        product_forecasts = self.get_product_forecasts()

        if product_forecasts.empty:
            self.stdout.write(self.style.WARNING('No product forecasts found. Run generate_sales_forecasts first.'))
            return

        self.stdout.write(f'Found {len(product_forecasts)} product forecasts')

        # Get current stock levels for all products
        self.stdout.write('\nFetching current stock levels...')
        stock_levels = self.get_stock_levels()

        if stock_levels.empty:
            self.stdout.write(self.style.WARNING('No stock data found.'))
            return

        self.stdout.write(f'Found stock data for {len(stock_levels)} product-branch combinations')

        # Calculate stock gaps
        self.stdout.write('\nAnalyzing stock gaps...')
        gaps = self.calculate_stock_gaps(product_forecasts, stock_levels, min_gap)

        self.stdout.write(f'Identified {len(gaps)} products needing replenishment')

        # Create replenishment requests
        if not dry_run:
            self.stdout.write('\nCreating replenishment requests...')
            created = self.create_requests(gaps, week_number, year)
            self.stdout.write(self.style.SUCCESS(f'\n✓ Created {created} replenishment requests'))
        else:
            self.stdout.write(self.style.WARNING(f'\n[DRY RUN] Would create {len(gaps)} replenishment requests'))
            self.show_sample_requests(gaps)

    def get_product_forecasts(self):
        """Get latest 30-day forecasts at product level"""

        # Check if we have product-level forecasts
        product_level_forecasts = SalesForecast.objects.filter(
            aggregation_level='product',
            horizon='30d'
        ).order_by('entity_name', '-forecast_date')

        if product_level_forecasts.exists():
            # Use product-level forecasts
            data = []
            for forecast in product_level_forecasts:
                total_forecast = sum([day.get('quantity', 0) for day in forecast.forecast_data.values()])
                data.append({
                    'product_name': forecast.entity_name,
                    'forecasted_demand_30d': total_forecast,
                    'ai_confidence': forecast.accuracy_score or 50.0,
                    'forecast_id': forecast.id
                })

            df = pd.DataFrame(data)
            # Remove duplicates, keeping latest
            df = df.drop_duplicates(subset=['product_name'], keep='first')
            return df

        # If no product forecasts, aggregate from school forecasts
        self.stdout.write(self.style.WARNING('  No product-level forecasts found, aggregating from school forecasts...'))

        query = """
        SELECT
            p.name as product_name,
            p.id as product_id,
            p.sub_category as school_name,
            SUM(li.qty) as total_sales
        FROM cin7_sync_salesorderlineitem li
        JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
        JOIN cin7_sync_product p ON p.id = li.product_id
        WHERE p.category_name LIKE '%%Shop'
          AND so.stage = 'Dispatched'
          AND so.cin7_created_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
        GROUP BY p.name, p.id, p.sub_category
        """

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            results = cursor.fetchall()

        df = pd.DataFrame(results, columns=columns)

        if df.empty:
            return pd.DataFrame()

        # Convert to float to avoid Decimal issues
        df['total_sales'] = df['total_sales'].astype(float)

        # Get school forecasts
        school_forecasts = SalesForecast.objects.filter(
            aggregation_level='school',
            horizon='30d'
        ).order_by('entity_name', '-forecast_date')

        school_forecast_map = {}
        for forecast in school_forecasts:
            if forecast.entity_name not in school_forecast_map:
                total_forecast = sum([day.get('quantity', 0) for day in forecast.forecast_data.values()])
                school_forecast_map[forecast.entity_name] = {
                    'total': total_forecast,
                    'confidence': forecast.accuracy_score or 50.0,
                    'id': forecast.id
                }

        # Calculate product forecasts based on historical share of school sales
        product_forecasts = []
        for product_name in df['product_name'].unique():
            product_data = df[df['product_name'] == product_name]

            # Calculate this product's share of each school's sales
            total_demand = 0
            weighted_confidence = 0
            forecast_ids = []

            for _, row in product_data.iterrows():
                school = row['school_name']
                if school in school_forecast_map:
                    school_total = school_forecast_map[school]['total']
                    school_sales = product_data[product_data['school_name'] == school]['total_sales'].sum()
                    total_school_sales = df[df['school_name'] == school]['total_sales'].sum()

                    if total_school_sales > 0:
                        share = school_sales / total_school_sales
                        product_demand = school_total * share
                        total_demand += product_demand
                        weighted_confidence += school_forecast_map[school]['confidence'] * product_demand
                        forecast_ids.append(school_forecast_map[school]['id'])

            avg_confidence = weighted_confidence / total_demand if total_demand > 0 else 50.0

            product_forecasts.append({
                'product_name': product_name,
                'forecasted_demand_30d': total_demand,
                'ai_confidence': avg_confidence,
                'forecast_id': forecast_ids[0] if forecast_ids else None
            })

        return pd.DataFrame(product_forecasts)

    def get_stock_levels(self):
        """Get current stock levels for all products at all branches"""

        query = """
        SELECT
            p.name as product_name,
            p.id as product_id,
            p.sub_category as school_name,
            b.company as branch_name,
            b.id as branch_id,
            s.available as available_stock,
            s.stock_on_hand as stock_on_hand
        FROM cin7_sync_stock s
        JOIN cin7_sync_product p ON p.id = s.product_id
        JOIN cin7_sync_branch b ON b.id = s.branch_id
        WHERE p.category_name LIKE '%%Shop'
          AND s.updated_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        """

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            results = cursor.fetchall()

        df = pd.DataFrame(results, columns=columns)

        if not df.empty:
            df['available_stock'] = df['available_stock'].fillna(0).astype(float)
            df['stock_on_hand'] = df['stock_on_hand'].fillna(0).astype(float)

        return df

    def calculate_stock_gaps(self, forecasts, stock_levels, min_gap):
        """Calculate stock gaps where forecast > current stock"""

        gaps = []

        for _, forecast_row in forecasts.iterrows():
            product_name = forecast_row['product_name']
            forecasted_demand = forecast_row['forecasted_demand_30d']

            # Get stock at each branch for this product
            product_stock = stock_levels[stock_levels['product_name'] == product_name]

            for _, stock_row in product_stock.iterrows():
                current_stock = stock_row['available_stock']
                gap = forecasted_demand - current_stock

                if gap >= min_gap:
                    # Calculate urgency based on days of stock
                    daily_demand = forecasted_demand / 30
                    days_of_stock = current_stock / daily_demand if daily_demand > 0 else 999

                    if days_of_stock < 7:
                        urgency = 'critical'
                    elif days_of_stock < 15:
                        urgency = 'high'
                    elif days_of_stock < 30:
                        urgency = 'medium'
                    else:
                        urgency = 'low'

                    gaps.append({
                        'product_name': product_name,
                        'product_id': stock_row['product_id'],
                        'branch_name': stock_row['branch_name'],
                        'branch_id': stock_row['branch_id'],
                        'school_name': stock_row['school_name'],
                        'current_stock': current_stock,
                        'forecasted_demand': forecasted_demand,
                        'gap': gap,
                        'suggested_quantity': gap,
                        'urgency': urgency,
                        'days_of_stock': days_of_stock,
                        'ai_confidence': forecast_row['ai_confidence'],
                        'forecast_id': forecast_row['forecast_id']
                    })

        return pd.DataFrame(gaps)

    def create_requests(self, gaps, week_number, year):
        """Create ReplenishmentRequest records using raw SQL to avoid ORM issues"""

        created_count = 0

        insert_query = """
        INSERT INTO dashboard_replenishmentrequest (
            request_id, week_number, year, product_id, branch_id, school_name,
            current_stock, forecasted_demand_30d, stock_gap, suggested_quantity,
            urgency, ai_confidence, forecast_id, status,
            created_at, updated_at,
            store_approved_quantity, store_manager_comment, store_manager_id, store_approved_at,
            dp_approved_quantity, dp_team_comment, dp_approver_id, dp_approved_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(),
            NULL, '', NULL, NULL, NULL, '', NULL, NULL
        )
        """

        with connection.cursor() as cursor:
            for idx, row in gaps.iterrows():
                request_id = f"RR-{year}-W{week_number:02d}-{created_count + 1}"

                try:
                    cursor.execute(insert_query, [
                        request_id,
                        week_number,
                        year,
                        row['product_id'],
                        row['branch_id'],
                        row['school_name'],
                        float(row['current_stock']),
                        float(row['forecasted_demand']),
                        float(row['gap']),
                        float(row['suggested_quantity']),
                        row['urgency'],
                        float(row['ai_confidence']),
                        int(row['forecast_id']) if row['forecast_id'] else None,
                        'pending'
                    ])

                    created_count += 1

                    if created_count % 100 == 0:
                        self.stdout.write(f'  Created {created_count} requests...')

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  Error creating request for {row["product_name"]}: {e}'))
                    continue

        return created_count

    def show_sample_requests(self, gaps):
        """Show sample requests that would be created"""

        sample_size = min(20, len(gaps))
        samples = gaps.sort_values('gap', ascending=False).head(sample_size)

        self.stdout.write('\nSample requests (top 20 by gap):')
        self.stdout.write('=' * 80)

        for idx, row in samples.iterrows():
            request_id = f"RR-{datetime.now().year}-W{datetime.now().isocalendar()[1]:02d}-{idx + 1}"
            self.stdout.write(
                f"[DRY RUN] Would create: {request_id} - {row['product_name']} @ {row['branch_name']} - "
                f"Gap: {row['gap']:.0f}, Suggested: {row['suggested_quantity']:.0f}, "
                f"Urgency: {row['urgency'].upper()}"
            )
