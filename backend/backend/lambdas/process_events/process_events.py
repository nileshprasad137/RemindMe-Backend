import os
import json
import requests
import boto3
from google.oauth2 import service_account
import google.auth.transport.requests

# Configuration
SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/firebase.messaging']
FIREBASE_PROJECT_ID = 'remindme-app-np137'

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
CUSTOMER_DEVICES_TABLE_NAME = os.environ["CUSTOMER_DEVICES_TABLE_NAME"]
REMINDERS_TABLE_NAME = os.environ["REMINDERS_TABLE_NAME"]

def get_access_token():
    """Generate an OAuth 2.0 access token for FCM using a service account."""
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token

def send_push_notification(device_token_id, task, reminder_message):
    """
    Sends a high-priority FCM notification with vibration enabled to the specified Android device.
    """
    try:
        # Get the access token for FCM
        access_token = get_access_token()

        # Prepare the notification content
        notification_content = {
            "title": "Reminder",
            "body": f"Task: {task}\n{reminder_message}"
        }

        # FCM headers and URL
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        url = f'https://fcm.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/messages:send'

        # FCM message body
        message = {
            "message": {
                "token": device_token_id,
                "notification": notification_content,
                "android": {
                    "priority": "high",
                    "notification": {
                        "default_vibrate_timings": True,
                        "sound": "default"
                    }
                }
            }
        }

        # Send the notification request
        response = requests.post(url, headers=headers, json=message)
        
        # Check response and return result
        if response.status_code == 200:
            print("Notification sent successfully:", response.json())
            return {"status": "Notification sent", "device_token_id": device_token_id, "content": notification_content}
        else:
            print("Failed to send notification:", response.json())
            return {"status": "Failed", "error": response.json()}

    except Exception as e:
        print("Error sending push notification:", e)
        return {"status": "Failed", "error": str(e)}


def handler(event, context):
    try:
        # Parse event data to get the device_id and reminder_id
        device_id = event.get("device_id")
        reminder_id = event.get("reminder_id")

        if not device_id or not reminder_id:
            print("device id or reminder_id not sent")
            print("see event: ", event)
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Device ID and Reminder ID are required"})
            }

        # Query CustomerDevices to get device info
        customer_devices_table = dynamodb.Table(CUSTOMER_DEVICES_TABLE_NAME)
        response = customer_devices_table.query(
            IndexName="DeviceIdIndex",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("device_id").eq(device_id)
        )

        if not response.get("Items"):
            print("device id not found")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Device not found"})
            }

        device_info = response["Items"][0]
        device_token_id = device_info.get("device_token_id")

        # Query RemindersTable to get the task content and message
        reminders_table = dynamodb.Table(REMINDERS_TABLE_NAME)
        reminder_response = reminders_table.get_item(
            Key={
                "PK": f"CUSTOMER#{device_id}",
                "SK": f"REMINDER#{reminder_id}"
            }
        )

        if "Item" not in reminder_response:
            print("no reminder found.")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Reminder not found"})
            }

        reminder = reminder_response["Item"]
        task = reminder.get("task", "No task specified")
        reminder_message = f"This is a reminder to - {task}"

        # Send push notification with task content
        notification_response = send_push_notification(device_token_id, task, reminder_message)

        # Log the notification response
        print(f"Push notification response: {notification_response}")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Event processed successfully", "notification": notification_response})
        }

    except Exception as e:
        print(f"Error processing event: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to process event"})
        }
