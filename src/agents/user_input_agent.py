import pandas as pd
from typing import Optional
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
import docx2txt
import PyPDF2
import io
from utils.db_reference import get_db_reference_data  # ✅ New import

def extract_text_from_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    if uploaded_file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(uploaded_file)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text

    elif uploaded_file.name.endswith(".docx"):
        return docx2txt.process(uploaded_file)

    return ""

def generate_user_stories(
    user_text: str,
    uploaded_file,
    settings: dict,  # ✅ replaces reference_file and api_key separately
    feedback_text: str = ""
) -> str:
    if isinstance(user_text, dict):
        user_text = str(user_text)

    extracted_text = extract_text_from_file(uploaded_file)
    reference_context = get_db_reference_data(settings) 
    # Format the reference context if available
    reference_text = f"Reference Data:\n{reference_context}" if reference_context else ""
# ✅ Get from SQLite

    prompt_template = PromptTemplate.from_template("""
You are a Product Analyst AI.

{feedback_text}

Generate clear user stories based on the following context.

User Input:
{user_input}

Document Content:
{file_content}

Use the connected database reference below to guide your decisions (if applicable).
{reference_text}

Feedback for Improvement:
{feedback_text}

If feedback is provided, you MUST revise your user stories accordingly.

Write each user story in this format:
- US1: As a [type of user], I want to [goal] so that [benefit].

Always end your response with the following plain text (no markdown):
Decision: APPROVED or REJECTED  
Reason: [your reasoning here]
""")

    llm = ChatGroq(api_key=settings["groq_api_key"], model_name="llama-3.1-8b-instant")
    chain = prompt_template | llm | StrOutputParser()

    return chain.invoke({
        "user_input": user_text,
        "file_content": extracted_text,
        "reference_text": reference_text,
        "feedback_text": feedback_text
    })
