from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_groq import ChatGroq


def run_llm_review(stage_output, stage_name, user_input, feedback, api_key):
    if not api_key:
        return "REJECTED", "❌ Missing API key for LLM review."

    llm = ChatGroq(temperature=0, groq_api_key=api_key, model_name="llama-3.1-8b-instant")

    prompt = ChatPromptTemplate.from_template(
        """
        You are an expert reviewer for an AI workflow system.

        Your job is to review the output generated for the stage: {stage_name}.

        ---
        🧾 User Input:
        {user_input}

        💡 Feedback (if any):
        {feedback}

        📤 Stage Output to Review:
        {stage_output}
        ---

        Evaluate the output based on the user input and feedback.
        Decide whether it should be APPROVED or REJECTED.

        Respond in the following format (plain text, no markdown or bullet points):
        Decision: APPROVED or REJECTED
        Reason: <short reason>
        """
    )

    chain = prompt | llm | StrOutputParser()
    raw_response = chain.invoke({
        "stage_output": stage_output,
        "stage_name": stage_name,
        "user_input": user_input,
        "feedback": feedback or "None"
    })

    # Extract decision and reason from plain text output
    decision_line = next((line for line in raw_response.splitlines() if "Decision:" in line), "Decision: REJECTED")
    reason_line = next((line for line in raw_response.splitlines() if "Reason:" in line), "Reason: No reason provided.")

    decision = decision_line.split(":", 1)[-1].strip().upper()
    reason = reason_line.split(":", 1)[-1].strip()

    return decision, reason
