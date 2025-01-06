import os
from dotenv import load_dotenv
from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_sqs as sqs,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_events as events,
    RemovalPolicy,
)
from constructs import Construct

load_dotenv()

class RemindMeBackend(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # ----------------------
        # 1) DYNAMODB TABLES
        # ----------------------
        reminders_table = dynamodb.Table(
            self, 
            "RemindersTable",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING)
        )
        reminders_table.apply_removal_policy(RemovalPolicy.RETAIN)

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

        feedback_table = dynamodb.Table(
            self,
            "FeedbackTable",
            partition_key=dynamodb.Attribute(name="feedback_id", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.RETAIN
        )
        feedback_table.apply_removal_policy(RemovalPolicy.RETAIN)

        # ----------------------
        # 2) IAM ROLE FOR SCHEDULER
        # ----------------------
        scheduler_role = iam.Role(
            self, 
            "SchedulerRole",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaRole")  
            ]
        )

        # Allow the Scheduler role to invoke Lambda
        scheduler_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=["*"]  
            )
        )

        # ----------------------
        # 3) SQS QUEUE
        # ----------------------
        reminders_queue = sqs.Queue(self, "RemindersQueue")
        reminders_queue.apply_removal_policy(RemovalPolicy.RETAIN)

        # ----------------------
        # 4) LAMBDAS
        # ----------------------
        # (a) set-reminder-by-text
        set_reminder_by_text_lambda = _lambda.Function(
            self,
            "SetReminderByTextFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="set_reminder_by_text.handler",
            timeout=Duration.seconds(30),
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
                "EVENTBRIDGE_TARGET": os.getenv("EVENTBRIDGE_TARGET"),
                "SCHEDULER_ROLE_ARN": scheduler_role.role_arn
            },
            architecture=_lambda.Architecture.X86_64
        )

        # (b) set-reminder-manually
        set_reminder_manually_lambda = _lambda.Function(
            self,
            "SetReminderManuallyFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="set_reminder_manually.handler",
            timeout=Duration.seconds(30),
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
                "EVENTBRIDGE_TARGET": os.getenv("EVENTBRIDGE_TARGET"),
                "SCHEDULER_ROLE_ARN": scheduler_role.role_arn
            },
            architecture=_lambda.Architecture.X86_64
        )

        # (c) manage_customer_device_info
        manage_customer_device_info_lambda = _lambda.Function(
            self,
            "ManageCustomerDeviceInfo",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="manage_customer_device_info.handler",
            timeout=Duration.seconds(30),
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

        # (d) get-reminder-list
        get_reminder_list_lambda = _lambda.Function(
            self,
            "GetReminderListFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="get_reminder_list.handler",
            timeout=Duration.seconds(30),
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

        # (e) mark-reminder-complete
        mark_reminder_complete_lambda = _lambda.Function(
            self,
            "MarkReminderCompleteFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="mark_reminder_complete.handler",
            timeout=Duration.seconds(30),
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

        # (f) process-events
        process_events_lambda = _lambda.Function(
            self,
            "ProcessEventsFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="process_events.handler",
            timeout=Duration.seconds(30),
            code=_lambda.Code.from_asset("backend/lambdas/process_events"),
            layers=[
                _lambda.LayerVersion.from_layer_version_arn(
                    self,
                    "DependenciesLayer",
                    os.getenv("LAMBDA_LAYER_ARN")
                )
            ],
            environment={
                "CUSTOMER_DEVICES_TABLE_NAME": customer_devices_table.table_name,
                "REMINDERS_TABLE_NAME": reminders_table.table_name
            },
            architecture=_lambda.Architecture.X86_64
        )

        # (g) submit-feedback
        submit_feedback_lambda = _lambda.Function(
            self,
            "SubmitFeedbackFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="submit_feedback.handler",
            timeout=Duration.seconds(30),
            code=_lambda.Code.from_asset("backend/lambdas/submit_feedback"),
            layers=[
                _lambda.LayerVersion.from_layer_version_arn(
                    self,
                    "DependenciesLayer6",
                    os.getenv("LAMBDA_LAYER_ARN")
                )
            ],
            environment={
                "FEEDBACK_TABLE_NAME": feedback_table.table_name
            },
            architecture=_lambda.Architecture.X86_64
        )

        # ----------------------
        # 5) GRANT TABLE & QUEUE PERMISSIONS
        # ----------------------
        reminders_table.grant_read_write_data(set_reminder_by_text_lambda)
        reminders_table.grant_read_write_data(set_reminder_manually_lambda)
        reminders_table.grant_read_write_data(manage_customer_device_info_lambda)
        customer_devices_table.grant_read_write_data(manage_customer_device_info_lambda)
        reminders_table.grant_read_data(get_reminder_list_lambda)
        reminders_table.grant_read_write_data(mark_reminder_complete_lambda)
        reminders_queue.grant_send_messages(set_reminder_by_text_lambda)
        reminders_queue.grant_send_messages(set_reminder_manually_lambda)
        customer_devices_table.grant_read_data(process_events_lambda)
        reminders_table.grant_read_data(process_events_lambda)
        feedback_table.grant_read_write_data(submit_feedback_lambda)

        # ----------------------
        # 6) EVENTBRIDGE / SCHEDULER PERMISSIONS
        # ----------------------
        # Give your "set reminder" Lambdas permission to create, update, or delete
        # schedules and pass the scheduler_role, etc.
        set_reminder_by_text_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "events:PutRule",
                    "events:PutTargets",
                    "scheduler:CreateSchedule",
                    "scheduler:UpdateSchedule",
                    "scheduler:DeleteSchedule",
                    "scheduler:GetSchedule",
                    "iam:PassRole",
                ],
                resources=[
                    f"arn:aws:events:{self.region}:{self.account}:rule/*",
                    f"arn:aws:scheduler:{self.region}:{self.account}:schedule/*",
                    scheduler_role.role_arn,
                ]
            )
        )

        set_reminder_manually_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "events:PutRule",
                    "events:PutTargets",
                    "scheduler:CreateSchedule",
                    "scheduler:UpdateSchedule",
                    "scheduler:DeleteSchedule",
                    "scheduler:GetSchedule",
                    "iam:PassRole",
                ],
                resources=[
                    f"arn:aws:events:{self.region}:{self.account}:rule/*",
                    f"arn:aws:scheduler:{self.region}:{self.account}:schedule/*",
                    scheduler_role.role_arn,
                ]
            )
        )

        # For describing or listing existing rules
        get_reminder_list_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:DescribeRule", "events:ListTagsForResource"],
                resources=[f"arn:aws:events:{self.region}:{self.account}:rule/*"]
            )
        )

        # For marking the reminder complete (disabling rules)
        mark_reminder_complete_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:DescribeRule", "events:DisableRule"],
                resources=[f"arn:aws:events:{self.region}:{self.account}:rule/*"]
            )
        )

        # IMPORTANT: Allow EventBridge Scheduler (or EventBridge) to invoke your Lambdas
        # If using the Scheduler:
        process_events_lambda.add_permission(
            "AllowSchedulerInvokeSetManual",
            principal=iam.ServicePrincipal("scheduler.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:scheduler:{self.region}:{self.account}:schedule/*"
        )

        # If some rules are in standard EventBridge (e.g., rule-based, not the Scheduler),
        # allow event bridge to invoke process lambda.
        process_events_lambda.add_permission(
            "AllowEventBridgeInvokeProcessEvents",
            principal=iam.ServicePrincipal("events.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:events:{self.region}:{self.account}:rule/*"
        )

        # ----------------------
        # 7) API GATEWAY
        # ----------------------
        api = apigateway.RestApi(
            self, 
            "RemindersApi",
            default_cors_preflight_options={
                "allow_origins": apigateway.Cors.ALL_ORIGINS,
                "allow_methods": ["OPTIONS", "GET", "POST"],
                "allow_headers": [
                    "Content-Type",
                    "X-Amz-Date",
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token"
                ]
            }
        )
        api.apply_removal_policy(RemovalPolicy.RETAIN)

        # set-reminder-by-text
        set_reminder_by_text_resource = api.root.add_resource("set-reminder-by-text")
        set_reminder_by_text_integration = apigateway.LambdaIntegration(set_reminder_by_text_lambda)
        set_reminder_by_text_resource.add_method("POST", set_reminder_by_text_integration)

        # set-reminder-manually
        set_reminder_manually_resource = api.root.add_resource("set-reminder-manually")
        set_reminder_manually_integration = apigateway.LambdaIntegration(set_reminder_manually_lambda)
        set_reminder_manually_resource.add_method("POST", set_reminder_manually_integration)

        # get-reminder-list
        get_reminder_list_resource = api.root.add_resource("get-reminder-list")
        get_reminder_list_integration = apigateway.LambdaIntegration(get_reminder_list_lambda)
        get_reminder_list_resource.add_method("GET", get_reminder_list_integration)

        # mark-reminder-complete
        mark_reminder_complete_resource = api.root.add_resource("mark-reminder-complete")
        mark_reminder_complete_integration = apigateway.LambdaIntegration(mark_reminder_complete_lambda)
        mark_reminder_complete_resource.add_method("POST", mark_reminder_complete_integration)

        # manage-customer-device-info
        manage_customer_device_info_resource = api.root.add_resource("manage-customer-device-info")
        manage_customer_device_info_integration = apigateway.LambdaIntegration(manage_customer_device_info_lambda)
        manage_customer_device_info_resource.add_method("POST", manage_customer_device_info_integration)

        # submit-feedback
        submit_feedback_resource = api.root.add_resource("submit-feedback")
        submit_feedback_integration = apigateway.LambdaIntegration(submit_feedback_lambda)
        submit_feedback_resource.add_method("POST", submit_feedback_integration)
