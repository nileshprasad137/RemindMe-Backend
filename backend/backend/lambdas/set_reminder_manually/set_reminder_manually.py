import os
import json
import uuid
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from helpers import (
    generate_reminder_summary,
    generate_eventbridge_expression
)

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")
events = boto3.client("events")
scheduler = boto3.client('scheduler')

REMINDERS_TABLE_NAME = os.environ["REMINDERS_TABLE_NAME"]
EVENTBRIDGE_TARGET = os.environ["EVENTBRIDGE_TARGET"]

def is_one_time_schedule(expression):
    """
    Determines if a given EventBridge expression is a one-time schedule.

    Parameters:
        expression (str): The schedule expression to check.

    Returns:
        bool: True if it is a one-time schedule ('at' expression), False otherwise.
    """
    return expression.strip().startswith("at(")


def handler(event, context):
    body = json.loads(event["body"])
    device_id = body["device_id"]
    reminder_data = body["reminder_data"]
    reminder_id = body.get("reminder_id", str(uuid.uuid4()))

    try:
        # Generate EventBridge expression
        expression = generate_eventbridge_expression(
            start_date=reminder_data["start_date"],
            time_str=reminder_data["time"],
            repeat_frequency=reminder_data.get("repeat_frequency") or None
        )

        reminder_scheduled_message = generate_reminder_summary(reminder_data)

        rule_name = f"reminder_{reminder_id}"
        
        if is_one_time_schedule(expression):
            scheduler.create_schedule(
                Name=rule_name,
                ScheduleExpression=expression,
                FlexibleTimeWindow={
                    'Mode': 'OFF'
                },
                # TODO: EVENTBRIDGE_TARGET AND ROLE NEEDS TO BE ADDED
                Target={
                    'Arn': EVENTBRIDGE_TARGET,
                    # TODO: ADD ROLE ARN
                }
            )
            print("One-time EventBridge Scheduler job created successfully.")
        else:
            # Create the EventBridge rule
            events.put_rule(
                Name=rule_name,
                ScheduleExpression=expression,
                State="ENABLED"
            )

        # Add the reminder entry to DynamoDB directly
        reminders_table = dynamodb.Table(REMINDERS_TABLE_NAME)
        reminder_data["PK"] = f"CUSTOMER#{device_id}"
        reminder_data["SK"] = f"REMINDER#{reminder_id}"
        reminder_data["reminder_scheduled_message"] = reminder_scheduled_message
        reminder_data["eventbridge_expression"] = expression
        reminder_data["is_completed"] = False
        reminder_data["created_at"] = datetime.now().isoformat()
        reminder_data["updated_at"] = datetime.now().isoformat()
        # Insert the reminder into DynamoDB
        reminders_table.put_item(Item=reminder_data)

        # Send success response with reminder ID
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Reminder scheduled successfully",
                "reminder_id": reminder_id,
                "reminder_scheduled_message": reminder_scheduled_message
            })
        }

    except ClientError as e:
        print(f"Error scheduling reminder: {e}")
        # Return an error response
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to schedule reminder"})
        }
