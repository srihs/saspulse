"""
Generate Simple Monthly Sales Forecasts

No Prophet, No AI - Just Smart Averages based on historical monthly patterns.

Algorithm:
1. Get historical sales for each month (last 3 years)
2. Calculate simple average per month
3. Apply growth trend (year-over-year change)
4. Identify peak/off seasons
5. Generate business recommendations

This approach works better for seasonal school uniform sales than complex ML models.
"""

import statistics
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum, Count
from django.utils import timezone

from django.db import connection

from dashboard.models import SalesForecastBase
from cin7.models import SalesOrderLineItem, ProductOption, Product


class Command(BaseCommand):
    help = 'Generate simple monthly forecasts using historical averages (no Prophet/ML)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--level',
            type=str,
            default='product',
            choices=['product', 'school'],
            help='Aggregation level for forecasts'
        )
        parser.add_argument(
            '--years',
            type=int,
            default=3,
            help='Number of historical years to use (default: 3)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regeneration of all forecasts'
        )

    def handle(self, *args, **options):
        level = options['level']
        years = options['years']
        force = options['force']

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("SIMPLE MONTHLY FORECAST GENERATION"))
        self.stdout.write(self.style.SUCCESS("No Prophet • No AI • Just Smart Averages"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"\nLevel: {level.upper()}")
        self.stdout.write(f"Historical years: {years}")
        self.stdout.write(f"Force regeneration: {force}\n")

        if level == 'product':
            self.generate_product_forecasts(years, force)
        elif level == 'school':
            self.generate_school_forecasts(years, force)

    def generate_product_forecasts(self, years, force):
        """Generate monthly forecasts for each product"""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("PRODUCT-LEVEL FORECASTS")
        self.stdout.write("=" * 80)

        # Get all products with historical sales using raw SQL
        query = """
        SELECT DISTINCT li.code
        FROM cin7_sync_salesorderlineitem li
        JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
        JOIN cin7_sync_product p ON p.id = li.product_id
        WHERE (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
          AND p.category_name NOT IN ('Shop', 'Store')
          AND so.stage = 'Dispatched'
          AND so.invoice_date IS NOT NULL
          AND so.invoice_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
          AND li.code IS NOT NULL
          AND li.code != ''
        ORDER BY li.code
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [365 * years])
            products = [row[0] for row in cursor.fetchall()]

        total = len(products)
        self.stdout.write(f"\nFound {total} active products\n")

        generated_count = 0
        skipped_count = 0
        error_count = 0

        for idx, product_code in enumerate(products, 1):
            try:
                # Get historical sales (will return empty if discontinued or insufficient data)
                sales_data, skip_reason = self.get_historical_sales_product(product_code, years)

                if not sales_data:
                    if idx % 100 == 0:  # Only show every 100th skip to reduce noise
                        self.stdout.write(
                            self.style.WARNING(f"  [{idx}/{total}] Skipping {product_code}: {skip_reason}")
                        )
                    skipped_count += 1
                    continue

                # Calculate monthly breakdown
                monthly_breakdown = self.calculate_monthly_breakdown(sales_data, years)

                # Identify seasonal patterns
                seasonal_profile = self.identify_seasonal_profile(monthly_breakdown)

                # Calculate growth metrics
                growth_metrics = self.calculate_growth_metrics(sales_data)

                # Save forecast
                forecast_id = f"simple-product-{product_code}-{date.today().isoformat()}"

                # Calculate forecast_valid_until (24 months from today)
                forecast_valid_until = date.today() + relativedelta(months=24)

                SalesForecastBase.objects.update_or_create(
                    entity_name=product_code,
                    aggregation_level='product',
                    forecast_date=date.today(),
                    defaults={
                        'forecast_id': forecast_id,
                        'model_type': 'statistical',
                        'monthly_breakdown': monthly_breakdown,
                        'seasonal_profile': seasonal_profile,
                        'growth_metrics': growth_metrics,
                        'training_data_start': date.today() - timedelta(days=365 * years),
                        'training_data_end': date.today(),
                        'forecast_valid_until': forecast_valid_until,  # NEW: 24-month validity
                        'model_params': {
                            'method': 'simple_monthly_average_24month',  # Updated method name
                            'years_used': years,
                            'forecast_horizon_months': 24,  # NEW: Track forecast horizon
                            'generated_at': datetime.now().isoformat()
                        }
                    }
                )

                generated_count += 1

                if idx % 50 == 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Progress: {idx}/{total} ({idx/total*100:.1f}%) - Generated: {generated_count}, Skipped: {skipped_count}"
                        )
                    )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"  [{idx}/{total}] Error processing {product_code}: {str(e)}")
                )

        # Final summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("GENERATION COMPLETE"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"✓ Generated: {generated_count}")
        self.stdout.write(f"⏭ Skipped: {skipped_count}")
        self.stdout.write(f"✗ Errors: {error_count}")
        self.stdout.write("=" * 80)

    def generate_school_forecasts(self, years, force):
        """Generate monthly forecasts for each school"""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("SCHOOL-LEVEL FORECASTS")
        self.stdout.write("=" * 80)

        # Get all schools with sales using raw SQL
        query = """
        SELECT DISTINCT p.sub_category
        FROM cin7_sync_product p
        JOIN cin7_sync_salesorderlineitem li ON li.product_id = p.id
        JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
        WHERE (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
          AND p.category_name NOT IN ('Shop', 'Store')
          AND p.category_name NOT LIKE 'Wholesale%%'
          AND p.sub_category IS NOT NULL
          AND p.sub_category != ''
          AND so.stage = 'Dispatched'
          AND so.invoice_date IS NOT NULL
          AND so.invoice_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        ORDER BY p.sub_category
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [365 * years])
            schools = [row[0] for row in cursor.fetchall()]

        total = len(schools)
        self.stdout.write(f"\nFound {total} schools\n")

        generated_count = 0
        skipped_count = 0

        for idx, school in enumerate(schools, 1):
            try:
                # Get historical sales for this school
                sales_data = self.get_historical_sales_school(school, years)

                if not sales_data:
                    self.stdout.write(
                        self.style.WARNING(f"  [{idx}/{total}] Skipping {school}: No sales history")
                    )
                    skipped_count += 1
                    continue

                # Calculate monthly breakdown
                monthly_breakdown = self.calculate_monthly_breakdown(sales_data, years)

                # Identify seasonal patterns
                seasonal_profile = self.identify_seasonal_profile(monthly_breakdown)

                # Calculate growth metrics
                growth_metrics = self.calculate_growth_metrics(sales_data)

                # Save forecast
                forecast_id = f"simple-school-{school}-{date.today().isoformat()}"

                # Calculate forecast_valid_until (24 months from today)
                forecast_valid_until = date.today() + relativedelta(months=24)

                SalesForecastBase.objects.update_or_create(
                    entity_name=school,
                    aggregation_level='school',
                    forecast_date=date.today(),
                    defaults={
                        'forecast_id': forecast_id,
                        'model_type': 'statistical',
                        'monthly_breakdown': monthly_breakdown,
                        'seasonal_profile': seasonal_profile,
                        'growth_metrics': growth_metrics,
                        'training_data_start': date.today() - timedelta(days=365 * years),
                        'training_data_end': date.today(),
                        'forecast_valid_until': forecast_valid_until,  # NEW: 24-month validity
                        'model_params': {
                            'method': 'simple_monthly_average_24month',  # Updated method name
                            'years_used': years,
                            'forecast_horizon_months': 24,  # NEW: Track forecast horizon
                            'generated_at': datetime.now().isoformat()
                        }
                    }
                )

                generated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  [{idx}/{total}] ✓ {school}: {seasonal_profile.get('annual_forecast', 0):.0f} units/year")
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  [{idx}/{total}] Error processing {school}: {str(e)}")
                )

        # Final summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("GENERATION COMPLETE"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"✓ Generated: {generated_count}")
        self.stdout.write(f"⏭ Skipped: {skipped_count}")
        self.stdout.write("=" * 80)

    def get_historical_sales_product(self, product_code, years):
        """
        Get historical sales grouped by year and month for a product

        Returns:
            tuple: (sales_dict, skip_reason)
            - sales_dict: {(year, month): quantity} or empty dict if should skip
            - skip_reason: String explaining why product was skipped (if applicable)
        """
        query = """
        SELECT
            YEAR(so.invoice_date) as year,
            MONTH(so.invoice_date) as month,
            SUM(li.qty) as quantity,
            DATE(MAX(so.invoice_date)) as last_sale_date
        FROM cin7_sync_salesorderlineitem li
        JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
        JOIN cin7_sync_product p ON p.id = li.product_id
        WHERE li.code = %s
          AND (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
          AND p.category_name NOT IN ('Shop', 'Store')
          AND so.stage = 'Dispatched'
          AND so.invoice_date IS NOT NULL
          AND so.invoice_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY YEAR(so.invoice_date), MONTH(so.invoice_date)
        ORDER BY year, month
        """

        sales_dict = defaultdict(float)
        last_sale_date = None

        with connection.cursor() as cursor:
            cursor.execute(query, [product_code, 365 * years])
            rows = cursor.fetchall()

            if not rows:
                return {}, "No sales history"

            for row in rows:
                year, month, quantity, sale_date = row
                sales_dict[(year, month)] = float(quantity)
                if last_sale_date is None or sale_date > last_sale_date:
                    last_sale_date = sale_date

        # Check if product is discontinued (no sales in last 2 years)
        if last_sale_date:
            # Convert datetime to date if needed
            if isinstance(last_sale_date, datetime):
                last_sale_date = last_sale_date.date()

            days_since_last_sale = (date.today() - last_sale_date).days
            if days_since_last_sale > 730:  # 2 years
                return {}, f"Discontinued ({days_since_last_sale} days since last sale)"

        # Check if we have enough data (at least 6 months of sales)
        if len(sales_dict) < 6:
            return {}, f"Insufficient data (only {len(sales_dict)} months)"

        return sales_dict, None

    def get_historical_sales_school(self, school_name, years):
        """Get historical sales grouped by year and month for a school"""
        query = """
        SELECT
            YEAR(so.invoice_date) as year,
            MONTH(so.invoice_date) as month,
            SUM(li.qty) as quantity
        FROM cin7_sync_salesorderlineitem li
        JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
        JOIN cin7_sync_product p ON p.id = li.product_id
        WHERE p.sub_category = %s
          AND (p.category_name LIKE '%%Shop' OR p.category_name LIKE '%%Store')
          AND p.category_name NOT IN ('Shop', 'Store')
          AND p.category_name NOT LIKE 'Wholesale%%'
          AND so.stage = 'Dispatched'
          AND so.invoice_date IS NOT NULL
          AND so.invoice_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY YEAR(so.invoice_date), MONTH(so.invoice_date)
        ORDER BY year, month
        """

        sales_dict = defaultdict(float)

        with connection.cursor() as cursor:
            cursor.execute(query, [school_name, 365 * years])
            for row in cursor.fetchall():
                year, month, quantity = row
                sales_dict[(year, month)] = float(quantity)

        return sales_dict

    def calculate_monthly_breakdown(self, sales_data, years):
        """
        Calculate forecast for each month using simple averaging

        UPDATED FOR 2-YEAR ROLLING FORECAST:
        - Generates forecasts for 24 months ahead (not just 12)
        - Uses forecasted values as baseline when actual sales don't exist
        - Applies seasonal patterns and growth trends

        Returns:
            {
                '2027-01': {
                    'quantity': 59,
                    'avg_last_3_years': 51.7,
                    'min': 45,
                    'max': 58,
                    'confidence': 'high',
                    'historical_sales': [45, 52, 58],
                    'baseline_source': 'actual'
                },
                ...
            }
        """
        monthly_breakdown = {}
        current_year = date.today().year
        current_month = date.today().month

        # Generate forecasts for 24 months ahead (current month + 24 months)
        for month_offset in range(1, 25):  # Changed from 12 to 24 months
            target_date = date.today() + relativedelta(months=month_offset)
            target_year = target_date.year
            target_month = target_date.month
            month_key = f"{target_year}-{target_month:02d}"

            # Try to get baseline data (actual or forecasted)
            baseline_qty, baseline_source = self.get_baseline_for_month(
                sales_data, target_year, target_month, years
            )

            if baseline_qty == 0:
                # No historical sales in this month - likely off-season
                monthly_breakdown[month_key] = {
                    'quantity': 0,
                    'avg_last_3_years': 0,
                    'min': 0,
                    'max': 0,
                    'confidence': 'high',  # High confidence it's off-season
                    'historical_sales': [],
                    'is_peak_month': False,
                    'baseline_source': baseline_source
                }
                continue

            # Get historical sales for this month across all years
            month_sales = []
            for year in range(current_year - years, current_year):
                quantity = sales_data.get((year, target_month), 0)
                if quantity > 0:
                    month_sales.append(quantity)

            if not month_sales:
                # Use baseline directly if no historical pattern
                monthly_breakdown[month_key] = {
                    'quantity': round(baseline_qty, 1),
                    'avg_last_3_years': round(baseline_qty, 1),
                    'min': round(baseline_qty, 1),
                    'max': round(baseline_qty, 1),
                    'confidence': 'medium',
                    'historical_sales': [],
                    'is_peak_month': False,
                    'baseline_source': baseline_source
                }
            else:
                # Calculate average and apply to baseline
                avg = statistics.mean(month_sales)
                min_val = min(month_sales)
                max_val = max(month_sales)

                # Apply growth adjustment if we have multiple years
                if len(month_sales) > 1:
                    growth_rate = (month_sales[-1] - month_sales[0]) / (month_sales[0] if month_sales[0] > 0 else 1)

                    # For future years, compound the growth
                    years_ahead = target_year - current_year
                    growth_multiplier = (1 + (growth_rate / (len(month_sales) - 1))) ** years_ahead

                    # Apply growth to baseline
                    adjusted = baseline_qty * growth_multiplier
                else:
                    adjusted = baseline_qty

                # Calculate confidence based on variance and baseline source
                confidence = self.calculate_confidence_with_source(month_sales, baseline_source, month_offset)

                monthly_breakdown[month_key] = {
                    'quantity': round(adjusted, 1),
                    'avg_last_3_years': round(avg, 1),
                    'min': round(min_val, 1),
                    'max': round(max_val, 1),
                    'confidence': confidence,
                    'historical_sales': [round(s, 1) for s in month_sales],
                    'is_peak_month': False,  # Will be set by seasonal profile
                    'baseline_source': baseline_source,
                    'baseline_value': round(baseline_qty, 1)
                }

        return monthly_breakdown

    def get_baseline_for_month(self, sales_data, target_year, target_month, years):
        """
        Get baseline sales for a month - uses actual if available, otherwise forecasted

        Args:
            sales_data: Historical sales data dict {(year, month): quantity}
            target_year: Year to forecast
            target_month: Month to forecast (1-12)
            years: Number of historical years

        Returns:
            Tuple of (baseline_quantity, source) where source is 'actual', 'forecast', or 'historical'
        """
        # Try to get actual sales for this year/month
        actual_sales = sales_data.get((target_year, target_month), 0)
        if actual_sales > 0:
            return actual_sales, 'actual'

        # No actual sales - try previous year's forecast
        # For now, use same month from previous year as proxy
        # (In future, this could query the monthly_breakdown from last year's forecast)
        previous_year_sales = sales_data.get((target_year - 1, target_month), 0)
        if previous_year_sales > 0:
            return previous_year_sales, 'forecast_proxy'

        # No previous year - get average from all available years for this month
        month_sales = []
        current_year = date.today().year
        for year in range(current_year - years, current_year):
            quantity = sales_data.get((year, target_month), 0)
            if quantity > 0:
                month_sales.append(quantity)

        if month_sales:
            return statistics.mean(month_sales), 'historical'

        return 0.0, 'none'

    def calculate_confidence_with_source(self, values, baseline_source, months_ahead):
        """
        Calculate confidence level based on variance and baseline source

        Args:
            values: Historical values list
            baseline_source: Source of baseline ('actual', 'forecast', 'historical', etc.)
            months_ahead: Number of months into the future

        Returns: 'high', 'medium', or 'low'
        """
        if baseline_source == 'actual':
            base_confidence = 'high'
        elif baseline_source == 'forecast_proxy':
            base_confidence = 'medium'
        else:
            base_confidence = 'low'

        # Reduce confidence for far-future forecasts
        if months_ahead > 18:
            if base_confidence == 'high':
                base_confidence = 'medium'
            elif base_confidence == 'medium':
                base_confidence = 'low'
        elif months_ahead > 12:
            if base_confidence == 'high' and len(values) < 2:
                base_confidence = 'medium'

        return base_confidence

    def calculate_monthly_breakdown_old(self, sales_data, years):
        """
        OLD VERSION - KEEPING FOR REFERENCE
        Calculate forecast for each month using simple averaging

        Returns:
            {
                '2027-01': {
                    'quantity': 59,
                    'avg_last_3_years': 51.7,
                    'min': 45,
                    'max': 58,
                    'confidence': 'high',
                    'historical_sales': [45, 52, 58]
                },
                ...
            }
        """
        monthly_breakdown = {}
        next_year = date.today().year + 1

        for month in range(1, 13):
            # Get historical sales for this month across all years
            month_sales = []
            for year in range(date.today().year - years, date.today().year):
                quantity = sales_data.get((year, month), 0)
                if quantity > 0:
                    month_sales.append(quantity)

            if not month_sales:
                # No historical sales in this month - likely off-season
                monthly_breakdown[f"{next_year}-{month:02d}"] = {
                    'quantity': 0,
                    'avg_last_3_years': 0,
                    'min': 0,
                    'max': 0,
                    'confidence': 'high',  # High confidence it's off-season
                    'historical_sales': [],
                    'is_peak_month': False
                }
            else:
                # Calculate average
                avg = statistics.mean(month_sales)
                min_val = min(month_sales)
                max_val = max(month_sales)

                # Simple growth adjustment (if we have multiple years)
                if len(month_sales) > 1:
                    # Year-over-year growth rate
                    growth_rate = (month_sales[-1] - month_sales[0]) / (month_sales[0] if month_sales[0] > 0 else 1)
                    adjusted = avg * (1 + (growth_rate / (len(month_sales) - 1)))
                else:
                    adjusted = avg

                # Calculate confidence based on variance
                confidence = self.calculate_confidence(month_sales)

                monthly_breakdown[f"{next_year}-{month:02d}"] = {
                    'quantity': round(adjusted, 1),
                    'avg_last_3_years': round(avg, 1),
                    'min': round(min_val, 1),
                    'max': round(max_val, 1),
                    'confidence': confidence,
                    'historical_sales': [round(s, 1) for s in month_sales],
                    'is_peak_month': False  # Will be set by seasonal profile
                }

        return monthly_breakdown

    def calculate_confidence(self, values):
        """
        Calculate confidence level based on variance in historical data

        Returns: 'high', 'medium', or 'low'
        """
        if len(values) < 2:
            return 'low'

        try:
            mean_val = statistics.mean(values)
            if mean_val == 0:
                return 'high'  # Consistently zero

            stdev = statistics.stdev(values)
            coefficient_of_variation = stdev / mean_val

            if coefficient_of_variation < 0.2:  # Low variance
                return 'high'
            elif coefficient_of_variation < 0.5:  # Medium variance
                return 'medium'
            else:  # High variance
                return 'low'
        except:
            return 'medium'

    def identify_seasonal_profile(self, monthly_breakdown):
        """
        Identify peak, medium, low, and off-season months

        Returns:
            {
                'peak_months': [1, 2, 11, 12],
                'medium_months': [3, 10],
                'low_months': [4, 5, 9],
                'zero_months': [6, 7, 8],
                'peak_season_label': 'Back-to-School (Jan-Feb, Nov-Dec)',
                'annual_forecast': 450
            }
        """
        # Extract quantities by month
        month_quantities = {}
        annual_total = 0

        for month_key, data in monthly_breakdown.items():
            month = int(month_key.split('-')[1])
            quantity = data['quantity']
            month_quantities[month] = quantity
            annual_total += quantity

        # Separate zero and non-zero months
        zero_months = [m for m, q in month_quantities.items() if q == 0]
        active_months = {m: q for m, q in month_quantities.items() if q > 0}

        if not active_months:
            return {
                'peak_months': [],
                'medium_months': [],
                'low_months': [],
                'zero_months': list(range(1, 13)),
                'peak_season_label': 'No sales',
                'annual_forecast': 0
            }

        # Sort active months by quantity
        sorted_months = sorted(active_months.items(), key=lambda x: x[1], reverse=True)

        # Classify into peak (top 25%), medium (middle 50%), low (bottom 25%)
        num_active = len(sorted_months)
        peak_count = max(1, num_active // 4)
        low_count = max(1, num_active // 4)

        peak_months = [m for m, q in sorted_months[:peak_count]]
        low_months = [m for m, q in sorted_months[-low_count:]]
        medium_months = [m for m, q in sorted_months[peak_count:-low_count] if low_count > 0] if num_active > 2 else []

        # Update monthly_breakdown with peak flags
        for month_key, data in monthly_breakdown.items():
            month = int(month_key.split('-')[1])
            data['is_peak_month'] = month in peak_months

        # Generate peak season label
        peak_season_label = self.generate_season_label(peak_months)

        # Calculate peak percentage
        peak_total = sum(month_quantities.get(m, 0) for m in peak_months)
        peak_percentage = int((peak_total / annual_total * 100) if annual_total > 0 else 0)

        return {
            'peak_months': sorted(peak_months),
            'medium_months': sorted(medium_months),
            'low_months': sorted(low_months),
            'zero_months': sorted(zero_months),
            'peak_season_label': peak_season_label,
            'annual_forecast': round(annual_total, 1),
            'peak_percentage': peak_percentage
        }

    def generate_season_label(self, peak_months):
        """Generate a friendly label for peak season"""
        if not peak_months:
            return "No peak season"

        month_names = {
            1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
            7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
        }

        # Check for common school seasons
        if set(peak_months) & {1, 2}:
            return "Back-to-School (Jan-Feb)"
        elif set(peak_months) & {11, 12}:
            return "End-of-Year Rush (Nov-Dec)"
        else:
            month_labels = [month_names[m] for m in sorted(peak_months)]
            return f"Peak Season ({', '.join(month_labels)})"

    def calculate_growth_metrics(self, sales_data):
        """
        Calculate year-over-year growth trend

        Returns:
            {
                'direction': 'growth' | 'decline' | 'stable',
                'annual_rate': 14.5,
                'trend_strength': 'strong' | 'moderate' | 'weak',
                'last_year_total': 420,
                'forecast_year_total': 480
            }
        """
        # Calculate annual totals
        annual_totals = defaultdict(float)
        for (year, month), quantity in sales_data.items():
            annual_totals[year] += quantity

        if len(annual_totals) < 2:
            return {
                'direction': 'stable',
                'annual_rate': 0,
                'trend_strength': 'unknown',
                'last_year_total': sum(annual_totals.values()),
                'forecast_year_total': sum(annual_totals.values())
            }

        # Get sorted years
        years = sorted(annual_totals.keys())
        first_year_total = annual_totals[years[0]]
        last_year_total = annual_totals[years[-1]]

        # Calculate annual growth rate
        if first_year_total > 0:
            total_growth = (last_year_total - first_year_total) / first_year_total
            num_years = len(years) - 1
            annual_rate = (total_growth / num_years) * 100  # Percentage
        else:
            annual_rate = 0

        # Determine direction
        if abs(annual_rate) < 5:
            direction = 'stable'
        elif annual_rate > 0:
            direction = 'growth'
        else:
            direction = 'decline'

        # Determine strength
        if abs(annual_rate) > 20:
            strength = 'strong'
        elif abs(annual_rate) > 10:
            strength = 'moderate'
        else:
            strength = 'weak'

        # Forecast next year total
        forecast_year_total = last_year_total * (1 + (annual_rate / 100))

        return {
            'direction': direction,
            'annual_rate': round(annual_rate, 1),
            'trend_strength': strength,
            'last_year_total': round(last_year_total, 1),
            'forecast_year_total': round(forecast_year_total, 1)
        }
