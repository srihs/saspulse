"""
Generate 365-day base sales forecasts using Statistical + AI/ML models

This management command generates ONE 365-day forecast per entity, which can then
be queried for any custom date range dynamically. This replaces the need to store
multiple horizon-based forecasts (30d, 90d, 180d, 365d).

Aggregation levels:
- By School
- By Product
- By Shop Location
- By Category

Benefits:
- 75% storage reduction (one forecast instead of four)
- Query ANY date range (7d, 45d, 91d, 200d) dynamically
- Simplified maintenance and regeneration
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
from dashboard.models import SalesForecastBase, ForecastSchedule
from cin7.models import Product, SalesOrderLineItem, SalesOrder
import warnings
warnings.filterwarnings('ignore')

# ML imports
try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    STATS_AVAILABLE = True
except ImportError as e:
    STATS_AVAILABLE = False
    print(f"Warning: Statsmodels not available: {e}")

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    print(f"Warning: Scikit-learn not available: {e}")

# Try XGBoost but don't fail if not available
try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except Exception as e:
    XGB_AVAILABLE = False
    print(f"Warning: XGBoost not available: {e}")

# Try Prophet for better time series forecasting
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except Exception as e:
    PROPHET_AVAILABLE = False
    print(f"Warning: Prophet not available: {e}")


class Command(BaseCommand):
    help = 'Generate 365-day base sales forecasts (one forecast per entity, query any date range)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--level',
            type=str,
            choices=['school', 'product', 'shop', 'category', 'all'],
            default='all',
            help='Aggregation level (default: all)'
        )
        parser.add_argument(
            '--model',
            type=str,
            choices=['statistical', 'ml', 'hybrid'],
            default='hybrid',
            help='Model type (default: hybrid)'
        )
        parser.add_argument(
            '--min-sales',
            type=int,
            default=10,
            help='Minimum sales to generate forecast (default: 10)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate forecasts even if they already exist'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of forecasts to generate (for testing)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('365-DAY BASE FORECASTING ENGINE - Statistical + AI/ML Models'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.WARNING('Strategy: Generate ONE 365-day forecast, extract any date range dynamically'))
        self.stdout.write(self.style.WARNING('Benefits: 75% storage reduction, infinite flexibility, simplified maintenance'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        level = options['level']
        model_type = options['model']
        min_sales = options['min_sales']
        force = options['force']
        limit = options['limit']

        # Define levels to process
        levels = ['school', 'product', 'shop'] if level == 'all' else [level]

        for l in levels:
            self.stdout.write(f"\n{self.style.WARNING(f'Processing: {l.upper()} - 365-day base forecasts')}")
            self.generate_forecasts(l, model_type, min_sales, force, limit)

        self.stdout.write(self.style.SUCCESS('\n✓ 365-day base forecasting complete!'))

    def generate_forecasts(self, aggregation_level, model_type, min_sales, force, limit):
        """Generate 365-day base forecasts for a specific aggregation level"""

        # Get historical sales data
        sales_data = self.get_historical_sales(aggregation_level)

        if sales_data.empty:
            self.stdout.write(self.style.WARNING(f'  No sales data found for {aggregation_level}'))
            return

        forecast_count = 0
        skipped_count = 0
        error_count = 0
        horizon_days = 365  # Always generate 365-day forecasts

        entities = sales_data['entity_name'].unique()
        total_entities = len(entities)

        if limit:
            entities = entities[:limit]
            self.stdout.write(self.style.WARNING(f'  Limited to {limit} entities for testing'))

        self.stdout.write(f'  Found {total_entities} entities to process')
        start_time = datetime.now()

        for idx, entity_name in enumerate(entities):
            entity_data = sales_data[sales_data['entity_name'] == entity_name].copy()

            # Skip if insufficient sales
            if entity_data['quantity'].sum() < min_sales:
                skipped_count += 1
                continue

            # Check if forecast already exists
            if not force:
                existing = SalesForecastBase.objects.filter(
                    entity_name=entity_name,
                    aggregation_level=aggregation_level,
                    forecast_date=datetime.now().date()
                ).exists()

                if existing:
                    skipped_count += 1
                    continue

            # Prepare time series
            ts_data = self.prepare_time_series(entity_data)

            if len(ts_data) < 30:  # Need at least 30 days of history
                skipped_count += 1
                continue

            # Generate 365-day forecast
            try:
                if model_type == 'statistical':
                    forecast = self.forecast_statistical(ts_data, horizon_days)
                elif model_type == 'ml':
                    forecast = self.forecast_ml(ts_data, horizon_days)
                else:  # hybrid
                    forecast = self.forecast_hybrid(ts_data, horizon_days)

                if forecast is not None:
                    # Save forecast to SalesForecastBase
                    self.save_forecast(
                        entity_name=entity_name,
                        aggregation_level=aggregation_level,
                        model_type=model_type,
                        forecast_data=forecast,
                        training_data=ts_data
                    )
                    forecast_count += 1

                    # Update forecast schedule
                    self.update_forecast_schedule(entity_name, aggregation_level)

                    # Progress tracking
                    if (idx + 1) % 10 == 0 or idx == 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        rate = (idx + 1) / elapsed if elapsed > 0 else 0
                        remaining = (total_entities - idx - 1) / rate if rate > 0 else 0
                        eta_str = str(timedelta(seconds=int(remaining)))

                        self.stdout.write(
                            f'  Progress: {idx + 1}/{total_entities} '
                            f'({(idx + 1) / total_entities * 100:.1f}%) - '
                            f'Generated: {forecast_count}, Skipped: {skipped_count} - '
                            f'ETA: {eta_str}'
                        )
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f'  Error processing {entity_name}: {e}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'  ✓ Complete - Generated: {forecast_count}, '
                f'Skipped: {skipped_count}, Errors: {error_count}'
            )
        )

    def get_historical_sales(self, aggregation_level):
        """Get historical sales data aggregated by level"""

        # Query sales for school products
        query = """
        SELECT
            so.cin7_created_date as sale_date,
            {entity_field} as entity_name,
            SUM(li.qty) as quantity,
            SUM(li.line_total) as revenue,
            COUNT(DISTINCT so.id) as order_count
        FROM cin7_sync_salesorderlineitem li
        JOIN cin7_sync_salesorder so ON so.id = li.sales_order_id
        JOIN cin7_sync_product p ON p.id = li.product_id
        WHERE (p.category_name LIKE '%Shop' OR p.category_name = 'Wholesale Schools')
          AND so.stage = 'Dispatched'
          AND so.cin7_created_date IS NOT NULL
          AND so.cin7_created_date >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
        GROUP BY DATE(so.cin7_created_date), {entity_field}
        ORDER BY sale_date, entity_name
        """

        # Set entity field based on aggregation level
        entity_fields = {
            'school': 'p.sub_category',
            'product': 'li.code',  # Use SKU code to forecast each variation separately
            'shop': 'p.category_name',
            'category': 'p.category_name'
        }

        entity_field = entity_fields.get(aggregation_level, 'p.sub_category')
        query = query.format(entity_field=entity_field)

        # Execute query
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            results = cursor.fetchall()

        # Convert to DataFrame
        df = pd.DataFrame(results, columns=columns)

        if not df.empty:
            df['sale_date'] = pd.to_datetime(df['sale_date'])
            df['quantity'] = df['quantity'].astype(float)
            df['revenue'] = df['revenue'].fillna(0).astype(float)

        return df

    def prepare_time_series(self, entity_data):
        """Prepare time series data with proper date indexing"""

        # Convert sale_date to date only (remove time component)
        entity_data = entity_data.copy()
        entity_data['sale_date'] = pd.to_datetime(entity_data['sale_date']).dt.date
        entity_data['sale_date'] = pd.to_datetime(entity_data['sale_date'])

        # Aggregate by calendar date first
        daily_data = entity_data.groupby('sale_date').agg({
            'quantity': 'sum',
            'revenue': 'sum',
            'order_count': 'sum'
        })

        # Create complete date range
        min_date = daily_data.index.min()
        max_date = daily_data.index.max()
        date_range = pd.date_range(start=min_date, end=max_date, freq='D')

        # Reindex to include all days (fill missing with 0)
        ts = daily_data.reindex(date_range, fill_value=0)
        ts.index.name = 'date'

        return ts

    def forecast_statistical(self, ts_data, horizon_days):
        """Generate forecast using Prophet (Facebook's time series forecasting model)"""

        try:
            # Try Prophet first - it's excellent for intermittent demand and seasonality
            if PROPHET_AVAILABLE:
                try:
                    # Prepare data in Prophet format (ds = date, y = value)
                    prophet_df = pd.DataFrame({
                        'ds': ts_data.index,
                        'y': ts_data['quantity'].values
                    })

                    # Initialize Prophet with optimized parameters for school products
                    model = Prophet(
                        daily_seasonality=False,
                        weekly_seasonality=True,
                        yearly_seasonality=True,
                        seasonality_mode='multiplicative',  # Better for intermittent demand
                        changepoint_prior_scale=0.05,  # Lower = less flexible, more stable
                        interval_width=0.8,  # 80% confidence intervals
                        growth='linear'
                    )

                    # Suppress Prophet's verbose output
                    import logging
                    logging.getLogger('prophet').setLevel(logging.ERROR)
                    logging.getLogger('cmdstanpy').setLevel(logging.ERROR)

                    # Fit the model
                    model.fit(prophet_df)

                    # Create future dataframe starting from today (forward-looking forecast)
                    today = datetime.now().date()
                    future_dates = pd.date_range(start=today, periods=horizon_days, freq='D')
                    future = pd.DataFrame({'ds': future_dates})
                    forecast = model.predict(future)

                    # Create forecast dictionary
                    forecast_dict = {}
                    for _, row in forecast.iterrows():
                        date_str = row['ds'].strftime('%Y-%m-%d')
                        qty = max(0, row['yhat'])  # Ensure non-negative

                        forecast_dict[date_str] = {
                            'quantity': float(qty),
                            'confidence_lower': float(max(0, row['yhat_lower'])),
                            'confidence_upper': float(max(0, row['yhat_upper']))
                        }

                    return {
                        'forecasts': forecast_dict,
                        'model': 'Prophet',
                        'fitted_params': {
                            'changepoint_prior_scale': 0.05,
                            'seasonality_mode': 'multiplicative',
                            'data_points': len(prophet_df)
                        }
                    }

                except Exception as prophet_error:
                    # Fall through to backup methods
                    pass

            # FALLBACK: Calculate key statistics for intermittent demand
            quantities = ts_data['quantity'].values
            total_quantity = quantities.sum()
            num_days = len(quantities)
            days_with_sales = (quantities > 0).sum()

            # Calculate average daily demand (simple moving average)
            # Use weighted recent history (last 90 days get more weight)
            recent_window = min(90, num_days)
            recent_data = quantities[-recent_window:]

            # Calculate demand rate (average per day)
            avg_daily_demand = recent_data.mean()

            # For intermittent demand, also calculate:
            # - Demand when it occurs (average non-zero demand)
            # - Probability of demand occurring
            non_zero_recent = recent_data[recent_data > 0]
            if len(non_zero_recent) > 0:
                avg_demand_when_occurs = non_zero_recent.mean()
                demand_probability = len(non_zero_recent) / len(recent_data)
            else:
                avg_demand_when_occurs = 0
                demand_probability = 0

            # Use exponential smoothing if data is not too sparse
            if days_with_sales / num_days >= 0.3 and STATS_AVAILABLE:  # At least 30% of days have sales
                try:
                    if len(ts_data) >= 14:
                        model = ExponentialSmoothing(
                            ts_data['quantity'],
                            seasonal_periods=7,
                            trend='add',
                            seasonal='add',
                            initialization_method='estimated'
                        )
                        fitted_model = model.fit(optimized=True, disp=False)
                        forecast_values = fitted_model.forecast(steps=horizon_days)
                        model_name = 'Exponential Smoothing'
                    else:
                        model = ExponentialSmoothing(
                            ts_data['quantity'],
                            trend='add',
                            initialization_method='estimated'
                        )
                        fitted_model = model.fit(optimized=True, disp=False)
                        forecast_values = fitted_model.forecast(steps=horizon_days)
                        model_name = 'Exponential Smoothing (Simple)'

                    # Create forecast dictionary from model output
                    forecast_dict = {}
                    start_date = datetime.now().date()

                    for i in range(horizon_days):
                        date = start_date + timedelta(days=i)
                        qty = max(0, forecast_values.iloc[i] if hasattr(forecast_values, 'iloc') else forecast_values[i])

                        forecast_dict[date.strftime('%Y-%m-%d')] = {
                            'quantity': float(qty),
                            'confidence_lower': float(max(0, qty * 0.8)),
                            'confidence_upper': float(qty * 1.2)
                        }

                    return {
                        'forecasts': forecast_dict,
                        'model': model_name,
                        'fitted_params': {}
                    }
                except:
                    # Fall through to simple average method if ES fails
                    pass

            # For sparse/intermittent demand, use simple average method
            forecast_dict = {}
            start_date = datetime.now().date()

            for i in range(horizon_days):
                date = start_date + timedelta(days=i)

                # Simple forecast: use average daily demand
                qty = avg_daily_demand

                forecast_dict[date.strftime('%Y-%m-%d')] = {
                    'quantity': float(qty),
                    'confidence_lower': float(max(0, qty * 0.7)),
                    'confidence_upper': float(qty * 1.3)
                }

            return {
                'forecasts': forecast_dict,
                'model': 'Moving Average (Intermittent Demand)',
                'fitted_params': {
                    'avg_daily_demand': float(avg_daily_demand),
                    'demand_probability': float(demand_probability),
                    'avg_when_occurs': float(avg_demand_when_occurs),
                    'days_with_sales_pct': float(days_with_sales / num_days * 100)
                }
            }

        except Exception as e:
            self.stdout.write(self.style.WARNING(f'    Statistical model error: {e}'))
            import traceback
            traceback.print_exc()
            return None

    def forecast_ml(self, ts_data, horizon_days):
        """Generate forecast using ML models (GradientBoosting, Random Forest)"""

        if not ML_AVAILABLE:
            return self.forecast_statistical(ts_data, horizon_days)

        try:
            # Feature engineering
            df = ts_data.copy()
            df['day_of_week'] = df.index.dayofweek
            df['day_of_month'] = df.index.day
            df['month'] = df.index.month
            df['is_weekend'] = (df.index.dayofweek >= 5).astype(int)

            # Lag features
            for lag in [1, 7, 14, 30]:
                df[f'lag_{lag}'] = df['quantity'].shift(lag)

            # Rolling features
            df['rolling_mean_7'] = df['quantity'].rolling(window=7).mean()
            df['rolling_mean_30'] = df['quantity'].rolling(window=30).mean()
            df['rolling_std_7'] = df['quantity'].rolling(window=7).std()

            # Drop NaN rows
            df = df.dropna()

            if len(df) < 60:  # Need enough data for ML
                return self.forecast_statistical(ts_data, horizon_days)

            # Prepare features and target
            feature_cols = ['day_of_week', 'day_of_month', 'month', 'is_weekend',
                           'lag_1', 'lag_7', 'lag_14', 'lag_30',
                           'rolling_mean_7', 'rolling_mean_30', 'rolling_std_7']

            X = df[feature_cols].values
            y = df['quantity'].values

            # Train model (use XGBoost if available, otherwise GradientBoosting)
            if XGB_AVAILABLE:
                model = xgb.XGBRegressor(
                    n_estimators=100,
                    max_depth=5,
                    learning_rate=0.1,
                    random_state=42,
                    n_jobs=-1
                )
                model_name = 'XGBoost'
            else:
                model = GradientBoostingRegressor(
                    n_estimators=100,
                    max_depth=5,
                    learning_rate=0.1,
                    random_state=42
                )
                model_name = 'GradientBoosting'

            model.fit(X, y)

            # Generate forecasts
            forecast_dict = {}
            last_date = ts_data.index[-1]
            last_values = ts_data['quantity'].tail(30).values  # Keep last 30 days for lag features

            for i in range(horizon_days):
                date = last_date + timedelta(days=i+1)

                # Create features for prediction
                features = [
                    date.dayofweek,
                    date.day,
                    date.month,
                    1 if date.dayofweek >= 5 else 0,
                    last_values[-1] if len(last_values) > 0 else 0,  # lag_1
                    last_values[-7] if len(last_values) >= 7 else 0,  # lag_7
                    last_values[-14] if len(last_values) >= 14 else 0,  # lag_14
                    last_values[-30] if len(last_values) >= 30 else 0,  # lag_30
                    np.mean(last_values[-7:]) if len(last_values) >= 7 else 0,  # rolling_mean_7
                    np.mean(last_values[-30:]) if len(last_values) >= 30 else 0,  # rolling_mean_30
                    np.std(last_values[-7:]) if len(last_values) >= 7 else 0,  # rolling_std_7
                ]

                qty_pred = max(0, model.predict([features])[0])

                forecast_dict[date.strftime('%Y-%m-%d')] = {
                    'quantity': float(qty_pred),
                    'confidence_lower': float(max(0, qty_pred * 0.85)),
                    'confidence_upper': float(qty_pred * 1.15)
                }

                # Update last_values for next iteration
                last_values = np.append(last_values[1:], qty_pred) if len(last_values) >= 30 else np.append(last_values, qty_pred)

            return {
                'forecasts': forecast_dict,
                'model': model_name,
                'feature_importance': dict(zip(feature_cols, model.feature_importances_.tolist()))
            }

        except Exception as e:
            self.stdout.write(self.style.WARNING(f'    ML model error: {e}'))
            return self.forecast_statistical(ts_data, horizon_days)

    def forecast_hybrid(self, ts_data, horizon_days):
        """Generate forecast using hybrid approach (average of statistical + ML)"""

        stat_forecast = self.forecast_statistical(ts_data, horizon_days)
        ml_forecast = self.forecast_ml(ts_data, horizon_days)

        if stat_forecast is None:
            return ml_forecast
        if ml_forecast is None:
            return stat_forecast

        # Average the two forecasts
        forecast_dict = {}
        for date_str in stat_forecast['forecasts'].keys():
            stat_qty = stat_forecast['forecasts'][date_str]['quantity']
            ml_qty = ml_forecast['forecasts'].get(date_str, {}).get('quantity', stat_qty)

            avg_qty = (stat_qty + ml_qty) / 2

            forecast_dict[date_str] = {
                'quantity': float(avg_qty),
                'stat_quantity': float(stat_qty),
                'ml_quantity': float(ml_qty),
                'confidence_lower': float(max(0, avg_qty * 0.75)),
                'confidence_upper': float(avg_qty * 1.25)
            }

        return {
            'forecasts': forecast_dict,
            'model': 'Hybrid (Statistical + ML)',
            'statistical_model': stat_forecast['model'],
            'ml_model': ml_forecast['model']
        }

    def save_forecast(self, entity_name, aggregation_level, model_type, forecast_data, training_data):
        """Save 365-day base forecast to database"""

        if forecast_data is None or 'forecasts' not in forecast_data:
            return

        forecast_id = f"{aggregation_level}_{entity_name.replace(' ', '_')}_365d_{datetime.now().strftime('%Y%m%d')}"

        # Validate that we have 365 days of forecasts
        num_forecast_days = len(forecast_data['forecasts'])
        if num_forecast_days != 365:
            self.stdout.write(
                self.style.WARNING(
                    f'  Warning: Expected 365 days, got {num_forecast_days} for {entity_name}'
                )
            )

        # Calculate accuracy metrics on training data if possible
        mae, mape, rmse = None, None, None
        try:
            # Simple backtest: use last 30 days
            if len(training_data) >= 60:
                train = training_data[:-30]
                test = training_data[-30:]

                # Generate predictions for test period
                test_forecast = self.forecast_statistical(train, 30)
                if test_forecast:
                    actual = test['quantity'].values
                    predicted = [test_forecast['forecasts'].get((test.index[i]).strftime('%Y-%m-%d'), {}).get('quantity', 0)
                                for i in range(len(test))]

                    # Calculate metrics
                    mae = float(mean_absolute_error(actual, predicted))
                    rmse = float(np.sqrt(mean_squared_error(actual, predicted)))

                    # For MAPE, use total demand instead of daily to avoid division by zero
                    total_actual = actual.sum()
                    total_predicted = sum(predicted)

                    if total_actual > 0:
                        mape = float(abs(total_actual - total_predicted) / total_actual * 100)
                    else:
                        mape = 0.0

                    # Cap MAPE at 200% to avoid astronomical values
                    mape = min(mape, 200.0)
        except Exception as e:
            pass

        # Save to database (SalesForecastBase)
        SalesForecastBase.objects.update_or_create(
            entity_name=entity_name,
            aggregation_level=aggregation_level,
            forecast_date=datetime.now().date(),
            defaults={
                'forecast_id': forecast_id,
                'model_type': model_type,
                'daily_forecasts': forecast_data['forecasts'],  # Store as JSON with 365 days
                'training_data_start': training_data.index.min().date(),
                'training_data_end': training_data.index.max().date(),
                'mae': mae,
                'mape': mape,
                'rmse': rmse,
                'accuracy_score': (100 - mape) if mape else None,
                'model_params': {
                    'model': forecast_data.get('model', 'Unknown'),
                    'horizon_days': 365,
                    'training_days': len(training_data),
                    **forecast_data.get('fitted_params', {})
                }
            }
        )

    def update_forecast_schedule(self, entity_name, aggregation_level):
        """Update the forecast schedule tracking"""

        now = timezone.now()
        next_due = now + timedelta(days=30)  # Default: regenerate every 30 days

        ForecastSchedule.objects.update_or_create(
            entity_name=entity_name,
            aggregation_level=aggregation_level,
            defaults={
                'last_generated': now,
                'next_generation_due': next_due,
                'generation_frequency_days': 30,
                'status': 'current'
            }
        )
