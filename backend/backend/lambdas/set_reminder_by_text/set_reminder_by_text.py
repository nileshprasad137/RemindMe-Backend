import os
import json
import uuid
import boto3
from botocore.exceptions import ClientError
from datetime import datetime

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")
events = boto3.client("events")

REMINDERS_TABLE_NAME = os.environ["REMINDERS_TABLE_NAME"]
REMINDERS_QUEUE_URL = os.environ["REMINDERS_QUEUE_URL"]

# Function to generate EventBridge expression
def generate_eventbridge_expression(reminder_text):
    return "rate(3 days)"  # Placeholder for your expression generation logic

def handler(event, context):
    body = json.loads(event["body"])
    device_id = body["device_id"]
    reminder_text = body["reminder_data"]["text"]
    reminder_id = body.get("reminder_id", str(uuid.uuid4()))

    # Generate EventBridge expression
    expression = generate_eventbridge_expression(reminder_text)
    rule_name = f"reminder_{device_id}_{reminder_id}"

    try:
        # Create the EventBridge rule
        events.put_rule(
            Name=rule_name,
            ScheduleExpression=expression,
            State="ENABLED"
        )

        # Add the reminder entry to DynamoDB directly
        reminders_table = dynamodb.Table(REMINDERS_TABLE_NAME)
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
        
        # Insert the reminder into DynamoDB
        reminders_table.put_item(Item=reminder_entry)

        # Send success response with reminder ID
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Reminder scheduled successfully",
                "reminder_id": reminder_id,
                "reminder_scheduled_message": None
            })
        }

    except ClientError as e:
        print(f"Error scheduling reminder: {e}")
        
        # On failure, send the reminder entry to SQS for error handling
        sqs.send_message(
            QueueUrl=REMINDERS_QUEUE_URL,
            MessageBody=json.dumps({
                "device_id": device_id,
                "reminder_id": reminder_id,
                "reminder_text": reminder_text,
                "rule_name": rule_name,
                "error": str(e)
            })
        )

        # Return an error response
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to schedule reminder"})
        }
