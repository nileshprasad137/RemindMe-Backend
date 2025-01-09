# RemindMe (Backend)

## Overall Architecture

This is backend of the "RemindMe" application which enables users to set, manage, and sync(WIP) reminders effortlessly using natural language input. It leverages a serverless architecture powered by AWS services, ensuring scalable, efficient, and cost-effective operations.  

<img width="686" alt="image" src="https://github.com/user-attachments/assets/56cc4d7c-17e6-49a6-90bb-ee01303d15e7" />


### Core AWS Components Used:
- **AWS Lambda**: Hosts the core backend logic for handling reminders, customer and device management, and scheduling tasks.
- **AWS EventBridge**: Manages scheduling and triggering of reminder events based on cron or rate expressions.
- **AWS DynamoDB**: A NoSQL database for storing reminders, customer information, and device data.
- **AWS SQS**: Facilitates asynchronous processing by queuing tasks between Lambda functions.
- **AWS CDK**: Infrastructure as code framework used to deploy and manage resources in AWS.
- **Lambda Layer**: Bundles shared dependencies for efficient reuse across Lambda functions.

---

## Project Structure

```
RemindMe
├── backend
│   ├── README.md                  # Backend-specific documentation
│   ├── app.py                    # Entry point for CDK application
│   ├── backend/                 # Backend source code
│   │   ├── backend_stack.py # CDK stack for backend infrastructure
│   │   ├── lambdas/         # Lambda function code
│   ├── cdk.json                 # CDK configuration file
│   ├── lambda_layer/            # Shared dependencies for Lambda
│   │   ├── requirements.txt # Dependencies for Lambda Layer
│   │   └── python/          # Lambda Layer packages
│   ├── requirements.txt         # Dependencies for Lambda functions
│   ├── requirements-dev.txt     # Development-specific dependencies
│   ├── tests/                   # Test cases for backend logic
├── README.md                        # Project documentation
├── notes.txt                        # Additional project notes
├── poc_script/                      # Proof of concept scripts
```

---

## Deployment Instructions

This guide assumes you have:
1. AWS credentials configured with access to deploy resources.
2. Node.js and npm installed.
3. Python (>=3.8) and virtualenv installed.
4. AWS CLI installed and configured.
5. CDK installed globally using `npm install -g aws-cdk`.

---

### Setup Environment Variables

Create a `.env` file in the root directory and populate it with the following variables:

```env
CDK_DEFAULT_ACCOUNT=<Your AWS Account ID>
CDK_DEFAULT_REGION=<Your AWS Region>
OPENAI_API_KEY=<Your OpenAI API Key>
LAMBDA_LAYER_ARN=<ARN of the deployed Lambda Layer>
EVENTBRIDGE_TARGET=<EventBridge target ARN>
SERVICE_ACCOUNT_JSON=<JSON OF SERVICE ACCOUNT>
FIREBASE_PROJECT_ID=<FIREBASE PROJECT ID FOR SENDING PNS ON ANDROID FROM FCM.>

(More on this below)
```

---

### Install Dependencies

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install development-specific dependencies (for testing and local development):
   ```bash
   pip install -r requirements-dev.txt
   ```

3. Install Lambda function-specific dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

### Deploy Lambda Layer

The Lambda Layer bundles shared dependencies (e.g., regex, croniter, google-auth). To deploy:

#### Prepare the Lambda Layer Directory

1. Create the necessary directory structure:
   ```bash
   mkdir -p lambda_layer/python/lib/python3.11/site-packages
   cd lambda_layer
   ```

2. Install dependencies into the `site-packages` directory:
   ```bash
   pip install --platform manylinux2014_x86_64 --only-binary=:all: --no-cache -r requirements.txt -t python/lib/python3.11/site-packages/
   ```

#### Package the Lambda Layer

1. Zip the contents of the `python` directory:
   ```bash
   zip -r lambda_layer.zip python
   ```

#### Deploy the Lambda Layer to AWS

1. Publish the Lambda layer using the AWS CLI:
   ```bash
   aws lambda publish-layer-version \
       --layer-name "your-layer-name" \
       --description "Lambda layer with shared dependencies" \
       --zip-file fileb://lambda_layer.zip \
       --compatible-runtimes python3.11 \
       --profile your-aws-profile
   ```

2. Note the ARN from the CLI output, which you will use in your Lambda function.

#### Attach the Layer to Your Lambda Function

In your AWS Lambda function code, reference the layer ARN:

```python
set_reminder_lambda = _lambda.Function(
    self,
    "SetReminderByTextFunction",
    runtime=_lambda.Runtime.PYTHON_3_11,
    handler="set_reminder_by_text.handler",
    code=_lambda.Code.from_asset("backend/lambdas/set_reminder_by_text"),
    layers=[
        _lambda.LayerVersion.from_layer_version_arn(
            self,
            "SharedDependenciesLayer",
            "arn:aws:lambda:<region>:<account-id>:layer:your-layer-name:<version>"
        )
    ],
    environment={
        "REMINDERS_TABLE_NAME": reminders_table.table_name,
        "REMINDERS_QUEUE_ARN": reminders_queue.queue_arn,
        "REMINDERS_QUEUE_URL": reminders_queue.queue_url,
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    },
)
```

---

### CDK Commands

The AWS CDK (Cloud Development Kit) simplifies cloud resource deployment. Below are the key commands:

1. **Initialize Virtual Environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Synthesize CloudFormation Template**
   This generates the CloudFormation template for your CDK application:
   ```bash
   cdk synth
   ```

3. **List Stacks**
   Display all stacks defined in the application:
   ```bash
   cdk ls
   ```

4. **Deploy Stack**
   Deploy the stack to your AWS account and region:
   ```bash
   cdk deploy
   ```

5. **Diff Stacks**
   Compare deployed stack with current code:
   ```bash
   cdk diff
   ```

6. **Open Documentation**
   Open the CDK documentation:
   ```bash
   cdk docs
   ```

---

## Notes on Requirements Files

- **Root `requirements-dev.txt`**: Contains dependencies required for development and testing (e.g., pytest, boto3).
- **Root `requirements.txt`**: Contains dependencies specific to the Lambda functions (e.g., boto3, openai).
- **`lambda_layer/requirements.txt`**: Contains dependencies that are shared across multiple Lambda functions and packaged into a Lambda Layer.

---

## Features

- **Natural Language Parsing**: Accepts user input in plain text and generates EventBridge schedules.
- **Reminder Management**: Stores and retrieves reminders with recurrence support.
- **Device Management**: [WIP] Syncs customer data across multiple devices. 
- **Scalability**: Serverless design ensures seamless scaling.

---

## Dependencies

The project uses the following key dependencies:

- **regex**: For parsing complex reminder patterns.
- **croniter**: To generate cron expressions for EventBridge.

---

## Notes

- **Environment Configuration**: Ensure all environment variables are correctly set in `.env`.
- **IAM Permissions**: The AWS user deploying the stack must have permissions to create and manage Lambda, EventBridge, DynamoDB, and SQS resources.

---

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Submit a pull request.

