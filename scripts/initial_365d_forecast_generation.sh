#!/bin/bash

################################################################################
# Initial 365-Day Base Forecast Generation Script
#
# This script generates the initial set of 365-day base forecasts for all
# aggregation levels (school, product, shop). Run this once to populate the
# SalesForecastBase model.
#
# Usage:
#   bash scripts/initial_365d_forecast_generation.sh
#
# Requirements:
#   - Python virtual environment activated
#   - Django project configured
#   - Database migrations applied
#   - Sufficient historical sales data (>30 days)
#
# Estimated Runtime:
#   - Small dataset (<100 entities): 5-10 minutes
#   - Medium dataset (100-500 entities): 30-60 minutes
#   - Large dataset (500-2000 entities): 1-3 hours
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MIN_SALES=10  # Minimum sales to generate forecast
PROJECT_DIR="/Users/sas/Repos/saspulse"

echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}  365-DAY BASE FORECAST SYSTEM - Initial Generation${NC}"
echo -e "${BLUE}================================================================================${NC}"
echo ""

# Check if we're in the project directory
if [ ! -f "manage.py" ]; then
    echo -e "${YELLOW}Warning: manage.py not found in current directory${NC}"
    echo -e "Changing to project directory: ${PROJECT_DIR}"
    cd "${PROJECT_DIR}" || exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: Python virtual environment not activated${NC}"
    echo -e "Attempting to activate env/bin/activate..."

    if [ -f "env/bin/activate" ]; then
        source env/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${RED}Error: Virtual environment not found at env/bin/activate${NC}"
        echo -e "Please activate your virtual environment and run again."
        exit 1
    fi
fi

# Check if migrations are applied
echo ""
echo -e "${YELLOW}Checking database migrations...${NC}"
python manage.py migrate dashboard --check 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Dashboard migrations not applied${NC}"
    echo -e "Running migrations..."
    python manage.py migrate dashboard
fi
echo -e "${GREEN}✓ Migrations are up to date${NC}"

# Start generation
echo ""
echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}  Starting 365-Day Forecast Generation${NC}"
echo -e "${BLUE}================================================================================${NC}"
echo ""
echo -e "Configuration:"
echo -e "  Minimum sales threshold: ${MIN_SALES}"
echo -e "  Aggregation levels: school, product, shop"
echo -e "  Forecast horizon: 365 days"
echo ""

START_TIME=$(date +%s)

# Generate school-level forecasts
echo -e "${YELLOW}[1/3] Generating SCHOOL-level forecasts...${NC}"
echo -e "      (Forecasts aggregated by school/sub-category)"
echo ""
python manage.py generate_365d_forecasts --level school --min-sales ${MIN_SALES}
SCHOOL_EXIT_CODE=$?

if [ $SCHOOL_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ School-level forecasts completed${NC}"
else
    echo -e "${RED}✗ School-level forecasts failed (exit code: ${SCHOOL_EXIT_CODE})${NC}"
fi

echo ""
echo -e "${BLUE}-------------------------------------------------------------------------------${NC}"
echo ""

# Generate product-level forecasts
echo -e "${YELLOW}[2/3] Generating PRODUCT-level forecasts...${NC}"
echo -e "      (Forecasts for individual SKU codes)"
echo ""
python manage.py generate_365d_forecasts --level product --min-sales ${MIN_SALES}
PRODUCT_EXIT_CODE=$?

if [ $PRODUCT_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Product-level forecasts completed${NC}"
else
    echo -e "${RED}✗ Product-level forecasts failed (exit code: ${PRODUCT_EXIT_CODE})${NC}"
fi

echo ""
echo -e "${BLUE}-------------------------------------------------------------------------------${NC}"
echo ""

# Generate shop-level forecasts
echo -e "${YELLOW}[3/3] Generating SHOP-level forecasts...${NC}"
echo -e "      (Forecasts aggregated by shop category)"
echo ""
python manage.py generate_365d_forecasts --level shop --min-sales ${MIN_SALES}
SHOP_EXIT_CODE=$?

if [ $SHOP_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Shop-level forecasts completed${NC}"
else
    echo -e "${RED}✗ Shop-level forecasts failed (exit code: ${SHOP_EXIT_CODE})${NC}"
fi

echo ""
echo -e "${BLUE}================================================================================${NC}"

# Calculate elapsed time
END_TIME=$(date +%s)
ELAPSED_TIME=$((END_TIME - START_TIME))
ELAPSED_MINUTES=$((ELAPSED_TIME / 60))
ELAPSED_SECONDS=$((ELAPSED_TIME % 60))

echo -e "${BLUE}  Generation Summary${NC}"
echo -e "${BLUE}================================================================================${NC}"
echo ""

# Check overall success
TOTAL_ERRORS=$((SCHOOL_EXIT_CODE + PRODUCT_EXIT_CODE + SHOP_EXIT_CODE))

if [ $TOTAL_ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All forecasts generated successfully!${NC}"
else
    echo -e "${RED}⚠ Some forecasts failed (${TOTAL_ERRORS} errors)${NC}"
fi

echo ""
echo -e "Results:"
echo -e "  School-level:  $([ $SCHOOL_EXIT_CODE -eq 0 ] && echo -e ${GREEN}SUCCESS${NC} || echo -e ${RED}FAILED${NC})"
echo -e "  Product-level: $([ $PRODUCT_EXIT_CODE -eq 0 ] && echo -e ${GREEN}SUCCESS${NC} || echo -e ${RED}FAILED${NC})"
echo -e "  Shop-level:    $([ $SHOP_EXIT_CODE -eq 0 ] && echo -e ${GREEN}SUCCESS${NC} || echo -e ${RED}FAILED${NC})"
echo ""
echo -e "Time elapsed: ${ELAPSED_MINUTES}m ${ELAPSED_SECONDS}s"
echo ""

# Get forecast statistics from database
echo -e "${YELLOW}Retrieving forecast statistics...${NC}"
python manage.py shell << 'PYEOF'
from dashboard.models import SalesForecastBase, ForecastSchedule

total_forecasts = SalesForecastBase.objects.count()
total_schedules = ForecastSchedule.objects.count()

print(f"\nForecast Statistics:")
print(f"  Total base forecasts: {total_forecasts}")
print(f"  Total schedules:      {total_schedules}")

# Breakdown by level
from django.db.models import Count
level_stats = SalesForecastBase.objects.values('aggregation_level').annotate(
    count=Count('id')
).order_by('aggregation_level')

print(f"\nBreakdown by aggregation level:")
for stat in level_stats:
    print(f"  {stat['aggregation_level']:10}: {stat['count']:5} forecasts")

# Show latest forecast
latest = SalesForecastBase.objects.order_by('-forecast_date').first()
if latest:
    print(f"\nLatest forecast:")
    print(f"  Entity:  {latest.entity_name}")
    print(f"  Level:   {latest.aggregation_level}")
    print(f"  Date:    {latest.forecast_date}")
    print(f"  Model:   {latest.model_params.get('model', 'Unknown')}")
    num_days = len(latest.daily_forecasts)
    print(f"  Days:    {num_days}")
PYEOF

echo ""
echo -e "${BLUE}================================================================================${NC}"
echo -e "${GREEN}✓ Initial forecast generation complete!${NC}"
echo -e "${BLUE}================================================================================${NC}"
echo ""

# Next steps
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo -e "  1. Verify forecasts in database:"
echo -e "     ${BLUE}python manage.py check_forecast_schedule${NC}"
echo ""
echo -e "  2. View forecasts in web dashboard:"
echo -e "     ${BLUE}http://localhost:8000/dashboard/forecasting/${NC}"
echo ""
echo -e "  3. Monitor forecast health:"
echo -e "     ${BLUE}http://localhost:8000/dashboard/forecasting/health/${NC}"
echo ""
echo -e "  4. Set up automated regeneration (cron):"
echo -e "     ${BLUE}bash scripts/setup_forecast_cron.sh${NC}"
echo ""

exit $TOTAL_ERRORS
