from langgraph.graph import StateGraph
import streamlit as st
from typing import TypedDict, Literal

from agents.user_input_agent import generate_user_stories
from agents.design_agent import generate_design_doc
from agents.code_agent import generate_code_snippet
from agents.review_agent import generate_review_summary
from agents.qa_agent import run_qa_check
from utils.review_utils import run_llm_review
from utils.github_helper import upload_file_to_github

# Define state schema
class WorkflowState(TypedDict):
    user_input: str
    user_file: object
    config: dict

###################################
# Entry Function for main.py Hook #
###################################

def make_review_node(stage_name: str):
    def review_fn(state: WorkflowState) -> Literal["approved", "rejected", "pause"]:
        review_mode = st.session_state.review_mode.get(stage_name, "AI")
        output = st.session_state.output.get(stage_name, "")
        user_input = state["user_input"]
        config = state["config"]

        if review_mode == "AI":
            decision, reason = run_llm_review(
                stage_output=output,
                stage_name=stage_name,
                user_input=user_input,
                feedback=st.session_state.feedback.get(stage_name, ""),
                api_key=config.get("groq_api_key", "")
            )

            st.session_state.review_reasons = st.session_state.get("review_reasons", {})
            st.session_state.review_reasons[stage_name] = reason

            if decision == "APPROVED":
                st.session_state.approved[stage_name] = True
                st.session_state.feedback[stage_name] = ""
                st.session_state.logs.append(f"✅ Approved by AI: {stage_name}")
                return "approved"
            else:
                st.session_state.approved[stage_name] = False
                st.session_state.feedback[stage_name] = reason
                st.session_state.logs.append(f"❌ Rejected by AI: {stage_name}. Feedback saved.")
                return "rejected"
        else:
            st.session_state.paused_stage = stage_name
            st.session_state.logs.append(f"⏸️ Paused for User Review at: {stage_name}")
            return "pause"

    return review_fn

def run_langgraph_pipeline(user_input, user_file):
    state: WorkflowState = {
        "user_input": user_input,
        "user_file": user_file,
        "config": st.session_state.config
    }

    if st.session_state.current_node == "END":
        st.session_state.logs.append("🎯 LangGraph workflow already completed.")
        return

    builder = StateGraph(schema=WorkflowState)

    def userstories_gen_fn(input: WorkflowState):
        feedback = st.session_state.feedback.get("userstories", "")
        st.session_state.logs.append("▶️ Generating User Stories via LangGraph...")
        out = generate_user_stories(input["user_input"], input["user_file"], input["config"], feedback)
        st.session_state.output["userstories"] = out
        return input

    def design_gen_fn(input: WorkflowState):
        feedback = st.session_state.feedback.get("design", "")
        st.session_state.logs.append("▶️ Generating Design via LangGraph...")
        out = generate_design_doc(input["user_input"], input["user_file"], input["config"], feedback)
        st.session_state.output["design"] = out
        return input

    def code_gen_fn(input: WorkflowState):
        feedback = st.session_state.feedback.get("code", "")
        design = st.session_state.output.get("design", "")
        st.session_state.logs.append("▶️ Generating Code via LangGraph...")
        out = generate_code_snippet(design, input["user_input"], input["user_file"], input["config"], feedback)
        st.session_state.output["code"] = out
        return input

    def review_gen_fn(input: WorkflowState):
        feedback = st.session_state.feedback.get("review", "")
        code = st.session_state.output.get("code", "")
        st.session_state.logs.append("▶️ Generating Review Summary via LangGraph...")
        out = generate_review_summary(code, input["config"], feedback)
        st.session_state.output["review"] = out
        return input

    def qa_gen_fn(input: WorkflowState):
        feedback = st.session_state.feedback.get("qa", "")
        st.session_state.logs.append("▶️ Running QA via LangGraph...")
        out = run_qa_check(
            st.session_state.output.get("userstories"),
            st.session_state.output.get("design"),
            st.session_state.output.get("code"),
            input["config"],
            feedback
        )
        st.session_state.output["qa"] = out
        return input

    builder.add_node("userstories_gen", userstories_gen_fn)
    builder.add_node("design_gen", design_gen_fn)
    builder.add_node("code_gen", code_gen_fn)
    builder.add_node("review_gen", review_gen_fn)
    builder.add_node("qa_gen", qa_gen_fn)

    builder.add_node("userstories_review", make_review_node("userstories"))
    builder.add_node("design_review", make_review_node("design"))
    builder.add_node("code_review", make_review_node("code"))
    builder.add_node("review_review", make_review_node("review"))
    builder.add_node("qa_review", make_review_node("qa"))

    builder.add_edge("userstories_gen", "userstories_review")
    builder.add_conditional_edges("userstories_review", {
        "approved": "design_gen",
        "rejected": "userstories_gen",
        "pause": None
    })
    builder.add_edge("design_gen", "design_review")
    builder.add_conditional_edges("design_review", {
        "approved": "code_gen",
        "rejected": "design_gen",
        "pause": None
    })
    builder.add_edge("code_gen", "code_review")
    builder.add_conditional_edges("code_review", {
        "approved": "review_gen",
        "rejected": "code_gen",
        "pause": None
    })
    builder.add_edge("review_gen", "review_review")
    builder.add_conditional_edges("review_review", {
        "approved": "qa_gen",
        "rejected": "code_gen",
        "pause": None
    })
    builder.add_edge("qa_gen", "qa_review")
    builder.add_conditional_edges("qa_review", {
        "approved": "END",
        "rejected": "code_gen",
        "pause": None
    })

    builder.set_entry_point(st.session_state.current_node)
    flow = builder.compile()
    result_state, next_node = flow.invoke(state)

    st.session_state.current_node = next_node or "END"
    if st.session_state.current_node == "END":
        st.session_state.logs.append("🎉 Workflow completed via LangGraph.")
