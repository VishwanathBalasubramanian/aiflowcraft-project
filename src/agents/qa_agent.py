from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from utils.db_reference import get_db_reference_data


def run_qa_check(user_stories: str, design_doc: str, code_snippet: str, settings: dict, feedback_text: str = "") -> str:
    reference_context = get_db_reference_data(settings)
    reference_text = f"Reference Data:\n{reference_context}" if reference_context else ""


    prompt_template = PromptTemplate.from_template("""
You are a QA Engineer AI responsible for validating the code implementation against the design and user stories.

{feedback_text}

User Stories:
{user_stories}

Design Document:
{design_doc}

Code Snippet:
{code_snippet}

Use the connected database reference below to guide your decisions (if applicable).
{reference_text}

QA Feedback (if any):
{feedback_text}

If feedback is provided, you MUST revise your QA assessment accordingly.

Please perform the following:
- Functional correctness
- Coverage of edge cases
- Validation logic
- Adherence to requirements
- Potential issues or bugs

Generate a QA assessment including observations and a final recommendation.

Be a bit more lenient with the assessment.

Always end your response with the following plain text (no markdown):
Decision: APPROVED or REJECTED  
Reason: [your reasoning here]
""")

    llm = ChatGroq(api_key=settings["groq_api_key"], model_name="llama-3.1-8b-instant")
    chain = prompt_template | llm | StrOutputParser()

    return chain.invoke({
        "user_stories": user_stories,
        "design_doc": design_doc,
        "code_snippet": code_snippet,
        "reference_text": reference_text,
        "feedback_text": feedback_text
    })
