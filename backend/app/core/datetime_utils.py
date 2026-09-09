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
