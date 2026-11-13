"""Date/time spans with explicit calendar validation and source precision."""

import datetime as dt
import re

DATE = r"(?<![\w\d])(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4})(?![\w\d])"
TIME = r"(?<![\w\d.,])\d{1,2}:\d{2}(?::\d{2})?(?![\w\d.,])"
CONTEXT_TIME = r"(?<![\w\d.,])\d{1,2}(?:[:.h])\d{2}(?::\d{2})?(?![\w\d.,])"


def dates(text):
    return list(re.finditer(DATE, text))


def times(text):
    return list(re.finditer(CONTEXT_TIME if dates(text) else TIME, text))


def parse(text):
    ds, ts = dates(text), times(text)
    if len(ds) != 1 or len(ts) > 1:
        return None, None, ["ambiguous_datetime"]
    try:
        parts = re.split(r"[/.-]", ds[0].group())
        year, month, day = map(int, parts if len(parts[0]) == 4 else reversed(parts))
        date = dt.date(year, month, day)
        if not ts:
            return date.isoformat(), "date", ["time_missing"]
        pieces = re.split(r"[:.h]", ts[0].group())
        hour, minute = map(int, pieces[:2])
        second = int(pieces[2]) if len(pieces) == 3 else 0
        value = dt.datetime.combine(date, dt.time(hour, minute, second))
        precision = "second" if len(pieces) == 3 else "minute"
        return (
            value.isoformat(timespec="seconds" if precision == "second" else "minutes"),
            precision,
            [],
        )
    except ValueError:
        return None, None, ["invalid_datetime"]
