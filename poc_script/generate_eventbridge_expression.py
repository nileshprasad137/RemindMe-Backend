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

def generate_eventbridge_expression(task, start_date, time_str, frequency, days_of_week, selected_days_of_month, selected_model="gpt-4o"):
    # Load the Chroma database
    embedding_function = OpenAIEmbeddings(openai_api_key=openai_api_key)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)
    model = ChatOpenAI(temperature=0, openai_api_key=openai_api_key, model=selected_model)

    # Simplified query text for similarity search
    query_text = (
        f"I need help with creating an AWS EventBridge schedule expression based on the following details:\n\n"
        f"Task: {task}\n"
        f"Start Date: {start_date} (in dd-mm-yyyy format)\n"
        f"Time: {time_str} (in hh:mm AM/PM format)\n"
        f"Frequency: {frequency}\n"
        f"Days of the Week: {', '.join(days_of_week) if days_of_week else 'N/A'}\n\n"
        f"Selected days of month: {', '.join(list(map(str,selected_days_of_month))) if selected_days_of_month else 'N/A'}\n\n"
        "Please retrieve any relevant context from saved docs on creating schedule expressions."
    )

    # Perform similarity search to retrieve relevant chunks
    results = db.similarity_search_with_relevance_scores(query_text, k=3)
    if not results or results[0][1] < 0.7:
        print("Unable to find matching results.")
        return

    context = "\n\n---\n\n".join([doc.page_content for doc, _ in results])

    # Define the prompt template with explicit day-of-week guidance
    prompt_template = ChatPromptTemplate.from_template("""
    Use the uploaded docs to answer the question:\n\n
    {context}\n\n
    Question: Based on the task details below, generate the correct AWS-compatible schedule expression:
    - **Task**: {task}
    - **Start Date**: {start_date} (in dd-mm-yyyy format)
    - **Time**: {time} (in hh:mm AM/PM format)
    - **Frequency**: {frequency}
    - **Days of the Week**: {days_of_week}
    - **Selected Days of the Month**: {selected_days_of_month}

    **Guidelines**:
    - **One-Time Event**: If `frequency` is one time or once , use an `at()` expression. Format it as `at(YYYY-MM-DDTHH:MM:SS)`, e.g., `at(2024-10-14T11:00:00)`. Don't use this if frequency is monthly, daily or weekly.
    - **Simple Interval Recurrence**: For simple intervals like every day or every hour, use a `rate` expression:
        - `rate(1 day)` for a daily schedule.
        - `rate(2 days)` for alternate days
        - `rate(3 days)` for every 3 days.
        - `rate(2 hours)` for every 2 hours
        - If `frequency` is "monthly", use a `cron` expression to run on a specific day each month. For example, `cron(0 11 14 * ? *)` for a task on the 14th of each month at 11:00 AM.
    - **Specific Day Recurrence or Complex Patterns**: Use a `cron` expression in AWS's 6-component format when specific days of the week are provided.
        - Day-of-week can be represented by numeric values 1-7 (where 1 - Sunday, 2 - Monday, 3 - Tuesday, 4-Wednesday, 5-Thursday, 6-Friday 7 for Saturday) or strings (SUN-SAT).
        - Example: For every Monday and Wednesday at 11:00 AM, use `cron(0 11 ? * 2,4 *)`.
        - Example: For the first of every month at 9:00 AM, use `cron(0 9 1 * ? *)`.

    **Expression Requirements**:
    - If `Days of the Week` is specified, use the `cron` format with those days. Use day abbreviations (e.g., MON, WED) or numeric values (e.g., 2, 4) as appropriate.
    - Ensure the cron expression has exactly 6 components: Minutes Hours Day-of-month Month Day-of-week Year. The `Year` should be a four-digit format (e.g., `2024`).
    - Choose the simplest expression format that accurately represents the schedule. For example, prefer `rate` for straightforward daily intervals and `cron` for weekly schedules on specific days and One-Time Event for one off event..
    """)

    prompt = prompt_template.format(
        context=context, task=task, start_date=start_date, 
        time=time_str, frequency=frequency,
        days_of_week=", ".join(days_of_week) if days_of_week else "N/A",
        selected_days_of_month=", ".join(list(map(str,selected_days_of_month))) if selected_days_of_month else "N/A"
    )

    # Generate the response
    response = model.predict(prompt)
    eventbridge_expression = response.strip()
    print(f"Generated EventBridge Expression: {eventbridge_expression}")
    return eventbridge_expression

if __name__ == "__main__":
    # Example data
    # parsed_data = {'task': 'exercise', 'frequency': 'once', 'days_of_week': [], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '14-10-2024'}
    # parsed_data = {'task': 'exercise', 'frequency': 'alternate days', 'days_of_week': [], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '14-10-2024'}
    # parsed_data = {'task': 'wish hbd', 'frequency': 'one-time', 'days_of_week': [], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '14-10-2024'}
    # parsed_data ={'task': 'exercise', 'frequency': 'weekly', 'days_of_week': ['Monday', 'Wednesday'], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '14-10-2024'}
    # parsed_data = {'task': 'pay cc bill', 'frequency': 'monthly', 'days_of_week': [], 'time': '11:00 AM', 'context': '', 'tags': ['finance'], 'start_date': '20-10-2024'}
    # parsed_data= {'task': 'pay cc bill', 'frequency': 'monthly', 'days_of_week': [], 'selected_days_of_month': [13], 'time': '11:00 AM', 'context': '', 'tags': ['bills'], 'start_date': '13-11-2024'}
    # parsed_data = {'task': 'visit doctor', 'frequency': 'monthly', 'days_of_week': [], 'time': '11:00 AM', 'context': '', 'tags': ['health'], 'start_date': '14-10-2024'}
    parsed_data = {'task': 'buy something', 'frequency': 'monthly', 'days_of_week': [], 'selected_days_of_month': [12, 15], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '12-11-2024'}
    generate_eventbridge_expression(
        task=parsed_data['task'],
        start_date=parsed_data['start_date'],
        time_str=parsed_data['time'],
        frequency=parsed_data['frequency'],
        days_of_week=parsed_data.get('days_of_week', []),
        selected_days_of_month=parsed_data.get('selected_days_of_month', [])
    )
