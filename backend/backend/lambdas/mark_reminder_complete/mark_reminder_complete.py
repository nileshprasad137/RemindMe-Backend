import os
import json
import boto3
from datetime import datetime

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
events_client = boto3.client("events")
REMINDERS_TABLE_NAME = os.environ["REMINDERS_TABLE_NAME"]

def handler(event, context):
    try:
        # Parse the request body to get device_id and reminder_id
        body = json.loads(event.get("body", "{}"))
        device_id = body.get("device_id")
        reminder_id = body.get("reminder_id")

        # Validate input
        if not device_id or not reminder_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "device_id and reminder_id are required"}),
                "headers": {
                    "Access-Control-Allow-Origin": "*",  # or specify your domain
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
                },
            }

        # Define the primary key and sort key for the reminder
        pk = f"CUSTOMER#{device_id}"
        sk = f"REMINDER#{reminder_id}"

        # Reference the DynamoDB table
        reminders_table = dynamodb.Table(REMINDERS_TABLE_NAME)

        # Update the reminder item to set is_completed to True and update the updated_at timestamp
        response = reminders_table.update_item(
            Key={
                "PK": pk,
                "SK": sk
            },
            UpdateExpression="SET is_completed = :completed, updated_at = :updated_at",
            ExpressionAttributeValues={
                ":completed": True,
                ":updated_at": datetime.now().isoformat()
            },
            ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
            ReturnValues="UPDATED_NEW"
        )

        # Disable the associated EventBridge rule
        rule_name = f"reminder_{reminder_id}"
        try:
            # Check if the EventBridge rule exists and disable it
            events_client.describe_rule(Name=rule_name)  # This checks if the rule exists
            events_client.disable_rule(Name=rule_name)
        except events_client.exceptions.ResourceNotFoundException:
            # If the rule doesn't exist, log and continue
            print(f"No EventBridge rule found for {rule_name}")

        # Return success response with updated attributes
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Reminder marked as complete and associated EventBridge rule disabled",
                "updated_attributes": response.get("Attributes", {})
            }),
            "headers": {
                "Access-Control-Allow-Origin": "*",  # or specify your domain
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
        }

    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        # This exception occurs if the item does not exist
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "Reminder not found"}),
            "headers": {
                "Access-Control-Allow-Origin": "*",  # or specify your domain
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
        }
    except Exception as e:
        print(f"Error marking reminder as complete: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to mark reminder as complete"}),
            "headers": {
                "Access-Control-Allow-Origin": "*",  # or specify your domain
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
        }
