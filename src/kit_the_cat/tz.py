"""Game time zone: Europe/Kyiv.

Uses the system tz database when present; otherwise (Pyodide/browser, minimal containers) a built-in rule:
EET (UTC+2) / EEST (UTC+3), summer time from the last Sunday of March 01:00 UTC to the last Sunday of October.
"""
from datetime import datetime, timedelta, tzinfo

_STD, _DST = timedelta(hours=2), timedelta(hours=3)


def _last_sunday(year: int, month: int) -> datetime:
    d = datetime(year, month + 1, 1) - timedelta(days=1) if month < 12 else datetime(year, 12, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _is_summer_utc(utc: datetime) -> bool:
    start = _last_sunday(utc.year, 3).replace(hour=1)
    end = _last_sunday(utc.year, 10).replace(hour=1)
    return start <= utc.replace(tzinfo=None) < end


class _Kyiv(tzinfo):
    def utcoffset(self, dt):
        if dt is None:
            return _STD
        # dt is local wall time: approximate with the standard offset to find the UTC instant
        return _DST if _is_summer_utc(dt.replace(tzinfo=None) - _STD) else _STD

    def dst(self, dt):
        return self.utcoffset(dt) - _STD

    def tzname(self, dt):
        return "EEST" if self.dst(dt) else "EET"

    def fromutc(self, dt):
        utc = dt.replace(tzinfo=None)
        return (utc + (_DST if _is_summer_utc(utc) else _STD)).replace(tzinfo=self)


def _zone() -> tzinfo:
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Kyiv")
    except Exception:  # no tzdata (browser) — use the built-in rule
        return _Kyiv()


TZ = _zone()
