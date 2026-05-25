from datetime import date
from django.utils import timezone

STORY_DAYS_TOTAL = 9
STORY_START_MONTH = 12
STORY_START_DAY = 24

def get_current_day_index() -> int:
    return STORY_DAYS_TOTAL - 1
    

