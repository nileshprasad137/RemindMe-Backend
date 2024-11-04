import os
import json
import boto3
import re
from datetime import datetime, timedelta
from croniter import croniter
from decimal import Decimal

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
REMINDERS_TABLE_NAME = os.environ["REMINDERS_TABLE_NAME"]

# AWS Day-of-week to croniter mapping
aws_day_map = {
    '1': '0', '2': '1', '3': '2', '4': '3', '5': '4', '6': '5', '7': '6',
    'SUN': '0', 'MON': '1', 'TUE': '2', 'WED': '3', 'THU': '4', 'FRI': '5', 'SAT': '6'
}

def parse_eventbridge_expression(expression, occurrences=3):
    """Parses EventBridge expressions to generate the next run times."""
    if expression.startswith("rate("):
        return get_next_rate_occurrences(expression, occurrences)
    elif expression.startswith("cron("):
        return get_next_cron_occurrences(expression, occurrences)
    elif expression.startswith("at("):
        return [parse_at_expression(expression)]
    else:
        raise ValueError("Unsupported EventBridge expression format")

def convert_day_of_week(cron_expr):
    cron_parts = cron_expr.split()
    day_of_week_part = cron_parts[4]
    converted_days = [aws_day_map.get(day.strip(), day.strip()) for day in day_of_week_part.split(',')]
    cron_parts[4] = ','.join(converted_days)
    return " ".join(cron_parts)

def get_next_rate_occurrences(expression, occurrences):
    rate_pattern = re.compile(r"rate\((\d+)\s(day|hour|minute|week)s?\)")
    match = rate_pattern.match(expression)
    
    if not match:
        raise ValueError("Invalid rate expression format")

    interval_value = int(match.group(1))
    interval_unit = match.group(2)
    delta = timedelta(days=interval_value) if interval_unit == "day" else \
            timedelta(hours=interval_value) if interval_unit == "hour" else \
            timedelta(minutes=interval_value) if interval_unit == "minute" else \
            timedelta(weeks=interval_value)

    occurrences_list = []
    next_run_time = datetime.now()
    for _ in range(occurrences):
        next_run_time += delta
        occurrences_list.append(next_run_time)
    
    return occurrences_list

def get_next_cron_occurrences(expression, occurrences):
    cron_expr = expression.replace("cron(", "").replace(")", "")
    cron_parts = cron_expr.split()
    if len(cron_parts) == 6:
        cron_expr = " ".join(cron_parts[:5])
    cron_expr = convert_day_of_week(cron_expr)
    cron_iter = croniter(cron_expr, datetime.now())
    return [cron_iter.get_next(datetime) for _ in range(occurrences)]

def parse_at_expression(expression):
    at_pattern = re.compile(r"at\(([\d-]+)T([\d:]+)\)")
    match = at_pattern.match(expression)
    
    if not match:
        raise ValueError("Invalid at expression format")
    
    date_part = match.group(1)
    time_part = match.group(2)
    return datetime.strptime(f"{date_part}T{time_part}", "%Y-%m-%dT%H:%M:%S")

def convert_decimal(obj):
    """Convert DynamoDB Decimal types to int or float for JSON serialization."""
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def handler(event, context):
    try:
        # Parse device_id, filter, and schedule inclusion flag from the request
        query_params = event.get("queryStringParameters", {})
        device_id = query_params.get("device_id")
        filter_type = query_params.get("filter", "all")  # Options: 'all', 'past', 'upcoming'
        include_schedule = query_params.get("include_schedule", "false").lower() == "true"

        if not device_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "device_id is required"})
            }

        # Prepare query parameters based on filter_type
        reminders_table = dynamodb.Table(REMINDERS_TABLE_NAME)
        filter_expression = None

        if filter_type == "past":
            filter_expression = boto3.dynamodb.conditions.Attr("is_completed").eq(True)
        elif filter_type == "upcoming":
            # Check for incomplete items (treat missing or null is_completed as False)
            filter_expression = boto3.dynamodb.conditions.Attr("is_completed").not_exists() | boto3.dynamodb.conditions.Attr("is_completed").eq(False)

        # Query DynamoDB based on the filter type
        if filter_expression:
            response = reminders_table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"CUSTOMER#{device_id}"),
                FilterExpression=filter_expression,
                ScanIndexForward=False
            )
        else:
            response = reminders_table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"CUSTOMER#{device_id}"),
                ScanIndexForward=False
            )

        reminders = response.get("Items", [])
        response_data = {"past": [], "upcoming": []}
        current_date = datetime.now().date()

        # Process reminders, optionally retrieving schedules for upcoming reminders
        for reminder in reminders:
            reminder = convert_decimal(reminder)  # Convert any Decimal fields to int/float
            is_completed = reminder.get("is_completed", False)
            end_date_str = reminder.get("end_date", None)
            reminder_data = reminder.copy()

            # Check if the reminder is past based on the end_date
            if end_date_str and end_date_str != "None":
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                is_past = end_date < current_date
            else:
                is_past = is_completed

            if include_schedule and not is_past:
                # Retrieve and parse the EventBridge schedule expression for upcoming reminders only
                eventbridge_expression = reminder.get("eventbridge_expression", None)
                if eventbridge_expression:
                    try:
                        next_occurrences = parse_eventbridge_expression(eventbridge_expression, occurrences=3)
                        reminder_data["next_occurrences"] = [occ.isoformat() for occ in next_occurrences]
                    except ValueError as e:
                        print(f"Error parsing EventBridge expression for reminder {reminder['SK']}: {e}")
                        reminder_data["next_occurrences"] = "Error parsing schedule"

            # Categorize reminders into past or upcoming based on end_date or completion status
            if is_past:
                response_data["past"].append(reminder_data)
            else:
                response_data["upcoming"].append(reminder_data)

        # Return only the requested type or all if "all" was specified
        if filter_type == "past":
            return {"statusCode": 200, "body": json.dumps({"past": response_data["past"]})}
        elif filter_type == "upcoming":
            return {"statusCode": 200, "body": json.dumps({"upcoming": response_data["upcoming"]})}
        else:
            return {"statusCode": 200, "body": json.dumps(response_data)}

    except Exception as e:
        print(f"Error fetching reminders: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to fetch reminders"})
        }
