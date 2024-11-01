import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

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
    
    elif repeat_frequency.get("weekly"):
        # Convert weeks to days for the rate expression
        weeks = repeat_frequency["weekly"]
        days = weeks * 7  # Convert weeks to days
        unit = "day" if days == 1 else "days"
        expression = f"rate({days} {unit})"
    
    elif repeat_frequency.get("monthly"):
        # Generate a cron expression for monthly schedules
        selected_days_of_month = repeat_frequency.get("selected_days_of_month", [])
        if selected_days_of_month:
            day_str = ",".join(map(str, selected_days_of_month))
            expression = f"cron({start_time} {day_str} * ? *)"
        else:
            # Default to the start date's day of the month
            expression = f"cron({start_time} {start_datetime.day} * ? *)"

    elif repeat_frequency.get("selected_days_of_month"):
        selected_days_of_month = repeat_frequency.get("selected_days_of_month", [])
        if selected_days_of_month:
            day_str = ",".join(map(str, selected_days_of_month))
            expression = f"cron({start_time} {day_str} * ? *)"
        else:
            return None

    elif repeat_frequency.get("selected_days_of_week"):
        # Use cron for specific days of the week
        selected_days_of_week = repeat_frequency["selected_days_of_week"]
        day_map = {1: 'SUN', 2: 'MON', 3: 'TUE', 4: 'WED', 5: 'THU', 6: 'FRI', 7: 'SAT'}
        days = [day_map[day] for day in selected_days_of_week]
        day_str = ",".join(days)
        expression = f"cron({start_time} ? * {day_str} *)"
    
    elif repeat_frequency.get("yearly"):
        # Yearly schedule with a specific month and day
        expression = f"cron({start_time} {start_datetime.day} {start_datetime.month} ? *)"
    
    else:
        # One-time expression for a specific date and time
        expression = f"at({start_datetime.strftime('%Y-%m-%dT%H:%M:%S')})"
    
    print(f"Generated EventBridge Expression: {expression}")
    return expression

# Example usage
# parsed_data = {
#     "task": "team meeting",
#     "start_date": "12-11-2024",
#     "time": "11:00 AM",
#     "repeat_frequency": {
#         "daily": 1,
#         # "weekly": 1,
#         # "monthly": 1,
#         # "yearly": 1,
#         # "hourly": 5,
#         # "selected_days_of_week": [2, 4]  # Monday, Wednesday
#         # "selected_days_of_month": [2, 4]  # 2nd and 4th of month
#     }
# }

parsed_data = {'task': 'pay rent', 'start_date': '01-11-2024', 'end_date': '01-11-2025', 'time': '10:00 AM', 'repeat_frequency': {'daily': None, 'weekly': None, 'monthly': None, 'yearly': None, 'hourly': None, 'selected_days_of_week': None, 'selected_days_of_month': [1]}, 'tags': ['bills', 'finance']}
generate_eventbridge_expression(
    task=parsed_data["task"],
    start_date=parsed_data["start_date"],
    time_str=parsed_data["time"],
    repeat_frequency=parsed_data["repeat_frequency"]
)
