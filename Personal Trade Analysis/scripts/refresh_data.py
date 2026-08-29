now = datetime.now(timezone.utc)

month_start = now.replace(
    day=1,
    hour=0,
    minute=0,
    second=0,
    microsecond=0
)