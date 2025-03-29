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


def generate_design_doc(user_input: str, uploaded_file, settings: dict, feedback_text: str = "") -> str:
    if isinstance(user_input, dict):
        user_input = str(user_input)

    file_content = extract_text_from_file(uploaded_file)
    reference_context = get_db_reference_data(settings)
    reference_text = f"Reference Data:\n{reference_context}" if reference_context else ""


    prompt_template = PromptTemplate.from_template("""
You are a Design Assistant AI.

Mention the feedback text in your response like this:
{feedback_text}

Generate a detailed design document based on the following context:

User Input:
{user_input}

Document Content:
{file_content}

Use the following database reference information to guide your response:
{reference_text}

Feedback for Improvement:
{feedback_text}

If feedback is provided, you MUST revise your design document accordingly.

The design should be structured, logical, and cover necessary system components.
Always end your response with the following plain text (no markdown):
Decision: APPROVED or REJECTED  
Reason: [your reasoning here]
""")

    llm = ChatGroq(api_key=settings["groq_api_key"], model_name="llama-3.1-8b-instant")
    chain = prompt_template | llm | StrOutputParser()

    return chain.invoke({
        "user_input": user_input,
        "file_content": file_content,
        "reference_text": reference_text,
        "feedback_text": feedback_text
    })
