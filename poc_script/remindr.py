import os
import dateparser
import parsedatetime
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# Load environment variables from .env
load_dotenv()

# Set up the OpenAI model
model = ChatOpenAI(temperature=0, openai_api_key=os.getenv("OPENAI_API_KEY"), model="gpt-3.5-turbo")

# Define the data structure for a reminder with context
class Reminder(BaseModel):
    task: str = Field(description="The action or task to be reminded of.")
    start_date_phrase: str = Field(description="The relative date phrase indicating when the reminder should start (e.g., tomorrow, next week).")
    frequency: str = Field(description="How often the reminder should occur (e.g., daily, weekly, alternate days).")
    days_of_week: list = Field(default=[], description="Specific days of the week for recurring reminders (e.g., ['Monday', 'Wednesday']).")
    selected_days_of_month: list = Field(default=[], description="Specific days of the month for recurring reminders (e.g., [1, 15, 28]).")
    time: str = Field(description="The specific time of day for the reminder.")
    context: str = Field(description="Any additional context or reason for the reminder, such as special occasions, relationships, or other relevant details.")
    tags: list = Field(description="Tags associated with the reminder for easy categorization.")

# Set up the JSON output parser with the extended Reminder model
parser = JsonOutputParser(pydantic_object=Reminder)

# Define the prompt template with enhanced instructions for context
prompt = PromptTemplate(
    template=(
        "You are an intelligent assistant designed to parse and understand reminder requests with dates and times "
        "specified in various formats. Please follow these instructions carefully:\n\n"
        
        "1. **Interpretation of Dates and Times**:\n"
        "   - Instead of converting dates to exact values, provide a relative date phrase for 'start_date_phrase' "
        "   that describes when the reminder should start (e.g., 'tomorrow,' 'next week').\n"
        
        "2. **Reminder Context**:\n"
        "   - Identify the core action or task within the reminder, as well as the purpose, person involved, or special occasion.\n\n"
        
        "3. **Formatting and Frequency**:\n"
        "   - Extract the main task, start_date_phrase, frequency, and time from the text.\n"
        "   - For reminders that occur on specific days of the week, extract these days as 'days_of_week' (e.g., ['Monday', 'Wednesday']).\n"
        "   - For reminders that occur on specific days of the month, extract these days as 'selected_days_of_month' (e.g., [13, 25]).\n"
        "   - Set the default time to '11:00 AM' if no specific time is given.\n\n"
        
        "4. **Tags Extraction**:\n"
        "   - Identify single or double-word tags from the reminder that represent the main topics or categories.\n\n"
        
        "5. **Output Requirements**:\n"
        "   - Provide the information in a structured JSON format with the following fields: task, start_date_phrase, frequency, "
        "days_of_week, selected_days_of_month, time, context, and tags.\n"
        
        "{format_instructions}\n\n"
        
        "Reminder Text: {query}"
    ),
    input_variables=["query"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# Create a chain that combines the prompt, model, and parser
chain = prompt | model | parser

# Function to process the reminder text using the chain and enhance with defaults
def process_reminder_text(reminder_text):
    # Pass the reminder text to the chain for processing
    parsed_data = chain.invoke({"query": reminder_text})

    # Extract the start date phrase and time from parsed data
    start_date_phrase = parsed_data.get('start_date_phrase', 'tomorrow')
    time_str = parsed_data.get('time', '11:00 AM')  # Default time if none provided
    selected_days_of_month = parsed_data.get('selected_days_of_month', [])

    # Determine the upcoming start date based on selected_days_of_month
    if selected_days_of_month:
        today = datetime.now()
        day = selected_days_of_month[0]
        
        # If the selected day has already passed this month, set it for next month
        if today.day > day:
            start_date = today.replace(day=1) + timedelta(days=(day - 1))
            start_date = (start_date.replace(month=start_date.month + 1) if start_date.month < 12
                          else start_date.replace(year=start_date.year + 1, month=1))
        else:
            start_date = today.replace(day=day)

        parsed_data['start_date'] = start_date.strftime('%d-%m-%Y')
    else:
        # Fall back to parsing start_date_phrase if no selected_days_of_month is given
        start_date = dateparser.parse(
            start_date_phrase,
            settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': datetime.now()}
        )

        if not start_date:
            # Fallback to parsedatetime if dateparser fails
            cal = parsedatetime.Calendar()
            time_struct, parse_status = cal.parse(start_date_phrase, datetime.now())
            start_date = datetime(*time_struct[:6]) if parse_status == 1 else datetime.now().date()

        parsed_data['start_date'] = start_date.strftime('%d-%m-%Y') if start_date else datetime.now().strftime('%d-%m-%Y')

    # Set the default time if missing
    parsed_data['time'] = time_str if parsed_data.get('time') else '11:00 AM'

    # Clean up the output for clarity by removing start_date_phrase
    del parsed_data['start_date_phrase']

    return parsed_data

# Example usage
reminder_text = "Remind me to drink water every 2 hours."
parsed_data = process_reminder_text(reminder_text)

print("Parsed Reminder Data:", parsed_data)
