import os
import json
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")
events = boto3.client("events")

REMINDERS_TABLE_NAME = os.environ["REMINDERS_TABLE_NAME"]
REMINDERS_QUEUE_URL = os.environ["REMINDERS_QUEUE_URL"]

def generate_eventbridge_expression(reminder_text):
    # Your function to generate the EventBridge cron/rate expression
    # Example return:
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
        response = events.put_rule(
            Name=rule_name,
            ScheduleExpression=expression,
            State="ENABLED"
        )

        # Add target (Lambda, SQS, etc., if applicable)
        events.put_targets(
            Rule=rule_name,
            Targets=[
                {
                    "Id": "1",
                    "Arn": REMINDERS_QUEUE_URL  # You can target SQS directly or trigger another Lambda
                }
            ]
        )

        # Send a message to SQS for DynamoDB processing
        sqs.send_message(
            QueueUrl=REMINDERS_QUEUE_URL,
            MessageBody=json.dumps({
                "device_id": device_id,
                "reminder_text": reminder_text,
                "rule_name": rule_name
            })
        )

        # Return success response
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
