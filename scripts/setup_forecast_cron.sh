#!/bin/bash

################################################################################
# Forecast Regeneration Cron Setup Script
#
# This script helps set up automated forecast regeneration using cron.
# It provides options for different schedules and automation levels.
#
# Usage:
#   bash scripts/setup_forecast_cron.sh [OPTIONS]
#
# Options:
#   --install     Add cron jobs to crontab
#   --remove      Remove cron jobs from crontab
#   --show        Show recommended cron configuration (default)
#   --test        Test the commands without installing
#
# Recommended Schedule:
#   - Daily health check with auto-regeneration (2 AM)
#   - Weekly email notification (Monday 8 AM)
#   - Monthly full regeneration (1st of month, 3 AM)
################################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_DIR="/Users/sas/Repos/saspulse"
VENV_DIR="env"
PYTHON_CMD="python"

# Parse arguments
ACTION="${1:-show}"

echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}  365-Day Forecast System - Cron Setup${NC}"
echo -e "${BLUE}================================================================================${NC}"
echo ""

# Function to show recommended cron jobs
show_cron_config() {
    echo -e "${YELLOW}Recommended Cron Configuration:${NC}"
    echo ""
    echo -e "${GREEN}# 365-Day Forecast System - Automated Maintenance${NC}"
    echo -e "${GREEN}# Project: SASPulse Dashboard${NC}"
    echo -e "${GREEN}# Generated: $(date)${NC}"
    echo ""
    echo -e "${BLUE}# Daily health check with auto-regeneration (2 AM)${NC}"
    echo "0 2 * * * cd ${PROJECT_DIR} && source ${VENV_DIR}/bin/activate && ${PYTHON_CMD} manage.py check_forecast_schedule --regenerate >> /tmp/forecast_cron.log 2>&1"
    echo ""
    echo -e "${BLUE}# Weekly email notification (Monday 8 AM)${NC}"
    echo "0 8 * * 1 cd ${PROJECT_DIR} && source ${VENV_DIR}/bin/activate && ${PYTHON_CMD} manage.py check_forecast_schedule --notify >> /tmp/forecast_cron.log 2>&1"
    echo ""
    echo -e "${BLUE}# Monthly full regeneration (1st of month, 3 AM)${NC}"
    echo "0 3 1 * * cd ${PROJECT_DIR} && source ${VENV_DIR}/bin/activate && ${PYTHON_CMD} manage.py generate_365d_forecasts --force >> /tmp/forecast_cron.log 2>&1"
    echo ""
}

# Function to create cron jobs file
create_cron_file() {
    CRON_FILE="/tmp/saspulse_forecast_cron.txt"

    cat > "${CRON_FILE}" << EOF
# 365-Day Forecast System - Automated Maintenance
# Project: SASPulse Dashboard
# Generated: $(date)

# Daily health check with auto-regeneration (2 AM)
0 2 * * * cd ${PROJECT_DIR} && source ${VENV_DIR}/bin/activate && ${PYTHON_CMD} manage.py check_forecast_schedule --regenerate >> /tmp/forecast_cron.log 2>&1

# Weekly email notification (Monday 8 AM)
0 8 * * 1 cd ${PROJECT_DIR} && source ${VENV_DIR}/bin/activate && ${PYTHON_CMD} manage.py check_forecast_schedule --notify >> /tmp/forecast_cron.log 2>&1

# Monthly full regeneration (1st of month, 3 AM)
0 3 1 * * cd ${PROJECT_DIR} && source ${VENV_DIR}/bin/activate && ${PYTHON_CMD} manage.py generate_365d_forecasts --force >> /tmp/forecast_cron.log 2>&1
EOF

    echo "${CRON_FILE}"
}

# Function to install cron jobs
install_cron() {
    echo -e "${YELLOW}Installing cron jobs...${NC}"
    echo ""

    # Check if cron is available
    if ! command -v crontab &> /dev/null; then
        echo -e "${RED}Error: crontab command not found${NC}"
        echo -e "Cron may not be installed or available on this system."
        exit 1
    fi

    # Create temporary cron file
    CRON_FILE=$(create_cron_file)

    # Check if our jobs already exist
    EXISTING_CRON=$(crontab -l 2>/dev/null || echo "")
    if echo "${EXISTING_CRON}" | grep -q "365-Day Forecast System"; then
        echo -e "${YELLOW}Warning: Forecast cron jobs already exist${NC}"
        echo ""
        echo -e "Existing jobs:"
        echo "${EXISTING_CRON}" | grep -A 10 "365-Day Forecast System"
        echo ""
        read -p "Remove existing jobs and reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Installation cancelled${NC}"
            exit 0
        fi

        # Remove existing jobs
        remove_cron
    fi

    # Backup current crontab
    BACKUP_FILE="/tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt"
    crontab -l > "${BACKUP_FILE}" 2>/dev/null || touch "${BACKUP_FILE}"
    echo -e "${GREEN}✓ Current crontab backed up to: ${BACKUP_FILE}${NC}"

    # Append new jobs
    (crontab -l 2>/dev/null; cat "${CRON_FILE}") | crontab -

    echo -e "${GREEN}✓ Cron jobs installed successfully${NC}"
    echo ""
    echo -e "Installed jobs:"
    crontab -l | grep -A 10 "365-Day Forecast System"
    echo ""
    echo -e "${YELLOW}Note: Logs will be written to /tmp/forecast_cron.log${NC}"
}

# Function to remove cron jobs
remove_cron() {
    echo -e "${YELLOW}Removing forecast cron jobs...${NC}"

    # Backup current crontab
    BACKUP_FILE="/tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt"
    crontab -l > "${BACKUP_FILE}" 2>/dev/null || touch "${BACKUP_FILE}"
    echo -e "${GREEN}✓ Current crontab backed up to: ${BACKUP_FILE}${NC}"

    # Remove lines related to forecast system
    crontab -l 2>/dev/null | grep -v "365-Day Forecast System" | grep -v "check_forecast_schedule" | grep -v "generate_365d_forecasts" | crontab -

    echo -e "${GREEN}✓ Forecast cron jobs removed${NC}"
}

# Function to test commands
test_cron() {
    echo -e "${YELLOW}Testing forecast commands...${NC}"
    echo ""

    # Test 1: Check forecast schedule
    echo -e "${BLUE}Test 1: Checking forecast schedule${NC}"
    cd "${PROJECT_DIR}" || exit 1

    if [ -f "${VENV_DIR}/bin/activate" ]; then
        source "${VENV_DIR}/bin/activate"
    fi

    ${PYTHON_CMD} manage.py check_forecast_schedule
    TEST1_EXIT=$?

    if [ $TEST1_EXIT -eq 0 ]; then
        echo -e "${GREEN}✓ check_forecast_schedule command works${NC}"
    else
        echo -e "${RED}✗ check_forecast_schedule command failed${NC}"
    fi

    echo ""
    echo -e "${BLUE}Test 2: Testing forecast generation (dry run)${NC}"
    echo -e "${YELLOW}Generating 1 test forecast...${NC}"

    ${PYTHON_CMD} manage.py generate_365d_forecasts --level product --limit 1
    TEST2_EXIT=$?

    if [ $TEST2_EXIT -eq 0 ]; then
        echo -e "${GREEN}✓ generate_365d_forecasts command works${NC}"
    else
        echo -e "${RED}✗ generate_365d_forecasts command failed${NC}"
    fi

    echo ""
    TOTAL_ERRORS=$((TEST1_EXIT + TEST2_EXIT))

    if [ $TOTAL_ERRORS -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed - commands are ready for cron${NC}"
    else
        echo -e "${RED}⚠ Some tests failed - please fix errors before installing cron${NC}"
        exit 1
    fi
}

# Main logic
case "${ACTION}" in
    --show)
        show_cron_config
        echo ""
        echo -e "${YELLOW}To install these cron jobs, run:${NC}"
        echo -e "  ${BLUE}bash scripts/setup_forecast_cron.sh --install${NC}"
        echo ""
        ;;

    --install)
        echo -e "${YELLOW}This will install automated forecast regeneration cron jobs.${NC}"
        echo ""
        show_cron_config
        echo ""
        read -p "Proceed with installation? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_cron
            echo ""
            echo -e "${GREEN}Setup complete!${NC}"
            echo ""
            echo -e "${YELLOW}Next steps:${NC}"
            echo -e "  1. Monitor logs: ${BLUE}tail -f /tmp/forecast_cron.log${NC}"
            echo -e "  2. View cron jobs: ${BLUE}crontab -l${NC}"
            echo -e "  3. Remove jobs: ${BLUE}bash scripts/setup_forecast_cron.sh --remove${NC}"
        else
            echo -e "${YELLOW}Installation cancelled${NC}"
        fi
        ;;

    --remove)
        echo -e "${YELLOW}This will remove all forecast cron jobs.${NC}"
        echo ""
        read -p "Proceed with removal? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            remove_cron
            echo ""
            echo -e "${GREEN}Cron jobs removed successfully${NC}"
        else
            echo -e "${YELLOW}Removal cancelled${NC}"
        fi
        ;;

    --test)
        test_cron
        echo ""
        echo -e "${GREEN}Tests complete!${NC}"
        echo ""
        echo -e "${YELLOW}To install cron jobs, run:${NC}"
        echo -e "  ${BLUE}bash scripts/setup_forecast_cron.sh --install${NC}"
        ;;

    *)
        echo -e "${RED}Error: Invalid option '${ACTION}'${NC}"
        echo ""
        echo "Usage: bash scripts/setup_forecast_cron.sh [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --show      Show recommended cron configuration (default)"
        echo "  --install   Install cron jobs"
        echo "  --remove    Remove cron jobs"
        echo "  --test      Test commands before installing"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}  Cron Setup Complete${NC}"
echo -e "${BLUE}================================================================================${NC}"
