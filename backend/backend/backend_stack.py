import os
from dotenv import load_dotenv
from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_sqs as sqs,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    aws_iam as iam
)
from constructs import Construct

load_dotenv()

class RemindMeBackend(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Define DynamoDB table for Reminders
        reminders_table = dynamodb.Table(
            self, 
            "RemindersTable",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING)
        )
        
        # Apply the removal policy to retain the table on stack deletion
        reminders_table.apply_removal_policy(RemovalPolicy.RETAIN)

        # Define DynamoDB table for CustomerDevices
        customer_devices_table = dynamodb.Table(
            self, 
            "CustomerDevices",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING)
        )
        customer_devices_table.add_global_secondary_index(
            index_name="DeviceIdIndex",
            partition_key=dynamodb.Attribute(name="device_id", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL
        )
        customer_devices_table.apply_removal_policy(RemovalPolicy.RETAIN)

        # Define SQS Queue for Failure Handling
        reminders_queue = sqs.Queue(self, "RemindersQueue")
        reminders_queue.apply_removal_policy(RemovalPolicy.RETAIN)

        # Define Lambda Function for set-reminder-by-text
        set_reminder_by_text_lambda = _lambda.Function(
            self,
            "SetReminderByTextFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="set_reminder_by_text.handler",
            timeout=Duration.seconds(15),
            code=_lambda.Code.from_asset("backend/lambdas/set_reminder_by_text"),
            layers=[
                _lambda.LayerVersion.from_layer_version_arn(
                    self,
                    "DependenciesLayer1",
                    os.getenv("LAMBDA_LAYER_ARN")
                )
            ],
            environment={
                "REMINDERS_TABLE_NAME": reminders_table.table_name,
                "REMINDERS_QUEUE_ARN": reminders_queue.queue_arn,
                "REMINDERS_QUEUE_URL": reminders_queue.queue_url,
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
                "EVENTBRIDGE_TARGET": os.getenv("EVENTBRIDGE_TARGET")
            },
            architecture=_lambda.Architecture.X86_64
        )

        # Define Lambda Function for set-reminder-manually
        set_reminder_manually_lambda = _lambda.Function(
            self,
            "SetReminderManuallyFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="set_reminder_manually.handler",
            timeout=Duration.seconds(15),
            code=_lambda.Code.from_asset("backend/lambdas/set_reminder_manually"),
            layers=[
                _lambda.LayerVersion.from_layer_version_arn(
                    self,
                    "DependenciesLayer2",
                    os.getenv("LAMBDA_LAYER_ARN")
                )
            ],
            environment={
                "REMINDERS_TABLE_NAME": reminders_table.table_name,
                "REMINDERS_QUEUE_ARN": reminders_queue.queue_arn,
                "REMINDERS_QUEUE_URL": reminders_queue.queue_url,
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
                "EVENTBRIDGE_TARGET": os.getenv("EVENTBRIDGE_TARGET")
            },
            architecture=_lambda.Architecture.X86_64
        )

        # Define Lambda Function for manage_customer_device_info
        manage_customer_device_info_lambda = _lambda.Function(
            self,
            "ManageCustomerDeviceInfo",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="manage_customer_device_info.handler",
            timeout=Duration.seconds(15),
            code=_lambda.Code.from_asset("backend/lambdas/manage_customer_device_info"),
            layers=[
                _lambda.LayerVersion.from_layer_version_arn(
                    self,
                    "DependenciesLayer5",
                    os.getenv("LAMBDA_LAYER_ARN")
                )
            ],
            environment={
                "CUSTOMER_DEVICES_TABLE_NAME": customer_devices_table.table_name
            },
            architecture=_lambda.Architecture.X86_64
        )

        # Define Lambda Function for get-reminder-list
        get_reminder_list_lambda = _lambda.Function(
            self,
            "GetReminderListFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="get_reminder_list.handler",
            timeout=Duration.seconds(15),
            code=_lambda.Code.from_asset("backend/lambdas/get_reminder_list"),
            layers=[
                _lambda.LayerVersion.from_layer_version_arn(
                    self,
                    "DependenciesLayer3",
                    os.getenv("LAMBDA_LAYER_ARN")
                )
            ],
            environment={
                "REMINDERS_TABLE_NAME": reminders_table.table_name,
                "EVENTBRIDGE_TARGET": os.getenv("EVENTBRIDGE_TARGET")
            },
            architecture=_lambda.Architecture.X86_64
        )

        # Define Lambda Function for mark-reminder-complete
        mark_reminder_complete_lambda = _lambda.Function(
            self,
            "MarkReminderCompleteFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="mark_reminder_complete.handler",
            timeout=Duration.seconds(15),
            code=_lambda.Code.from_asset("backend/lambdas/mark_reminder_complete"),
            layers=[
                _lambda.LayerVersion.from_layer_version_arn(
                    self,
                    "DependenciesLayer4",
                    os.getenv("LAMBDA_LAYER_ARN")
                )
            ],
            environment={
                "REMINDERS_TABLE_NAME": reminders_table.table_name
            },
            architecture=_lambda.Architecture.X86_64
        )

        # Grant Lambda permissions to DynamoDB table and SQS
        reminders_table.grant_read_write_data(set_reminder_by_text_lambda)
        reminders_table.grant_read_write_data(set_reminder_manually_lambda)
        reminders_table.grant_read_write_data(manage_customer_device_info_lambda)
        customer_devices_table.grant_read_write_data(manage_customer_device_info_lambda)
        reminders_table.grant_read_data(get_reminder_list_lambda)
        reminders_table.grant_read_write_data(mark_reminder_complete_lambda)
        reminders_queue.grant_send_messages(set_reminder_by_text_lambda)
        reminders_queue.grant_send_messages(set_reminder_manually_lambda)

        # Add EventBridge permissions to the Lambda roles
        set_reminder_by_text_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:PutRule", "events:PutTargets"],
                resources=[f"arn:aws:events:{self.region}:{self.account}:rule/*"]
            )
        )
        set_reminder_manually_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:PutRule", "events:PutTargets"],
                resources=[f"arn:aws:events:{self.region}:{self.account}:rule/*"]
            )
        )
        get_reminder_list_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:DescribeRule", "events:ListTagsForResource"],
                resources=[f"arn:aws:events:{self.region}:{self.account}:rule/*"]
            )
        )
        mark_reminder_complete_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:DescribeRule", "events:DisableRule"],
                resources=[f"arn:aws:events:{self.region}:{self.account}:rule/*"]
            )
        )

        # Define API Gateway to trigger Lambda
        api = apigateway.RestApi(self, "RemindersApi")
        api.apply_removal_policy(RemovalPolicy.RETAIN)

        # API resource for set-reminder-by-text
        set_reminder_by_text_resource = api.root.add_resource("set-reminder-by-text")
        set_reminder_by_text_integration = apigateway.LambdaIntegration(set_reminder_by_text_lambda)
        set_reminder_by_text_resource.add_method("POST", set_reminder_by_text_integration)

        # API resource for set-reminder-manually
        set_reminder_manually_resource = api.root.add_resource("set-reminder-manually")
        set_reminder_manually_integration = apigateway.LambdaIntegration(set_reminder_manually_lambda)
        set_reminder_manually_resource.add_method("POST", set_reminder_manually_integration)

        # API resource for get-reminder-list
        get_reminder_list_resource = api.root.add_resource("get-reminder-list")
        get_reminder_list_integration = apigateway.LambdaIntegration(get_reminder_list_lambda)
        get_reminder_list_resource.add_method("GET", get_reminder_list_integration)

        # API resource for mark-reminder-complete
        mark_reminder_complete_resource = api.root.add_resource("mark-reminder-complete")
        mark_reminder_complete_integration = apigateway.LambdaIntegration(mark_reminder_complete_lambda)
        mark_reminder_complete_resource.add_method("POST", mark_reminder_complete_integration)
        
        # API resource for register-device-data
        manage_customer_device_info_resource = api.root.add_resource("manage-customer-device-info")
        manage_customer_device_info_integration = apigateway.LambdaIntegration(manage_customer_device_info_lambda)
        manage_customer_device_info_resource.add_method("POST", manage_customer_device_info_integration)
