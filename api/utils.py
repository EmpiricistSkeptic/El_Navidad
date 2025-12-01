from datetime import date

from django.utils import timezone

STORY_DAYS_TOTAL = 9
STORY_START_MONTH = 12
STORY_START_DAY = 24

def get_current_day_index() -> int:

    today=timezone.localdate()

    if today.month == 1:
        start_year = today.year
    else:
        start_year = today.year
    
    start_date = date(start_year, STORY_START_MONTH, STORY_START_DAY)
    delta = (today - start_date).days

    if delta < 0:
        return 0
    if delta >= STORY_DAYS_TOTAL:
        return STORY_DAYS_TOTAL - 1
    return delta
    

