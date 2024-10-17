from datetime import datetime, timedelta
from croniter import croniter
import re

# Map AWS numeric day of week to croniter format (0-6)
aws_day_map = {
    '1': '0', '2': '1', '3': '2', '4': '3', '5': '4', '6': '5', '7': '6',
    'SUN': '0', 'MON': '1', 'TUE': '2', 'WED': '3', 'THU': '4', 'FRI': '5', 'SAT': '6'
}

def parse_eventbridge_expression(expression, occurrences=10):
    if expression.startswith("rate("):
        # Handle rate expression
        return get_next_rate_occurrences(expression, occurrences)
    elif expression.startswith("cron("):
        # Handle cron expression
        return get_next_cron_occurrences(expression, occurrences)
    elif expression.startswith("at("):
        # Handle at expression (one-time)
        return [parse_at_expression(expression)]
    else:
        raise ValueError("Unsupported EventBridge expression format")

def convert_day_of_week(cron_expr):
    """Convert AWS-style day-of-week in cron expression to croniter-compatible format."""
    cron_parts = cron_expr.split()
    day_of_week_part = cron_parts[4]
    
    # Replace numeric or string days with croniter format
    converted_days = [aws_day_map.get(day.strip(), day.strip()) for day in day_of_week_part.split(',')]
    cron_parts[4] = ','.join(converted_days)
    
    return " ".join(cron_parts)

def get_next_rate_occurrences(expression, occurrences):
    # Extract the rate interval (e.g., "rate(1 day)", "rate(3 hours)")
    rate_pattern = re.compile(r"rate\((\d+)\s(day|hour|minute|week)s?\)")
    match = rate_pattern.match(expression)
    
    if not match:
        raise ValueError("Invalid rate expression format")

    interval_value = int(match.group(1))
    interval_unit = match.group(2)
    
    # Map the interval unit to a timedelta
    if interval_unit == "day":
        delta = timedelta(days=interval_value)
    elif interval_unit == "hour":
        delta = timedelta(hours=interval_value)
    elif interval_unit == "minute":
        delta = timedelta(minutes=interval_value)
    elif interval_unit == "week":
        delta = timedelta(weeks=interval_value)
    else:
        raise ValueError("Unsupported interval unit in rate expression")
    
    # Generate the next n occurrences
    occurrences_list = []
    next_run_time = datetime.now()
    for _ in range(occurrences):
        next_run_time += delta
        occurrences_list.append(next_run_time)
    
    return occurrences_list

def get_next_cron_occurrences(expression, occurrences):
    # Remove 'cron(' and ')' to get the cron schedule string
    cron_expr = expression.replace("cron(", "").replace(")", "")
    cron_parts = cron_expr.split()
    
    if len(cron_parts) == 6:
        # Remove the year component to make it compatible with croniter
        cron_expr = " ".join(cron_parts[:5])

    # Convert AWS day-of-week to croniter-compatible format
    cron_expr = convert_day_of_week(cron_expr)

    # Initialize croniter and generate next n occurrences
    cron_iter = croniter(cron_expr, datetime.now())
    occurrences_list = [cron_iter.get_next(datetime) for _ in range(occurrences)]
    
    return occurrences_list

def parse_at_expression(expression):
    # Extract the date and time from the at expression
    at_pattern = re.compile(r"at\(([\d-]+)T([\d:]+)\)")
    match = at_pattern.match(expression)
    
    if not match:
        raise ValueError("Invalid at expression format")
    
    date_part = match.group(1)
    time_part = match.group(2)
    next_run_time = datetime.strptime(f"{date_part}T{time_part}", "%Y-%m-%dT%H:%M:%S")
    
    return next_run_time

# Example usage
expressions = [
    "rate(1 day)",
    "rate(3 hours)",
    "cron(0 11 ? * 2,4 *)",
    "cron(0 9 1 * 3 *)",  # Third day of each month
    "cron(0 12 ? * 2,4 *)",
    "at(2024-10-14T11:00:00)"
]

for expr in expressions:
    try:
        next_run_times = parse_eventbridge_expression(expr, occurrences=10)
        print(f"Expression: {expr}")
        for i, run_time in enumerate(next_run_times, start=1):
            print(f"  Run {i}: {run_time}")
    except ValueError as e:
        print(f"Error parsing expression {expr}: {e}")
