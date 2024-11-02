import os
import json
import uuid
import boto3
from botocore.exceptions import ClientError
from datetime import datetime

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")
events = boto3.client("events")

REMINDERS_TABLE_NAME = os.environ["REMINDERS_TABLE_NAME"]
REMINDERS_QUEUE_ARN = os.environ["REMINDERS_QUEUE_ARN"]
REMINDERS_QUEUE_URL = os.environ["REMINDERS_QUEUE_URL"]

def generate_eventbridge_expression(reminder_text):
    # Placeholder for your function to generate the EventBridge cron/rate expression
    return "rate(3 days)"

def handler(event, context):
    body = json.loads(event["body"])
    device_id = body["device_id"]
    reminder_text = body["reminder_data"]["text"]
    # if reminder_id is not in body, create a new reminder id, else use that to update.
    reminder_id = body["reminder_id"]

    if not reminder_id:
        # Generate a unique reminder ID
        reminder_id = str(uuid.uuid4())

    # Generate EventBridge expression
    expression = generate_eventbridge_expression(reminder_text)

    # Create EventBridge rule
    rule_name = f"reminder_{device_id}_{reminder_id}"
    try:
        events.put_rule(
            Name=rule_name,
            ScheduleExpression=expression,
            State="ENABLED"
        )

        # Add reminder entry to DynamoDB through SQS
        reminder_entry = {
            "PK": f"CUSTOMER#{device_id}",
            "SK": f"REMINDER#{reminder_id}",
            "task": reminder_text,
            "start_date": datetime.now().strftime('%Y-%m-%d'),
            "end_date": None,
            "time": "8:00 AM",
            "repeat_frequency": {
                "daily": None,
                "weekly": None,
                "monthly": None,
                "yearly": None,
                "hourly": 7,
                "selected_days_of_week": None,
                "selected_days_of_month": None
            },
            "tags": ["example_tag"],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Send message to SQS with the reminder entry for DynamoDB addition
        sqs.send_message(
            QueueUrl=REMINDERS_QUEUE_URL,
            MessageBody=json.dumps(reminder_entry)
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Reminder scheduled successfully",
                "reminder_id": reminder_id
            })
        }

    except ClientError as e:
        print(f"Error scheduling reminder: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to schedule reminder"})
        }
