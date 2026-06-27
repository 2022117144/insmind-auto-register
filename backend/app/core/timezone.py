from datetime import datetime, timedelta, timezone

# Calculate Beijing Time (UTC+8) based on absolute offset
BEIJING_TZ = timezone(timedelta(hours=8))

def get_beijing_time() -> datetime:
    """
    Returns the current datetime in Beijing Time (UTC+8).
    This function should be used as the default value for all SQLAlchemy DateTime columns
    to prevent timezone gaps when displaying and filtering on the frontend.
    """
    # Create an aware UTC datetime and then astimezone to Beijing Time
    return datetime.now(timezone.utc).astimezone(BEIJING_TZ).replace(tzinfo=None)
