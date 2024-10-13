import os
import shutil
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Paths
CHROMA_PATH = "chroma"
DATA_PATH = "data"

def main():
    generate_data_store()
    # parsed_data = {'task': 'exercise', 'frequency': 'every 3 days', 'days_of_week': [], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '14-10-2024'}
    # parsed_data = {'task': 'wish hbd', 'frequency': 'one-time', 'days_of_week': [], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '14-10-2024'}
    # parsed_data ={'task': 'exercise', 'frequency': 'weekly', 'days_of_week': ['Monday', 'Wednesday'], 'time': '11:00 AM', 'context': '', 'tags': [], 'start_date': '14-10-2024'}
    parsed_data = {'task': 'visit doctor', 'frequency': 'monthly', 'days_of_week': [], 'time': '11:00 AM', 'context': '', 'tags': ['health'], 'start_date': '14-10-2024'}
    generate_eventbridge_expression(
        task=parsed_data['task'],
        start_date=parsed_data['start_date'],
        time_str=parsed_data['time'],
        frequency=parsed_data['frequency'],
        days_of_week=parsed_data.get('days_of_week', [])
    )

def generate_data_store():
    documents = load_documents()
    chunks = split_text(documents)
    save_to_chroma(chunks)

def load_documents():
    loader = DirectoryLoader(DATA_PATH, glob="*.md")
    documents = loader.load()
    return documents

def split_text(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=100,
        length_function=len,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(chunks)} chunks.")
    return chunks

def save_to_chroma(chunks: list[Document]):
    # Clear out the database first
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)

    # Create a new DB from the documents
    db = Chroma.from_documents(
        chunks, OpenAIEmbeddings(openai_api_key=openai_api_key), persist_directory=CHROMA_PATH
    )
    db.persist()
    print(f"Saved {len(chunks)} chunks to {CHROMA_PATH}.")

def generate_eventbridge_expression(task, start_date, time_str, frequency, days_of_week):
    # Load the Chroma database
    embedding_function = OpenAIEmbeddings(openai_api_key=openai_api_key)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)
    model = ChatOpenAI(temperature=0, openai_api_key=openai_api_key, model="gpt-3.5-turbo")

    # Prepare the query text
    query_text = (
        f"I need to create an AWS EventBridge schedule expression for the following reminder:\n\n"
        f"Task: {task}\n"
        f"Start Date: {start_date} (in dd-mm-yyyy format)\n"
        f"Time: {time_str} (in hh:mm AM/PM format)\n"
        f"Frequency: {frequency}\n"
        f"Days of the Week: {', '.join(days_of_week) if days_of_week else 'N/A'}\n\n"
        "Use the AWS EventBridge documentation to convert `Start Date`, `Time`, `Frequency` and `Days of the Week`  into a schedule expression:\n"
        "- Use 'rate' expressions for simple intervals (e.g., 'rate(1 day)') (for example, alternate days is example of rate(2 days) and so on.) .\n"
        "- Use 'cron' expressions in AWS's 6-component format for more specific schedules (Minutes Hours Day-of-month Month Day-of-week Year). (Year should be just like 2024 and so on not dd-mm-yyyy)\n"
        "- Use 'at()' expressions for one-time schedules, formatted as 'at(YYYY-MM-DDTHH:MM:SS)'.\n"
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
    Question: Based on the provided task details, generate the correct AWS-compatible schedule expression.
    
    - Task: {task}
    - Start Date: {start_date}
    - Time: {time}
    - Frequency: {frequency}
    - Days of the Week: {days_of_week}
    
    If the schedule is a one-time event, provide an 'at()' expression.
    If it’s a recurring schedule with simple intervals, use a 'rate' expression.
    For more specific recurring schedules, generate a 'cron' expression in AWS's 6-component format.
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
    main()
