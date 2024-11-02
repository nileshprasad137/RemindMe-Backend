import queue
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_sqs as sqs,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    RemovalPolicy,  # Import RemovalPolicy from aws_cdk
    aws_iam as iam
)
from constructs import Construct
import os

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

        dlq_failover = sqs.Queue(
            self, 
            "RemindersDLQ2",
        )
        dead_letter_queue = sqs.DeadLetterQueue(max_receive_count=500, queue=dlq_failover)

        # Define SQS Queue for Reminder Processing
        reminders_queue = sqs.Queue(
            self, 
            "RemindersQueue",
            dead_letter_queue=dead_letter_queue,
        )
        reminders_queue.apply_removal_policy(RemovalPolicy.RETAIN)

        # Define Lambda Function for set-reminder-by-text
        set_reminder_lambda = _lambda.Function(
            self,
            "SetReminderByTextFunction",
            runtime=_lambda.Runtime.PYTHON_3_8,
            handler="set_reminder_by_text.handler",
            code=_lambda.Code.from_asset("backend/lambdas/set_reminder_by_text"),
            environment={
                "REMINDERS_TABLE_NAME": reminders_table.table_name,
                "REMINDERS_QUEUE_ARN": reminders_queue.queue_arn,
                "REMINDERS_QUEUE_URL": reminders_queue.queue_url,
            },
        )

        # Grant Lambda permissions to DynamoDB table and SQS
        reminders_table.grant_read_write_data(set_reminder_lambda)
        reminders_queue.grant_send_messages(set_reminder_lambda)

        # Add EventBridge permissions to the Lambda role
        set_reminder_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:PutRule", "events:PutTargets"],
                resources=[f"arn:aws:events:{self.region}:{self.account}:rule/*"]
            )
        )

        # Define API Gateway to trigger Lambda
        api = apigateway.RestApi(self, "RemindersApi")
        api.apply_removal_policy(RemovalPolicy.RETAIN)
        reminders = api.root.add_resource("set-reminder-by-text")
        reminders_integration = apigateway.LambdaIntegration(set_reminder_lambda)
        reminders.add_method("POST", reminders_integration)
