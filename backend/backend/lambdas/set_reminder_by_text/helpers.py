import os
import pytz
import dateparser
import parsedatetime
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, List
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# Load environment variables from .env
load_dotenv()

def sanitize_time_format(time_str):
    """
    Ensures the time string is in the correct format for parsing.
    
    Args:
        time_str (str): Input time string (e.g., '5:38 p.m.')

    Returns:
        str: Sanitized time string (e.g., '5:38 PM')
    """
    return time_str.strip().replace('.', '').upper()

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

day_of_week_mapping_string = ", ".join([f"{key}: {value}" for key, value in day_of_week_map.items()])


def get_reminder_schedule_json(reminder_text: str):
    """ Returns the reminder json with schedule details

    Args:
        reminder_text (str): Natural language text from which reminder details need to be extracted.

    Returns:
        dict: Details of the processed reminder which contains reminder frequency and other reminder details.
    """
    # Set up the OpenAI model
    model = ChatOpenAI(temperature=0, openai_api_key=os.getenv("OPENAI_API_KEY"), model="gpt-3.5-turbo")
    # Set up the JSON output parser with the Reminder model
    parser = JsonOutputParser(pydantic_object=Reminder)
    # Define the prompt template with enhanced instructions
    prompt = PromptTemplate(
        template=(
            "You are a highly intelligent assistant that parses reminder requests with dates, times, and repeat frequencies "
            "in various formats. Follow these instructions carefully to extract details without introducing additional fields.\n\n"
            
            "Instructions:\n"
            "1. **Interpretation of Dates and Times**:\n"
            "   - Provide a relative date phrase for 'start_date_phrase' "
            "     that describes when the reminder should start (e.g., 'tomorrow,' 'next week').\n"
            "   - Understand whether the reminder is for a specific day/week or it repeats recurringly.\n"
            "   - Extract the time at which the reminder is needed; if no specific time is provided, default to 11:00 AM.\n"
            "   - For ambiguous or relative time-of-day phrases like:\n"
            "     - 'morning,' map to 8:00 AM.\n"
            "     - 'afternoon,' map to 2:00 PM.\n"
            "     - 'evening,' map to 6:00 PM.\n"
            "     - 'night,' map to 9:00 PM.\n"
            "   - Translate phrases like 'alternate days,' 'weekdays,' or 'weekends' into structured formats.\n\n"
            
            "2. **Day of the Week Mapping**:\n"
            "   - Use the following mapping for days of the week when interpreting selected days:\n"
            "     {day_of_week_mapping_string}\n"
            "   - For example, 'Sunday' maps to 1, 'Wednesday' maps to 4, and so on.\n\n"
            
            "3. Populate 'repeat_frequency' directly with integer values if provided, for fields like 'daily', 'weekly', etc.\n"
            "   - Do not introduce new keys such as 'interval'. Instead, set 'daily': 2 for 'every 2 days'.\n\n"
            
            "4. For specific days, use 'selected_days_of_week' as a list of integers (e.g., [1, 4] for Sunday and Wednesday), "
            "   and 'selected_days_of_month' as a list of integers for days of the month (e.g., [1, 15]).\n\n"
            
            "5. **Tags Extraction**:\n"
            "   - Identify single or double-word tags from the reminder that represent the main topics or categories.\n\n"
            
            "Output the information in structured JSON with fields: task, start_date, end_date, time, repeat_frequency, and tags.\n\n"
            
            "{format_instructions}\n\n"
            
            "Reminder Text: {query}"
        ),
        input_variables=["query"],
        partial_variables={
            "format_instructions": parser.get_format_instructions(),
            "day_of_week_mapping_string": day_of_week_mapping_string,
        },
    )
    # Create a chain that combines the prompt, model, and parser
    chain = prompt | model | parser
    # Pass the reminder text to the chain for processing
    parsed_data = chain.invoke({"query": reminder_text})
    # Extract the start date phrase and time from parsed data
    start_date_phrase = parsed_data.get('start_date_phrase') or "today"
    # Process start_date using dateparser
    start_date = dateparser.parse(
        start_date_phrase,
        settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': datetime.now()}
    )
    if not start_date:
        # Fallback to parsedatetime if dateparser fails
        cal = parsedatetime.Calendar()
        time_struct, parse_status = cal.parse(start_date_phrase, datetime.now())
        start_date = datetime(*time_struct[:6]) if parse_status == 1 else datetime.now().date()

    parsed_data['start_date'] = start_date.strftime('%d-%m-%Y') if start_date else datetime.now().strftime('%d-%m-%Y')
    # Filter out None values at the top level
    parsed_data = {key: value for key, value in parsed_data.items() if value is not None}
    # Remove None values specifically from within repeat_frequency
    if 'repeat_frequency' in parsed_data:
        parsed_data['repeat_frequency'] = {
            k: v for k, v in parsed_data['repeat_frequency'].items() if v is not None
        }
    return parsed_data


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
        expression = f"at({start_datetime_utc.strftime('%Y-%m-%dT%H:%M:%S')})"
    
    elif repeat_frequency.get("hourly"):
        # Use rate expression for hourly schedules
        hours = repeat_frequency["hourly"]
        unit = "hour" if hours == 1 else "hours"
        expression = f"rate({hours} {unit})"

    elif repeat_frequency.get("weekly"):
        # Convert weeks to days for the rate expression
        weeks = repeat_frequency["weekly"]
        days = weeks * 7  # Convert weeks to days
        unit = "day" if days == 1 else "days"
        expression = f"rate({days} {unit})"
    
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
