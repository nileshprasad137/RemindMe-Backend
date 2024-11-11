import os
import dateparser
import json
import uuid
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from helpers import (
    get_reminder_schedule_json,
    generate_reminder_summary,
    generate_eventbridge_expression
)


# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")
events = boto3.client("events")
scheduler = boto3.client('scheduler')

REMINDERS_TABLE_NAME = os.environ["REMINDERS_TABLE_NAME"]
REMINDERS_QUEUE_URL = os.environ["REMINDERS_QUEUE_URL"]
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
    reminder_text = body["reminder_data"]["text"]
    reminder_id = body.get("reminder_id", str(uuid.uuid4()))

    try:
        reminder_schedule_json = get_reminder_schedule_json(reminder_text)

        # Generate EventBridge expression
        expression = generate_eventbridge_expression(
            start_date=reminder_schedule_json["start_date"],
            time_str=reminder_schedule_json["time"],
            repeat_frequency=reminder_schedule_json["repeat_frequency"]
        )

        reminder_scheduled_message = generate_reminder_summary(reminder_schedule_json)

        rule_name = f"reminder_{reminder_id}"

        if is_one_time_schedule(expression):
            scheduler.create_schedule(
                Name=rule_name,
                ScheduleExpression=expression,
                FlexibleTimeWindow={
                    'Mode': 'OFF'
                },
                Target={
                    'Arn': EVENTBRIDGE_TARGET,
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
        reminder_schedule_json["PK"] = f"CUSTOMER#{device_id}"
        reminder_schedule_json["SK"] = f"REMINDER#{reminder_id}"
        reminder_schedule_json["reminder_scheduled_message"] = reminder_scheduled_message
        reminder_schedule_json["eventbridge_expression"] = expression
        reminder_schedule_json["is_completed"] = False
        reminder_schedule_json["created_at"] = datetime.now().isoformat()
        reminder_schedule_json["updated_at"] = datetime.now().isoformat()
        reminder_schedule_json["time"] = dateparser.parse(reminder_schedule_json["time"]).strftime('%I:%M %p')
        # Insert the reminder into DynamoDB
        reminders_table.put_item(Item=reminder_schedule_json)

        # Send success response with reminder ID
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Reminder scheduled successfully",
                "reminder_id": reminder_id,
                "reminder_scheduled_message": reminder_scheduled_message
            }),
            "headers": {
                "Access-Control-Allow-Origin": "*",  # or specify your domain
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
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
            "body": json.dumps({"error": "Failed to schedule reminder"}),
            "headers": {
                "Access-Control-Allow-Origin": "*",  # or specify your domain
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
        }
