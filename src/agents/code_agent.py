# code_agent.py
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
import docx2txt
import PyPDF2
from utils.db_reference import get_db_reference_data

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

def generate_code_snippet(design_doc: str, user_input: str, uploaded_file, settings: dict, feedback_text: str = "") -> str:
    extracted_text = extract_text_from_file(uploaded_file)
    reference_context = get_db_reference_data(settings)
    reference_text = f"Reference Data:\n{reference_context}" if reference_context else ""

    
    

    prompt_template = PromptTemplate.from_template("""
You are a Code Generation AI.

{feedback_text}

Based on the following inputs, generate clean and functional code snippets:

Use python as the predominant language. If the user input requires us to use SQL please use it.

User Input:
{user_input}

Design Document:
{design_doc}

Document Content:
{file_content}

Use the connected database reference below to guide your decisions (if applicable).
{reference_text}

Feedback for Improvement:
{feedback_text}
If feedback is provided, you MUST revise your code accordingly and mention it in your output.
Always end your response with the following plain text (no markdown):
Decision: APPROVED or REJECTED  
Reason: [your reasoning here]
""")

    llm = ChatGroq(api_key=settings["groq_api_key"], model_name="qwen-2.5-coder-32b")
    chain = prompt_template | llm | StrOutputParser()

    return chain.invoke({
        "user_input": user_input,
        "design_doc": design_doc,
        "file_content": extracted_text,
        "reference_text": reference_text,
        "feedback_text": feedback_text
    })
