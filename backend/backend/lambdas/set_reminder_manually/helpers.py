from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, List
import pytz

# Load environment variables from .env
load_dotenv()

def get_ordinal_suffix(day):
    if 11 <= day <= 13:  # Special case for 11th, 12th, and 13th
        return f"{day}th"
    last_digit = day % 10
    if last_digit == 1:
        return f"{day}st"
    elif last_digit == 2:
        return f"{day}nd"
    elif last_digit == 3:
        return f"{day}rd"
    else:
        return f"{day}th"

# Define the data structure for repeat frequency
class RepeatFrequency(BaseModel):
    daily: Optional[int] = None
    weekly: Optional[int] = None
    monthly: Optional[int] = None
    yearly: Optional[int] = None
    hourly: Optional[int] = None
    selected_days_of_week: Optional[List[int]] = None
    selected_days_of_month: Optional[List[int]] = None

class Reminder(BaseModel):
    task: str = Field(description="The action or task to be reminded of.")
    start_date_phrase: str = Field(description="The relative date phrase indicating when the reminder should start (e.g., today, tomorrow, next week).")
    end_date: Optional[str] = Field(description="The end date of the reminder in dd-mm-yyyy format.")
    time: Optional[str] = Field(default="11:00 AM", description="The specific time of day for the reminder.")
    repeat_frequency: RepeatFrequency = Field(default_factory=RepeatFrequency, description="Repeat frequency settings.")
    tags: List[str] = Field(default_factory=list, description="Tags associated with the reminder for easy categorization.")


day_of_week_map = {
    1: "Sunday",
    2: "Monday",
    3: "Tuesday",
    4: "Wednesday",
    5: "Thursday",
    6: "Friday",
    7: "Saturday"
}


def sanitize_time_format(time_str):
    """
    Ensures the time string is in the correct format for parsing.
    
    Args:
        time_str (str): Input time string (e.g., '5:38 p.m.')

    Returns:
        str: Sanitized time string (e.g., '5:38 PM')
    """
    return time_str.strip().replace('.', '').upper()


def generate_eventbridge_expression(start_date, time_str, repeat_frequency, timezone="Asia/Kolkata"):
    """
    Generates EventBridge schedule expression in UTC by converting input datetime to UTC.

    Parameters:
    - start_date (str): Date in the format "dd-mm-yyyy"
    - time_str (str): Time in the format "hh:mm AM/PM"
    - repeat_frequency (dict): Frequency of the schedule (e.g., daily, weekly, etc.)
    - timezone (str): Timezone of the input datetime (default is Asia/Kolkata)

    Returns:
    - str: EventBridge schedule expression in UTC
    """
    # Sanitize the time string
    sanitized_time = sanitize_time_format(time_str)
    
    # Convert start_date and sanitized_time to datetime format
    local_timezone = pytz.timezone(timezone)
    start_datetime_local = datetime.strptime(f"{start_date} {sanitized_time}", "%d-%m-%Y %I:%M %p")
    start_datetime_local = local_timezone.localize(start_datetime_local)

    # Convert to UTC
    start_datetime_utc = start_datetime_local.astimezone(pytz.utc)
    start_time = f"{start_datetime_utc.minute} {start_datetime_utc.hour}"

    # Determine the EventBridge expression based on frequency
    if not repeat_frequency:
        # One-time expression for a specific date and time in UTC
        expression = f"at({start_datetime_local.strftime('%Y-%m-%dT%H:%M:%S')})"
    
    elif repeat_frequency.get("hourly"):
        # Use rate expression for hourly schedules
        hours = repeat_frequency["hourly"]
        unit = "hour" if hours == 1 else "hours"
        expression = f"rate({hours} {unit})"
    
    elif repeat_frequency.get("daily"):
        # Use cron for daily schedules with interval
        interval = repeat_frequency["daily"]
        if interval == 1:
            expression = f"cron({start_time} * * ? *)"  # Every day
        else:
            expression = f"cron({start_time} 1/{interval} * ? *)"  # Every N days
    
    elif repeat_frequency.get("selected_days_of_week"):
        # Use cron for specific days of the week
        selected_days_of_week = repeat_frequency["selected_days_of_week"]
        day_map = {1: 'SUN', 2: 'MON', 3: 'TUE', 4: 'WED', 5: 'THU', 6: 'FRI', 7: 'SAT'}
        days = [day_map[day] for day in selected_days_of_week]
        day_str = ",".join(days)
        expression = f"cron({start_time} ? * {day_str} *)"
    
    elif repeat_frequency.get("weekly"):
        # Convert weeks to days for the rate expression
        weeks = repeat_frequency["weekly"]
        days = weeks * 7  # Convert weeks to days
        unit = "day" if days == 1 else "days"
        expression = f"rate({days} {unit})"
    
    elif repeat_frequency.get("selected_days_of_month"):
        # Use cron for specific days of the month
        selected_days_of_month = repeat_frequency["selected_days_of_month"]
        if selected_days_of_month:
            day_str = ",".join(map(str, selected_days_of_month))
            expression = f"cron({start_time} {day_str} * ? *)"
        else:
            return None
    
    elif repeat_frequency.get("monthly"):
        # Use cron for monthly schedules
        interval = repeat_frequency["monthly"]
        if interval == 1:
            expression = f"cron({start_time} {start_datetime_utc.day} * ? *)"
        else:
            expression = f"cron({start_time} {start_datetime_utc.day} 1/{interval} ? *)"
    
    elif repeat_frequency.get("yearly"):
        # Use cron for yearly schedules
        expression = f"cron({start_time} {start_datetime_utc.day} {start_datetime_utc.month} ? *)"
    
    else:
        # One-time expression for a specific date and time
        expression = f"at({start_datetime_utc.strftime('%Y-%m-%dT%H:%M:%S')})"
    
    print(f"Generated EventBridge Expression (UTC): {expression}")
    return expression


def generate_reminder_summary(parsed_data):
    task = parsed_data['task']
    start_date = parsed_data['start_date']
    frequency = parsed_data.get('repeat_frequency') or None
    time_str = parsed_data['time']
    # start_date_phrase = parsed_data['start_date_phrase']
    # Determine the frequency description
    if not frequency:
        frequency_desc = f"on {start_date} at {time_str}"
    elif frequency.get('daily'):
        frequency_desc = f"every {frequency['daily']} day(s)"
    elif frequency.get('selected_days_of_week'):
        days = [day_of_week_map[day] for day in frequency['selected_days_of_week']]
        frequency_desc = f"on {', '.join(days)}"
    elif frequency.get('selected_days_of_month'):
        days = [get_ordinal_suffix(day) for day in frequency['selected_days_of_month']]
        frequency_desc = f"every {', '.join(days)} of the month"
    elif frequency.get('weekly'):
        frequency_desc = f"every {frequency['weekly']} week(s)"
    elif frequency.get('monthly'):
        frequency_desc = f"every {frequency['monthly']} month(s)"
    elif frequency.get('yearly'):
        frequency_desc = f"every {frequency['yearly']} year(s)"
    elif frequency.get('hourly'):
        frequency_desc = f"every {frequency['hourly']} hour(s)"
    else:
        frequency_desc = f"on {start_date} at {time_str}"
    # Create the summary sentence
    summary = f"I will remind you to {task} {frequency_desc}"
    return summary
