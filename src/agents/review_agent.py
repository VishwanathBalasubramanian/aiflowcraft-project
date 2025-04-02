from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from utils.db_reference import get_db_reference_data

def generate_review_summary(code: str, settings: dict, feedback_text: str = "") -> str:
    reference_context = get_db_reference_data(settings)
    reference_text = f"Reference Data:\n{reference_context}" if reference_context else ""

    prompt_template = PromptTemplate.from_template("""
You are a Senior Code Reviewer AI.

{feedback_text}

Review the following code and provide structured feedback.

code:
{code}

Use the connected database reference below to guide your decisions (if applicable).
{reference_text}

Reviewer Feedback (if any):
{feedback_text}

If feedback is provided, you MUST revise your review feedback accordingly.


Please analyze:
- Code quality (structure, readability, performance)
- Best practice adherence
- Maintainability
- Test coverage
- Alignment with user needs

Provide a structured review.

write test cases based on the {code} so that its clear on the UAT as well.

Always end your response with the following plain text (no markdown):

Decision: APPROVED or REJECTED  
Reason: [your reasoning here]
""")

    llm = ChatGroq(api_key=settings["groq_api_key"], model_name="llama-3.1-8b-instant")
    chain = prompt_template | llm | StrOutputParser()

    return chain.invoke({
        "code": code,
        "reference_text": reference_text,
        "feedback_text": feedback_text
    })
