from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "UTC"


def get_nice_time(timezone_name: str = DEFAULT_TIMEZONE) -> str:
    now = datetime.now(ZoneInfo(timezone_name))
    # Filesystem-friendly timestamp used in run names and dump filenames.
    return now.strftime("%Y-%m-%dT%H_%M_%S")
