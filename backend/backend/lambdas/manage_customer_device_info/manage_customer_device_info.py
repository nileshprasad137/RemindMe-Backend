import os
import json
import uuid
import boto3
from datetime import datetime

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
CUSTOMER_DEVICES_TABLE_NAME = os.environ["CUSTOMER_DEVICES_TABLE_NAME"]

def generate_customer_id():
    """Generate a unique customer ID if none is provided."""
    return str(uuid.uuid4())

def check_device_id_uniqueness(device_id):
    """Check if device_id already exists in CustomerDevices table."""
    table = dynamodb.Table(CUSTOMER_DEVICES_TABLE_NAME)
    response = table.query(
        IndexName="DeviceIdIndex",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("device_id").eq(device_id)
    )
    return response.get("Items", [])

def update_customer_info(customer_id, name=None, mobile=None, email=None):
    """Create or update customer-specific info."""
    if not (name or mobile or email):
        return None  # No customer info to update

    now = datetime.utcnow().isoformat()

    customer_item = {
        "PK": f"CUSTOMER#{customer_id}",
        "SK": "CUSTOMER#INFO",
        "updated_at": now
    }
    if name: 
        customer_item["name"] = name
    if mobile: 
        customer_item["mobile"] = mobile
    if email: 
        customer_item["email"] = email

    if "created_at" not in customer_item:
        customer_item["created_at"] = now

    customer_devices_table = dynamodb.Table(CUSTOMER_DEVICES_TABLE_NAME)
    customer_devices_table.put_item(Item=customer_item)
    return customer_item

def update_device_info(customer_id, device_id, device_token_id, os_version=None, platform=None, model=None, is_virtual=None):
    """Create or update device-specific info."""
    now = datetime.now().isoformat()

    device_item = {
        "PK": f"CUSTOMER#{customer_id}",
        "SK": f"DEVICE#{device_id}",
        "device_id": device_id,
        "device_token_id": device_token_id,
        "updated_at": now
    }
    if os_version: 
        device_item["os_version"] = os_version
    if platform: 
        device_item["platform"] = platform
    if model: 
        device_item["model"] = model
    if is_virtual is not None: 
        device_item["is_virtual"] = is_virtual

    if "created_at" not in device_item:
        device_item["created_at"] = now

    customer_devices_table = dynamodb.Table(CUSTOMER_DEVICES_TABLE_NAME)
    customer_devices_table.put_item(Item=device_item)
    return device_item

def handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        device_id = body.get("device_id")
        device_token_id = body.get("device_token_id")

        # Validate required fields for device info
        if not device_id or not device_token_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "device_id and device_token_id are required"}),
                "headers": {
                    "Access-Control-Allow-Origin": "*",  # or specify your domain
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
                },
            }

        # Check if the device_id is unique
        existing_device = check_device_id_uniqueness(device_id)
        if existing_device:
            # Device already exists, update the existing record if customer_id matches
            if existing_device[0]["PK"] != f"CUSTOMER#{body.get('customer_id')}":
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Device ID already registered under a different customer"})
                }
            # Update the existing device record
            customer_id = existing_device[0]["PK"].split("#")[1]
        else:
            # Generate or use provided customer_id if device is new
            customer_id = body.get("customer_id") or generate_customer_id()

        # Update customer-specific info if provided
        customer_item = update_customer_info(
            customer_id=customer_id,
            name=body.get("name"),
            mobile=body.get("mobile"),
            email=body.get("email")
        )

        # Update device-specific info
        device_item = update_device_info(
            customer_id=customer_id,
            device_id=device_id,
            device_token_id=device_token_id,
            os_version=body.get("os_version"),
            platform=body.get("platform"),
            model=body.get("model"),
            is_virtual=body.get("is_virtual")
        )

        response_data = {
            "message": "Customer and device data registered successfully",
            "customer_id": customer_id,
            "customer_info": customer_item,
            "device_info": device_item
        }

        return {
            "statusCode": 200,
            "body": json.dumps(response_data),
            "headers": {
                "Access-Control-Allow-Origin": "*",  # or specify your domain
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
        }

    except Exception as e:
        print(f"Error registering customer and device data: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to register customer and device data"}),
            "headers": {
                "Access-Control-Allow-Origin": "*",  # or specify your domain
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
        }
