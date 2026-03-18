"""
Financial Year Utilities

Provides functions for calculating financial year dates based on configurable settings.
"""

from datetime import date, timedelta
from typing import Tuple, Optional


def get_financial_year_dates(reference_date: Optional[date] = None) -> Tuple[date, date]:
    """
    Calculate the last completed financial year dates based on system settings.

    This function handles financial years that span across calendar year boundaries
    (e.g., April 1, 2025 to March 31, 2026).

    Args:
        reference_date: Date to use as reference point (default: today)

    Returns:
        Tuple of (fy_start, fy_end) representing the last COMPLETED financial year

    Examples:
        If today is March 18, 2026 and FY is April-March:
        - Current FY: April 1, 2025 to March 31, 2026 (ongoing)
        - Last COMPLETED FY: April 1, 2024 to March 31, 2025 (returned)

        If today is March 18, 2026 and FY is July-June:
        - Current FY: July 1, 2025 to June 30, 2026 (ongoing)
        - Last COMPLETED FY: July 1, 2024 to June 30, 2025 (returned)
    """
    from dashboard.models import SystemSettings

    # Load system settings (uses defaults if not configured)
    settings = SystemSettings.load()

    # Use today if no reference date provided
    if reference_date is None:
        reference_date = date.today()

    # Get FY configuration
    fy_start_month = settings.fy_start_month
    fy_start_day = settings.fy_start_day
    fy_end_month = settings.fy_end_month
    fy_end_day = settings.fy_end_day

    # Determine the current FY based on reference date
    # Since FY spans year boundary, we need to check if we're before or after the start month
    current_year = reference_date.year

    # Try to construct the FY start date for the current calendar year
    try:
        current_fy_start = date(current_year, fy_start_month, fy_start_day)
    except ValueError:
        # Handle edge case like Feb 30 by using last valid day of month
        current_fy_start = _get_last_valid_day(current_year, fy_start_month, fy_start_day)

    # Check if we're currently in a FY that started this calendar year
    if reference_date >= current_fy_start:
        # We're in the FY that started this year
        # Current FY: fy_start_month/fy_start_day/current_year to fy_end_month/fy_end_day/(current_year+1)
        # Last COMPLETED FY: previous year
        last_fy_start_year = current_year - 1
        last_fy_end_year = current_year
    else:
        # We're before the FY start, so we're in the FY that started last year
        # Current FY: fy_start_month/fy_start_day/(current_year-1) to fy_end_month/fy_end_day/current_year
        # Last COMPLETED FY: two years ago
        last_fy_start_year = current_year - 2
        last_fy_end_year = current_year - 1

    # Construct last completed FY dates
    try:
        last_fy_start = date(last_fy_start_year, fy_start_month, fy_start_day)
    except ValueError:
        last_fy_start = _get_last_valid_day(last_fy_start_year, fy_start_month, fy_start_day)

    try:
        last_fy_end = date(last_fy_end_year, fy_end_month, fy_end_day)
    except ValueError:
        last_fy_end = _get_last_valid_day(last_fy_end_year, fy_end_month, fy_end_day)

    return (last_fy_start, last_fy_end)


def get_current_financial_year_dates(reference_date: Optional[date] = None) -> Tuple[date, date]:
    """
    Calculate the current (ongoing) financial year dates based on system settings.

    Args:
        reference_date: Date to use as reference point (default: today)

    Returns:
        Tuple of (fy_start, fy_end) representing the current financial year

    Examples:
        If today is March 18, 2026 and FY is April-March:
        - Current FY: April 1, 2025 to March 31, 2026 (returned)
    """
    from dashboard.models import SystemSettings

    # Load system settings
    settings = SystemSettings.load()

    # Use today if no reference date provided
    if reference_date is None:
        reference_date = date.today()

    # Get FY configuration
    fy_start_month = settings.fy_start_month
    fy_start_day = settings.fy_start_day
    fy_end_month = settings.fy_end_month
    fy_end_day = settings.fy_end_day

    # Determine the current FY
    current_year = reference_date.year

    # Try to construct the FY start date for the current calendar year
    try:
        current_fy_start = date(current_year, fy_start_month, fy_start_day)
    except ValueError:
        current_fy_start = _get_last_valid_day(current_year, fy_start_month, fy_start_day)

    # Check if we're currently in a FY that started this calendar year
    if reference_date >= current_fy_start:
        # We're in the FY that started this year
        fy_start_year = current_year
        fy_end_year = current_year + 1
    else:
        # We're before the FY start, so we're in the FY that started last year
        fy_start_year = current_year - 1
        fy_end_year = current_year

    # Construct current FY dates
    try:
        current_fy_start = date(fy_start_year, fy_start_month, fy_start_day)
    except ValueError:
        current_fy_start = _get_last_valid_day(fy_start_year, fy_start_month, fy_start_day)

    try:
        current_fy_end = date(fy_end_year, fy_end_month, fy_end_day)
    except ValueError:
        current_fy_end = _get_last_valid_day(fy_end_year, fy_end_month, fy_end_day)

    return (current_fy_start, current_fy_end)


def _get_last_valid_day(year: int, month: int, day: int) -> date:
    """
    Get the last valid day of a month, handling edge cases like Feb 30.

    Args:
        year: Year
        month: Month (1-12)
        day: Desired day (may be invalid like 31 for February)

    Returns:
        Valid date with the last available day of the month if day is invalid
    """
    # Try decreasing days until we find a valid date
    for d in range(day, 0, -1):
        try:
            return date(year, month, d)
        except ValueError:
            continue

    # Fallback (should never reach here)
    return date(year, month, 1)


def get_financial_year_label(fy_start: date, fy_end: date) -> str:
    """
    Generate a human-readable label for a financial year.

    Args:
        fy_start: Start date of financial year
        fy_end: End date of financial year

    Returns:
        String like "FY 2024-25" or "FY 2025"

    Examples:
        April 1, 2024 to March 31, 2025 -> "FY 2024-25"
        July 1, 2024 to June 30, 2025 -> "FY 2024-25"
    """
    if fy_start.year == fy_end.year:
        return f"FY {fy_start.year}"
    else:
        # Use short year format for end year
        end_year_short = str(fy_end.year)[-2:]
        return f"FY {fy_start.year}-{end_year_short}"


def format_date_range(start_date: date, end_date: date) -> str:
    """
    Format a date range in a human-readable way.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        String like "1 April 2024 to 31 March 2025"
    """
    return f"{start_date.strftime('%d %B %Y')} to {end_date.strftime('%d %B %Y')}"
