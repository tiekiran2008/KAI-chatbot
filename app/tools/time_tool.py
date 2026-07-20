import datetime

def get_current_time() -> str:
    """
    Returns the current date and time.
    Use this tool when you need to know the current time, date, day of the week, or timezone.
    """
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")
