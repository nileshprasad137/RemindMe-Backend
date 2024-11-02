import os
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
            "   that describes when the reminder should start (e.g., 'tomorrow,' 'next week').\n"
            "   Try to understand whether the reminder is for a specific day / week or it repeats recurringly."
            "   Try to extract time at which you need to remind else default to 11am."
            "   Try to understand phrases like alternate days."
            "2. Populate 'repeat_frequency' directly with integer values if provided, for fields like 'daily', 'weekly', etc.\n"
            "   - Do not introduce new keys such as 'interval'. Instead, set 'daily': 2 for 'every 2 days'.\n"
            "3. For specific days, use 'selected_days_of_week' as a list of integers (e.g., [1, 4] for Monday and Thursday), "
            "and 'selected_days_of_month' as a list of integers for days of the month (e.g., [1, 15]).\n\n"
            "4. **Tags Extraction**:\n"
            "   - Identify single or double-word tags from the reminder that represent the main topics or categories.\n\n"
            
            "Output the information in structured JSON with fields: task, start_date, end_date, time, repeat_frequency, and tags.\n\n"
            
            "{format_instructions}\n\n"
            
            "Reminder Text: {query}"
        ),
        input_variables=["query"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
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
    return parsed_data


def generate_eventbridge_expression(task, start_date, time_str, repeat_frequency):
    # Convert start_date and time_str to datetime format
    start_datetime = datetime.strptime(f"{start_date} {time_str}", "%d-%m-%Y %I:%M %p")
    start_time = f"{start_datetime.minute} {start_datetime.hour}"

    # Determine the EventBridge expression based on frequency
    if repeat_frequency.get("daily"):
        days = repeat_frequency["daily"]
        unit = "day" if days == 1 else "days"
        expression = f"rate({days} {unit})"
    
    elif repeat_frequency.get("hourly"):
        hours = repeat_frequency["hourly"]
        unit = "hour" if hours == 1 else "hours"
        expression = f"rate({hours} {unit})"
    
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
        selected_days_of_month = repeat_frequency.get("selected_days_of_month", [])
        if selected_days_of_month:
            day_str = ",".join(map(str, selected_days_of_month))
            expression = f"cron({start_time} {day_str} * ? *)"
        else:
            return None
    
    elif repeat_frequency.get("monthly"):
        # Generate a cron expression for monthly schedules
        selected_days_of_month = repeat_frequency.get("selected_days_of_month", [])
        if selected_days_of_month:
            day_str = ",".join(map(str, selected_days_of_month))
            expression = f"cron({start_time} {day_str} * ? *)"
        else:
            # Default to the start date's day of the month
            expression = f"cron({start_time} {start_datetime.day} * ? *)"
    
    elif repeat_frequency.get("yearly"):
        # Yearly schedule with a specific month and day
        expression = f"cron({start_time} {start_datetime.day} {start_datetime.month} ? *)"
    
    else:
        # One-time expression for a specific date and time
        expression = f"at({start_datetime.strftime('%Y-%m-%dT%H:%M:%S')})"
    
    print(f"Generated EventBridge Expression: {expression}")
    return expression


def generate_reminder_summary(parsed_data):
    task = parsed_data['task']
    start_date = parsed_data['start_date']
    frequency = parsed_data['repeat_frequency']
    time_str = parsed_data['time']
    # start_date_phrase = parsed_data['start_date_phrase']
    # Determine the frequency description
    if frequency.get('daily'):
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
