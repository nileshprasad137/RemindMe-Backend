import os
import dateparser
import parsedatetime
from datetime import datetime
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
        "   - For reminders that occur on specific days, extract these days as 'days_of_week' (e.g., ['Monday', 'Wednesday']).\n"
        "   - Set the default time to '11:00 AM' if no specific time is given.\n\n"
        
        "4. **Tags Extraction**:\n"
        "   - Identify single or double-word tags from the reminder that represent the main topics or categories.\n\n"
        
        "5. **Output Requirements**:\n"
        "   - Provide the information in a structured JSON format with the following fields: task, start_date_phrase, frequency, "
        "days_of_week, time, context, and tags.\n"
        
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

    start_date = dateparser.parse(
        start_date_phrase,
        settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': datetime.now()}
    )

    if not start_date:
        # Fallback to parsedatetime if dateparser fails
        cal = parsedatetime.Calendar()
        # Use parsedatetime for the relative date phrase
        time_struct, parse_status = cal.parse(start_date_phrase, datetime.now())
        if parse_status == 1:
            start_date = datetime(*time_struct[:6])
        else:
            # Fallback to today if parsedatetime fails
            start_date = datetime.now().date()

    # Fallback to today's date if parsing fails
    if start_date:
        parsed_data['start_date'] = start_date.strftime('%d-%m-%Y')
    else:
        parsed_data['start_date'] = datetime.now().strftime('%d-%m-%Y')  # Default to today if parsing fails

    # Set the default time if missing
    parsed_data['time'] = time_str if parsed_data.get('time') else '11:00 AM'

    # Clean up the output for clarity by removing start_date_phrase
    del parsed_data['start_date_phrase']

    return parsed_data

# Example usage
reminder_text = "Remind me to exercise on monday and wednesday."
parsed_data = process_reminder_text(reminder_text)

print("Parsed Reminder Data:", parsed_data)
