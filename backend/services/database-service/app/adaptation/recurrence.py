"""Finite recurrence plans anchored to the original date, not shifted dates."""
from calendar import monthrange
from datetime import timedelta

from app.adaptation.rules import next_business_day


def recurrence_dates(start, frequency="once", count=1, *, interval_days=None):
    if frequency not in {"once", "weekly", "monthly", "custom"} or not 1 <= count <= 52:
        raise ValueError("Укажите периодичность и от 1 до 52 повторений")
    if frequency == "once" and count != 1:
        raise ValueError("Для однократной точки число повторений должно быть 1")
    if frequency == "custom" and not (isinstance(interval_days, int) and 1 <= interval_days <= 365):
        raise ValueError("Для произвольной периодичности укажите интервал от 1 до 365 дней")
    result = []
    for index in range(count):
        if frequency == "monthly":
            year, month = divmod(start.year * 12 + start.month - 1 + index, 12)
            scheduled = start.replace(year=year, month=month + 1, day=min(start.day, monthrange(year, month + 1)[1]))
        elif frequency == "custom":
            scheduled = start + timedelta(days=index * interval_days)
        else:
            scheduled = start + timedelta(weeks=index)
        result.append(next_business_day(scheduled))
    return result
