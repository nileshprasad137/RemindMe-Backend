import os
import uuid
import boto3
import json
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
FEEDBACK_TABLE_NAME = os.getenv("FEEDBACK_TABLE_NAME")
feedback_table = dynamodb.Table(FEEDBACK_TABLE_NAME)

def handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        feedback_id = str(uuid.uuid4())
        
        # Extract fields
        email = body.get("email")
        category = body.get("category")
        feedback_text = body.get("feedback_text")
        device_id = body.get("device_id")
        timestamp = datetime.utcnow().isoformat()

        # Validate inputs
        if not email or not category or not feedback_text:
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "All fields are required."}),
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
                },
            }
        
        # Save to DynamoDB
        feedback_table.put_item(
            Item={
                "feedback_id": feedback_id,
                "device_id": device_id,
                "email": email,
                "category": category,
                "feedback_text": feedback_text,
                "timestamp": timestamp,
            }
        )

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Feedback submitted successfully!"}),
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },

        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
        }
