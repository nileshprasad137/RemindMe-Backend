import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Paths
CHROMA_PATH = "chroma"

def generate_eventbridge_expression(task, start_date, time_str, frequency, days_of_week):
    # Load the Chroma database
    embedding_function = OpenAIEmbeddings(openai_api_key=openai_api_key)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)
    model = ChatOpenAI(temperature=0, openai_api_key=openai_api_key, model="gpt-4o-mini")

    #  Prepare the simplified query text for similarity search
    query_text = (
        f"I need help with creating an AWS EventBridge schedule expression based on the following details:\n\n"
        f"Task: {task}\n"
        f"Start Date: {start_date} (in dd-mm-yyyy format)\n"
        f"Time: {time_str} (in hh:mm AM/PM format)\n"
        f"Frequency: {frequency}\n"
        f"Days of the Week: {', '.join(days_of_week) if days_of_week else 'N/A'}\n\n"
        "Please retrieve any relevant context from saved docs on creating schedule expressions."
    )

    # Perform similarity search to retrieve relevant chunks
    results = db.similarity_search_with_relevance_scores(query_text, k=3)
    if not results or results[0][1] < 0.7:
        print("Unable to find matching results.")
        return

    context = "\n\n---\n\n".join([doc.page_content for doc, _ in results])

    # Define the prompt template for generating the appropriate expression
    prompt_template = ChatPromptTemplate.from_template("""
    Use the following context on AWS EventBridge schedule expressions to answer the question:\n\n
    {context}\n\n
    Question: Based on the task details below, generate the correct AWS-compatible schedule expression:
    - **Task**: {task}
    - **Start Date**: {start_date} (in dd-mm-yyyy format)
    - **Time**: {time} (in hh:mm AM/PM format)
    - **Frequency**: {frequency}
    - **Days of the Week**: {days_of_week}
    
    **Guidelines**:
    - **One-Time Event**: Use an `at()` expression when `frequency` is set to "one-time", formatted as `at(YYYY-MM-DDTHH:MM:SS)`. Example: `at(2024-10-14T11:00:00)`.
    - **Simple Interval Recurrence**: Use a `rate` expression for intervals such as every 1 day, 3 days, or 1 week:
        - Example: For daily recurrence, use `rate(1 day)`.
        - Example: For a 3-day interval, use `rate(3 days)`.
        - Example: For weekly recurrence without specific days, use `rate(1 week)`.
    - **Specific Day Recurrence or Complex Patterns**: Use a `cron` expression in AWS's 6-component format if specific days of the week are provided. The format is `Minutes Hours Day-of-month Month Day-of-week Year`. 
        - Example: For every Monday and Wednesday at 11:00 AM, use `cron(0 11 ? * 2,4 *)`.
        - Example: For the first of every month at 9:00 AM, use `cron(0 9 1 * ? *)`.

    **Expression Requirements**:
    - If `Days of the Week` is specified, use `cron` to ensure the expression runs only on those days.
    - `Frequency` should determine whether a `rate`, `cron`, or `at` expression is used:
        - For `weekly` on specified days, make sure the cron expression includes those days.
        - For intervals like `every 3 days`, use `rate` unless specific days of the week are required.
        - Ensure the cron expression has exactly 6 components: Minutes Hours Day-of-month Month Day-of-week Year. The `Year` should be a four-digit format like `2024`.
    """)

    prompt = prompt_template.format(
        context=context, task=task, start_date=start_date, 
        time=time_str, frequency=frequency,
        days_of_week=", ".join(days_of_week) if days_of_week else "N/A"
    )

    # Generate the response
    response = model.predict(prompt)
    eventbridge_expression = response.strip()
    print(f"Generated EventBridge Expression: {eventbridge_expression}")
    return eventbridge_expression

if __name__ == "__main__":
    # Example data
    parsed_data = {'task': 'exercise', 'frequency': 'weekly', 'days_of_week': ['Monday', 'Wednesday'], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '14-10-2024'}
    # parsed_data = {'task': 'wish hbd', 'frequency': 'one-time', 'days_of_week': [], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '14-10-2024'}
    parsed_data = {'task': 'exercise', 'frequency': 'one-time', 'days_of_week': [], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '14-10-2024'}
    generate_eventbridge_expression(
        task=parsed_data['task'],
        start_date=parsed_data['start_date'],
        time_str=parsed_data['time'],
        frequency=parsed_data['frequency'],
        days_of_week=parsed_data.get('days_of_week', [])
    )
