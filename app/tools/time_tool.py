"""
Time Tool

Provides reliable date/time parsing and utilities using only standard library.
Used by agents, orchestrator, and analytics modules for consistent time handling.

Functions:
- utcnow_iso(): Get current UTC time as ISO string
- parse_iso_datetime(value): Parse ISO datetime string to datetime object
- parse_iso_date(value): Parse date string to date object
- ensure_date_str(value, default): Convert any date input to YYYY-MM-DD string
- ensure_datetime_str(value, default): Convert any datetime input to ISO string
- minutes_between(a, b): Calculate minutes between two timestamps

All functions are safe (never raise on bad input, return None or default).
No external dependencies beyond Python standard library.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


def utcnow_iso() -> str:
    """
    Get current UTC time as ISO 8601 string with 'Z' suffix.
    
    Returns:
        ISO string like "2026-02-05T00:30:00Z"
    
    Example:
        >>> now = utcnow_iso()
        >>> now.endswith('Z')
        True
    """
    return datetime.utcnow().isoformat() + "Z"


def today_iso() -> str:
    """
    Get today's date as YYYY-MM-DD string (UTC).
    
    Returns:
        Date string like "2026-02-05"
    """
    return datetime.utcnow().date().isoformat()


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    """
    Parse ISO datetime string to datetime object.
    
    Supports formats:
    - "2026-02-05T00:30:00Z"
    - "2026-02-05T00:30:00"
    - "2026-02-05 00:30:00"
    - "2026-02-05T00:30:00+01:00"
    
    Args:
        value: datetime, string, or other value
    
    Returns:
        datetime object or None if parsing fails
    
    Example:
        >>> dt = parse_iso_datetime("2026-02-05T00:30:00Z")
        >>> dt is not None
        True
    """
    if value is None:
        return None
    
    # Already a datetime
    if isinstance(value, datetime):
        return value
    
    # Convert to string
    value_str = str(value).strip()
    
    if not value_str:
        return None
    
    # Try various ISO formats
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",          # 2026-02-05T00:30:00Z
        "%Y-%m-%dT%H:%M:%S",           # 2026-02-05T00:30:00
        "%Y-%m-%d %H:%M:%S",           # 2026-02-05 00:30:00
        "%Y-%m-%dT%H:%M:%S.%fZ",      # 2026-02-05T00:30:00.123Z
        "%Y-%m-%dT%H:%M:%S.%f",       # 2026-02-05T00:30:00.123
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(value_str, fmt)
        except ValueError:
            continue
    
    # Try ISO format with timezone (using fromisoformat if available)
    try:
        # Remove 'Z' suffix and parse
        if value_str.endswith('Z'):
            value_str = value_str[:-1]
        # Handle timezone offsets by removing them (keep naive datetime)
        if '+' in value_str:
            value_str = value_str.split('+')[0]
        elif value_str.count('-') > 2:  # Has negative timezone offset
            parts = value_str.rsplit('-', 1)
            if ':' in parts[1]:  # Timezone part
                value_str = parts[0]
        
        return datetime.fromisoformat(value_str)
    except (ValueError, AttributeError):
        pass
    
    logger.debug(f"Failed to parse datetime: {value}")
    return None


def parse_iso_date(value: Any) -> Optional[date]:
    """
    Parse date string to date object.
    
    Supports formats:
    - "2026-02-05"
    - "2026/02/05"
    - "05-02-2026" (if unambiguous)
    
    Args:
        value: date, string, or other value
    
    Returns:
        date object or None if parsing fails
    
    Example:
        >>> d = parse_iso_date("2026-02-05")
        >>> d is not None
        True
    """
    if value is None:
        return None
    
    # Already a date
    if isinstance(value, date):
        return value
    
    # If it's a datetime, extract date
    if isinstance(value, datetime):
        return value.date()
    
    # Convert to string
    value_str = str(value).strip()
    
    if not value_str:
        return None
    
    # Try various date formats
    formats = [
        "%Y-%m-%d",     # 2026-02-05
        "%Y/%m/%d",     # 2026/02/05
        "%Y%m%d",       # 20260205
        "%d-%m-%Y",     # 05-02-2026
        "%d/%m/%Y",     # 05/02/2026
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(value_str, fmt)
            return dt.date()
        except ValueError:
            continue
    
    # Try ISO format
    try:
        return date.fromisoformat(value_str.split('T')[0])  # Handle datetime strings
    except (ValueError, AttributeError):
        pass
    
    logger.debug(f"Failed to parse date: {value}")
    return None


def ensure_date_str(value: Any, default: Optional[date] = None) -> str:
    """
    Convert any date input to YYYY-MM-DD string.
    
    Args:
        value: date, datetime, string, or other value
        default: Default date to use if parsing fails (None = today)
    
    Returns:
        Date string in YYYY-MM-DD format
    
    Example:
        >>> ensure_date_str("2026-02-05")
        '2026-02-05'
        >>> ensure_date_str(None) == today_iso()
        True
    """
    parsed = parse_iso_date(value)
    
    if parsed is not None:
        return parsed.isoformat()
    
    # Use default or today
    if default is not None:
        return default.isoformat() if isinstance(default, date) else str(default)
    
    return today_iso()


def ensure_datetime_str(value: Any, default: Optional[datetime] = None) -> str:
    """
    Convert any datetime input to ISO string.
    
    Args:
        value: datetime, string, or other value
        default: Default datetime to use if parsing fails (None = now)
    
    Returns:
        ISO datetime string with 'Z' suffix
    
    Example:
        >>> dt_str = ensure_datetime_str("2026-02-05T00:30:00Z")
        >>> dt_str.endswith('Z')
        True
    """
    parsed = parse_iso_datetime(value)
    
    if parsed is not None:
        return parsed.isoformat() + ("Z" if not parsed.isoformat().endswith("Z") else "")
    
    # Use default or now
    if default is not None:
        if isinstance(default, datetime):
            return default.isoformat() + "Z"
        return str(default)
    
    return utcnow_iso()


def minutes_between(a: Any, b: Any) -> Optional[int]:
    """
    Calculate minutes between two timestamps.
    
    Args:
        a: First timestamp (datetime, string, or other)
        b: Second timestamp (datetime, string, or other)
    
    Returns:
        Integer minutes difference (absolute value) or None if parsing fails
    
    Example:
        >>> t1 = "2026-02-05T00:00:00Z"
        >>> t2 = "2026-02-05T01:30:00Z"
        >>> minutes_between(t1, t2)
        90
    """
    dt_a = parse_iso_datetime(a)
    dt_b = parse_iso_datetime(b)
    
    if dt_a is None or dt_b is None:
        return None
    
    delta = abs(dt_b - dt_a)
    return int(delta.total_seconds() / 60)


def add_hours(value: Any, hours: int) -> str:
    """
    Add hours to a datetime.
    
    Args:
        value: datetime or string
        hours: Hours to add (can be negative)
    
    Returns:
        ISO datetime string
    
    Example:
        >>> result = add_hours("2026-02-05T00:00:00Z", 2)
        >>> "02:00" in result
        True
    """
    dt = parse_iso_datetime(value)
    
    if dt is None:
        dt = datetime.utcnow()
    
    new_dt = dt + timedelta(hours=hours)
    return new_dt.isoformat() + "Z"


def format_time_range(start: Any, end: Any) -> str:
    """
    Format time range as human-readable string.
    
    Args:
        start: Start time
        end: End time
    
    Returns:
        Formatted string like "09:00-11:00" or "2026-02-05 09:00 - 11:00"
    
    Example:
        >>> start = "2026-02-05T09:00:00Z"
        >>> end = "2026-02-05T11:00:00Z"
        >>> range_str = format_time_range(start, end)
        >>> "09:00" in range_str
        True
    """
    dt_start = parse_iso_datetime(start)
    dt_end = parse_iso_datetime(end)
    
    if dt_start is None or dt_end is None:
        return ""
    
    # Same day - show time range only
    if dt_start.date() == dt_end.date():
        return f"{dt_start.strftime('%H:%M')}-{dt_end.strftime('%H:%M')}"
    
    # Different days - show full range
    return f"{dt_start.strftime('%Y-%m-%d %H:%M')} - {dt_end.strftime('%Y-%m-%d %H:%M')}"


# Self-test examples (run when module is executed directly)
if __name__ == "__main__":
    print("Time Tool Self-Test")
    print("=" * 50)
    
    # Test utcnow_iso
    now = utcnow_iso()
    print(f"Current UTC time: {now}")
    assert now.endswith('Z'), "UTC time should end with Z"
    
    # Test today_iso
    today = today_iso()
    print(f"Today's date: {today}")
    assert len(today) == 10, "Date should be YYYY-MM-DD"
    
    # Test parse_iso_datetime
    test_dt = "2026-02-05T00:30:00Z"
    parsed = parse_iso_datetime(test_dt)
    print(f"Parsed datetime: {parsed}")
    assert parsed is not None, "Should parse valid ISO datetime"
    
    # Test parse_iso_date
    test_date = "2026-02-05"
    parsed_date = parse_iso_date(test_date)
    print(f"Parsed date: {parsed_date}")
    assert parsed_date is not None, "Should parse valid date"
    
    # Test ensure_date_str
    date_str = ensure_date_str("2026-02-05")
    print(f"Ensured date string: {date_str}")
    assert date_str == "2026-02-05", "Should return YYYY-MM-DD"
    
    # Test minutes_between
    t1 = "2026-02-05T00:00:00Z"
    t2 = "2026-02-05T01:30:00Z"
    mins = minutes_between(t1, t2)
    print(f"Minutes between {t1} and {t2}: {mins}")
    assert mins == 90, "Should calculate 90 minutes"
    
    # Test add_hours
    result = add_hours("2026-02-05T00:00:00Z", 2)
    print(f"Added 2 hours: {result}")
    assert "02:00" in result, "Should add 2 hours"
    
    # Test format_time_range
    range_str = format_time_range("2026-02-05T09:00:00Z", "2026-02-05T11:00:00Z")
    print(f"Formatted time range: {range_str}")
    assert "09:00" in range_str and "11:00" in range_str, "Should format time range"
    
    print("\n✅ All tests passed!")
