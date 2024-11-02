import os
import json
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")
events = boto3.client("events")

REMINDERS_TABLE_NAME = os.environ["REMINDERS_TABLE_NAME"]
REMINDERS_QUEUE_ARN = os.environ["REMINDERS_QUEUE_ARN"]
REMINDERS_QUEUE_URL = os.environ["REMINDERS_QUEUE_URL"]

def generate_eventbridge_expression(reminder_text):
    # Your function to generate the EventBridge cron/rate expression
    return "rate(1 day)"

def handler(event, context):
    body = json.loads(event["body"])
    device_id = body["device_id"]
    reminder_text = body["reminder_data"]["text"]

    # Generate EventBridge expression
    expression = generate_eventbridge_expression(reminder_text)

    # Create EventBridge rule
    rule_name = f"reminder_{device_id}_{context.aws_request_id}"
    try:
        events.put_rule(
            Name=rule_name,
            ScheduleExpression=expression,
            State="ENABLED"
        )

        # Optionally send a message to SQS for further processing
        sqs.send_message(
            QueueUrl=os.environ["REMINDERS_QUEUE_URL"],  # Use URL here for SQS client
            MessageBody=json.dumps({
                "device_id": device_id,
                "reminder_text": reminder_text,
                "rule_name": rule_name
            })
        )

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Reminder scheduled successfully"})
        }

    except ClientError as e:
        print(f"Error scheduling reminder: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to schedule reminder"})
        }
