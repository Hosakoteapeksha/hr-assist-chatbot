"""Government of India gazetted (closed) holidays for Central Government offices.
Sources: DoPT O.M. F.No.12/2/2023-JCA dated 03.07.2025 (2026) and dated 16.07.2026 (2027).
Used for the Holidays page and to count working days in leave requests."""
from datetime import date, timedelta

HOLIDAYS = {
 2026: [("Republic Day","2026-01-26","Monday"),("Holi","2026-03-04","Wednesday"),("Id-ul-Fitr","2026-03-21","Saturday"),
        ("Ram Navami","2026-03-26","Thursday"),("Mahavir Jayanti","2026-03-31","Tuesday"),("Good Friday","2026-04-03","Friday"),
        ("Buddha Purnima","2026-05-01","Friday"),("Id-ul-Zuha (Bakrid)","2026-05-27","Wednesday"),("Muharram","2026-06-26","Friday"),
        ("Independence Day","2026-08-15","Saturday"),("Milad-un-Nabi / Id-e-Milad (Birthday of Prophet Mohammad)","2026-08-26","Wednesday"),
        ("Janmashtami (Vaishnava)","2026-09-04","Friday"),("Mahatma Gandhi's Birthday (Gandhi Jayanti)","2026-10-02","Friday"),
        ("Dussehra (Vijaya Dashami)","2026-10-20","Tuesday"),("Diwali (Deepavali)","2026-11-08","Sunday"),
        ("Guru Nanak's Birthday (Guru Nanak Jayanti)","2026-11-24","Tuesday"),("Christmas Day","2026-12-25","Friday")],
 2027: [("Republic Day","2027-01-26","Tuesday"),("Id-ul-Fitr","2027-03-10","Wednesday"),("Holi","2027-03-23","Tuesday"),
        ("Good Friday","2027-03-26","Friday"),("Ram Navami","2027-04-15","Thursday"),("Mahavir Jayanti","2027-04-19","Monday"),
        ("Id-ul-Zuha (Bakrid)","2027-05-17","Monday"),("Buddha Purnima","2027-05-20","Thursday"),("Muharram","2027-06-16","Wednesday"),
        ("Independence Day","2027-08-15","Sunday"),("Milad-un-Nabi / Id-e-Milad (Birthday of Prophet Mohammad)","2027-08-15","Sunday"),
        ("Janmashtami (Vaishnava)","2027-08-25","Wednesday"),("Mahatma Gandhi's Birthday (Gandhi Jayanti)","2027-10-02","Saturday"),
        ("Dussehra (Vijaya Dashami)","2027-10-09","Saturday"),("Diwali (Deepavali)","2027-10-29","Friday"),
        ("Guru Nanak's Birthday (Guru Nanak Jayanti)","2027-11-14","Sunday"),("Christmas Day","2027-12-25","Saturday")],
}


def holiday_list(year=None):
    """[(date, name, weekday)] sorted by date."""
    rows = []
    for y, items in HOLIDAYS.items():
        if year and y != year:
            continue
        for name, d, day in items:
            rows.append((date.fromisoformat(d), name, day))
    return sorted(rows)


def holiday_dates():
    return {d for d, _, _ in holiday_list()}


def upcoming_holidays(today=None, limit=5):
    today = today or date.today()
    return [h for h in holiday_list() if h[0] >= today][:limit]


def working_days(start, end):
    """Days between start and end (inclusive), excluding Saturdays, Sundays and public holidays."""
    if not start or not end or end < start:
        return 0
    off = holiday_dates()
    count, d = 0, start
    while d <= end:
        if d.weekday() < 5 and d not in off:
            count += 1
        d += timedelta(days=1)
    return count
