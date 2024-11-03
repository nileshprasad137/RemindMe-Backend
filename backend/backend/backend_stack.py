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

        # Define SQS Queue for Failure Handling
        reminders_queue = sqs.Queue(self, "RemindersQueue")
        reminders_queue.apply_removal_policy(RemovalPolicy.RETAIN)

        # Define Lambda Function for set-reminder-by-text
        set_reminder_by_text_lambda =  _lambda.Function(
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
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")
            },
            architecture=_lambda.Architecture.X86_64
        )

        # Define Lambda Function for set-reminder-manually
        set_reminder_manually_lambda =  _lambda.Function(
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
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")
            },
            architecture=_lambda.Architecture.X86_64
        )

        # Grant Lambda permissions to DynamoDB table and SQS
        reminders_table.grant_read_write_data(set_reminder_by_text_lambda)
        reminders_table.grant_read_write_data(set_reminder_manually_lambda)
        reminders_queue.grant_send_messages(set_reminder_by_text_lambda)
        reminders_queue.grant_send_messages(set_reminder_manually_lambda)

        # Add EventBridge permissions to the Lambda role
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

        # Define API Gateway to trigger Lambda
        api = apigateway.RestApi(self, "RemindersApi")
        api.apply_removal_policy(RemovalPolicy.RETAIN)
        # add api -> set-reminder-by-text
        set_reminder_by_text_resource = api.root.add_resource("set-reminder-by-text")
        set_reminder_by_text_integration = apigateway.LambdaIntegration(set_reminder_by_text_lambda)
        set_reminder_by_text_resource.add_method("POST", set_reminder_by_text_integration)
        # add api -> set-reminder-manually
        set_reminder_manually_resource = api.root.add_resource("set-reminder-manually")
        set_reminder_manually_integration = apigateway.LambdaIntegration(set_reminder_manually_lambda)
        set_reminder_manually_resource.add_method("POST", set_reminder_manually_integration)