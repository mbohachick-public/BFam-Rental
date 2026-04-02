from datetime import date, timedelta


def iter_days_inclusive(start: date, end: date) -> list[date]:
    if end < start:
        return []
    out: list[date] = []
    d = start
    while d <= end:
        out.append(d)
        d += timedelta(days=1)
    return out


def next_day(d: date) -> date:
    return d + timedelta(days=1)
