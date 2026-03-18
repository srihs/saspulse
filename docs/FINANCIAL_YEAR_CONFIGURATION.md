# Financial Year Configuration System

## Overview

The financial year (FY) configuration system allows you to define and manage your organization's financial year period through the Django admin interface. The system now defaults to **April 1 to March 31** (replacing the previous July 1 to June 30 system) and is fully configurable.

## Key Features

- **Configurable FY Dates**: Set any financial year start/end through admin
- **Default: April-March**: April 1 to March 31 (NZ/AU/UK/India standard)
- **Singleton Pattern**: Only one settings record (prevents configuration conflicts)
- **Validation**: Ensures FY dates are valid and span year boundaries
- **Edge Case Handling**: Handles leap years, invalid dates (e.g., Feb 30)
- **Easy Integration**: Simple utility functions for use throughout the codebase

## Implementation Details

### 1. SystemSettings Model

**Location**: `dashboard/models.py`

```python
class SystemSettings(models.Model):
    """
    Singleton model for system-wide settings
    Stores configurable parameters like financial year dates
    """
    fy_start_month = models.IntegerField(default=4)  # April
    fy_start_day = models.IntegerField(default=1)    # 1st
    fy_end_month = models.IntegerField(default=3)    # March
    fy_end_day = models.IntegerField(default=31)     # 31st
```

**Features**:
- Singleton pattern (only one record with pk=1)
- Auto-creates with defaults if doesn't exist
- Validation ensures dates are valid and span year boundary
- Cannot be deleted (protection)

### 2. Admin Interface

**Location**: `dashboard/admin.py`

**How to Access**:
1. Go to Django Admin: `/admin/`
2. Navigate to: **Dashboard > System Settings**
3. Edit the single settings record
4. Change FY dates as needed

**Features**:
- User-friendly form with month/day dropdowns
- Inline help text with examples
- Validation prevents invalid configurations
- Tracks who made changes (`updated_by` field)
- Cannot add multiple records (singleton enforcement)
- Cannot delete the settings record

### 3. Utility Functions

**Location**: `dashboard/utils/financial_year.py`

#### `get_financial_year_dates(reference_date=None)`

Returns the **last completed** financial year dates.

```python
from dashboard.utils.financial_year import get_financial_year_dates

# Get last completed FY (default: uses today)
last_fy_start, last_fy_end = get_financial_year_dates()

# Example output for March 18, 2026 with April-March FY:
# last_fy_start = date(2024, 4, 1)   # April 1, 2024
# last_fy_end = date(2025, 3, 31)    # March 31, 2025
```

#### `get_current_financial_year_dates(reference_date=None)`

Returns the **current ongoing** financial year dates.

```python
from dashboard.utils.financial_year import get_current_financial_year_dates

# Get current FY
current_fy_start, current_fy_end = get_current_financial_year_dates()

# Example output for March 18, 2026 with April-March FY:
# current_fy_start = date(2025, 4, 1)   # April 1, 2025
# current_fy_end = date(2026, 3, 31)    # March 31, 2026
```

#### `get_financial_year_label(fy_start, fy_end)`

Generates a human-readable label.

```python
label = get_financial_year_label(date(2024, 4, 1), date(2025, 3, 31))
# Returns: "FY 2024-25"
```

#### `format_date_range(start_date, end_date)`

Formats dates in readable format.

```python
range_str = format_date_range(date(2024, 4, 1), date(2025, 3, 31))
# Returns: "01 April 2024 to 31 March 2025"
```

### 4. Updated Views

**Location**: `dashboard/views.py`

The `top_performing_schools` view has been updated to use the new utility:

```python
from dashboard.utils.financial_year import get_financial_year_dates

def top_performing_schools(request):
    # Old hardcoded logic removed
    # if today.month >= 7:
    #     last_fy_start = date(today.year - 1, 7, 1)
    #     last_fy_end = date(today.year, 6, 30)

    # New configurable system
    last_fy_start, last_fy_end = get_financial_year_dates()

    # Rest of view logic...
```

## Usage Examples

### Example 1: Default April-March System (Current)

**Configuration**:
- Start: April 1
- End: March 31

**Scenario**: Today is March 18, 2026

```python
# Current FY (ongoing)
current_fy_start, current_fy_end = get_current_financial_year_dates()
# Result: April 1, 2025 to March 31, 2026

# Last completed FY
last_fy_start, last_fy_end = get_financial_year_dates()
# Result: April 1, 2024 to March 31, 2025
```

### Example 2: Old July-June System

**Configuration**:
- Start: July 1
- End: June 30

**Scenario**: Today is January 15, 2026

```python
# Current FY (ongoing)
current_fy_start, current_fy_end = get_current_financial_year_dates()
# Result: July 1, 2025 to June 30, 2026

# Last completed FY
last_fy_start, last_fy_end = get_financial_year_dates()
# Result: July 1, 2024 to June 30, 2025
```

### Example 3: US Federal Government (October-September)

**Configuration**:
- Start: October 1
- End: September 30

## How to Change Financial Year

### Through Django Admin (Recommended)

1. Log in to Django Admin
2. Go to **Dashboard > System Settings**
3. Click on the settings record (there will be only one)
4. Update the values:
   - **FY Start Month**: Choose from dropdown (1=January, 4=April, etc.)
   - **FY Start Day**: Choose day (1-31)
   - **FY End Month**: Choose from dropdown
   - **FY End Day**: Choose day (1-31)
5. Click **Save**

### Validation Rules

The system validates:
1. **Valid Dates**: Month/day combinations must be valid (e.g., no Feb 30)
2. **Year Boundary**: FY must span year boundary (start month > end month)
   - ✅ Valid: April 1 to March 31 (4 > 3)
   - ✅ Valid: July 1 to June 30 (7 > 6)
   - ❌ Invalid: March 1 to June 30 (3 < 6)

### Edge Cases Handled

#### Leap Years
If you set Feb 29 as an end date, the system automatically falls back to Feb 28 in non-leap years.

**Example**:
- FY: March 1 to February 29
- For FY 2024-25: March 1, 2024 to **Feb 28, 2025** (auto-adjusted)
- For FY 2023-24: March 1, 2023 to **Feb 29, 2024** (leap year, valid)

#### Invalid Days for Month
If you set an invalid day (e.g., April 31), the system uses the last valid day of that month.

## Testing

A comprehensive test suite is available:

```bash
python3 test_financial_year.py
```

**Tests include**:
1. Default April-March system
2. Edge case: After FY end
3. Alternative July-June system
4. February leap year handling

## Migration

The system was migrated in:
- **Migration**: `dashboard/migrations/0011_systemsettings.py`
- **Date**: March 18, 2026

To apply the migration (already done):
```bash
python3 manage.py migrate dashboard
```

## Files Changed/Created

### New Files
1. `dashboard/utils/financial_year.py` - Utility functions
2. `test_financial_year.py` - Test suite
3. `FINANCIAL_YEAR_CONFIGURATION.md` - This documentation

### Modified Files
1. `dashboard/models.py` - Added SystemSettings model
2. `dashboard/admin.py` - Registered SystemSettings admin
3. `dashboard/views.py` - Updated top_performing_schools view
4. `dashboard/migrations/0011_systemsettings.py` - Migration file

## Integration with Existing Code

To use the financial year system in your code:

```python
from dashboard.utils.financial_year import (
    get_financial_year_dates,
    get_current_financial_year_dates,
    get_financial_year_label,
    format_date_range
)

# Get last completed FY for reporting
last_fy_start, last_fy_end = get_financial_year_dates()

# Get current FY for ongoing tracking
current_fy_start, current_fy_end = get_current_financial_year_dates()

# Generate labels
fy_label = get_financial_year_label(last_fy_start, last_fy_end)
date_range = format_date_range(last_fy_start, last_fy_end)

print(f"{fy_label}: {date_range}")
# Output: "FY 2024-25: 01 April 2024 to 31 March 2025"
```

## Benefits

1. **No More Hardcoding**: FY logic is centralized and configurable
2. **Easy Updates**: Change FY through admin, no code changes needed
3. **Consistent**: All parts of system use same FY definition
4. **Flexible**: Supports any FY scheme (April-March, July-June, etc.)
5. **Safe**: Validation prevents invalid configurations
6. **Tested**: Comprehensive test coverage for edge cases

## Future Enhancements

Potential future improvements:
- Multiple FY definitions (for different departments/regions)
- Historical FY tracking (when FY definition changes)
- Automatic alerts when approaching FY boundaries
- FY calendar view in admin
- Export FY dates as iCal/CSV

## Support

For questions or issues, contact the development team or refer to:
- Django Admin: `/admin/dashboard/systemsettings/`
- Test Script: `python3 test_financial_year.py`
- This Documentation: `FINANCIAL_YEAR_CONFIGURATION.md`

---

**Last Updated**: March 18, 2026
**Default FY**: April 1 to March 31
**Status**: ✅ Implemented and Tested
