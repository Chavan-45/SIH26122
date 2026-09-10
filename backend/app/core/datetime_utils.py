from datetime import datetime, date
import zoneinfo
from app.core.config import settings


def get_tz():
    """Returns the ZoneInfo instance based on settings.APP_TIMEZONE."""
    try:
        return zoneinfo.ZoneInfo(settings.APP_TIMEZONE)
    except Exception:
        return zoneinfo.ZoneInfo("UTC")


def get_today_date() -> date:
    """Returns today's date in the configured APP_TIMEZONE."""
    tz = get_tz()
    return datetime.now(tz).date()


def get_now_datetime() -> datetime:
    """Returns the current timezone-aware datetime in APP_TIMEZONE."""
    tz = get_tz()
    return datetime.now(tz)


def get_yesterday_date() -> date:
    """Returns yesterday's date in APP_TIMEZONE."""
    from datetime import timedelta
    return get_today_date() - timedelta(days=1)


def get_last_7_days_range() -> tuple[date, date]:
    """Returns (start_date, end_date) for the rolling 7-day window ending today."""
    from datetime import timedelta
    today = get_today_date()
    return today - timedelta(days=7), today


def get_last_week_range() -> tuple[date, date]:
    """
    Returns (monday, sunday) for the previous calendar week (Monday to Sunday).
    Consistent standard: Monday = 0, Sunday = 6.
    """
    from datetime import timedelta
    today = get_today_date()
    # today.weekday(): Monday is 0, Sunday is 6
    # Days since last week's Monday = today.weekday() + 7
    # Days since last week's Sunday = today.weekday() + 1
    last_week_monday = today - timedelta(days=today.weekday() + 7)
    last_week_sunday = today - timedelta(days=today.weekday() + 1)
    return last_week_monday, last_week_sunday

