from agents.user_input_agent import generate_user_stories
from agents.design_agent import generate_design_doc
from agents.code_agent import generate_code_snippet
from agents.review_agent import generate_review_summary
from agents.qa_agent import run_qa_check
from utils.review_utils import run_llm_review
from utils.db_reference import get_db_reference_data
from utils.github_helper import upload_file_to_github
import streamlit as st


def run_generation(stage, user_input, user_file):
    st.session_state.logs.append(f"\u25b6\ufe0f Generating {stage.title()}...")

    feedback = st.session_state.feedback.get(stage, "")
    config = st.session_state.config

    if feedback and feedback.lower() != "none":
        feedback_text = f"\ud83d\udcdd Feedback Acknowledged: {feedback}"
        st.session_state.logs.append(f"\ud83d\udcac Feedback acknowledged for {stage}: {feedback}")
    else:
        feedback_text = ""

    reference_context = get_db_reference_data(config)
    reference_text = f"Reference Data:\n{reference_context}" if reference_context else ""

    if reference_text:
        st.session_state.logs.append(f"\ud83d\udce6 Reference Data Used in {stage}: \u2705 Database reference injected")
    else:
        st.session_state.logs.append(f"\ud83d\udce6 Reference Data Used in {stage}: \u274c No DB reference available")

    if stage == "userstories":
        out = generate_user_stories(user_input, user_file, config, feedback_text)
    elif stage == "design":
        out = generate_design_doc(user_input, user_file, config, feedback_text)
    elif stage == "code":
        out = generate_code_snippet(st.session_state.output.get("design"), user_input, user_file, config, feedback_text)
    elif stage == "review":
        out = generate_review_summary(st.session_state.output.get("code"), config, feedback_text)
    elif stage == "qa":
        out = run_qa_check(
            st.session_state.output.get("userstories"),
            st.session_state.output.get("design"),
            st.session_state.output.get("code"),
            config, feedback_text
        )

    st.session_state.output[stage] = out
    st.session_state.current_node = f"{stage}_review"
    st.rerun()


def run_review(stage, next_stage, fallback_stage, user_input):
    mode = st.session_state.review_mode[stage]
    output = st.session_state.output.get(stage, "")

    if mode == "AI":
        decision, reason = run_llm_review(
            stage_output=output,
            stage_name=stage,
            user_input=user_input,
            feedback=st.session_state.feedback.get(stage, ""),
            api_key=st.session_state.config["groq_api_key"]
        )
        st.session_state.logs.append(f"\ud83e\udd16 AI Review [{stage}]: {decision} - {reason}")

        st.session_state.review_reasons = st.session_state.get("review_reasons", {})
        st.session_state.review_reasons[stage] = reason

        if decision == "APPROVED":
            st.session_state.approved[stage] = True
            st.session_state.feedback[stage] = ""
            st.session_state.logs.append(f"\u2705 Approved by AI: {stage}")

            if stage == "qa":
                github_cfg = st.session_state.config.get("github", {})
                if github_cfg.get("enabled"):
                    code = st.session_state.output.get("code", "")
                    token = github_cfg.get("token")
                    repo = github_cfg.get("repo")
                    path = github_cfg.get("path")

                    if token and repo and path:
                        try:
                            st.session_state.logs.append(
                                f"\ud83d\udd27 Attempting GitHub upload with:\n- Repo: {repo}\n- Path: {path}\n- Token present: {'Yes' if token else 'No'}"
                            )
                            status, response = upload_file_to_github(token, repo, path, code)
                            if status in [200, 201]:
                                st.session_state.logs.append(f"\ud83d\ude80 Code uploaded to GitHub: `{repo}/{path}`")
                            else:
                                st.session_state.logs.append(f"\u274c GitHub upload failed: {response.get('message')}")
                        except Exception as e:
                            st.session_state.logs.append(f"\u274c GitHub upload error: {str(e)}")
                    else:
                        st.session_state.logs.append("\u26a0\ufe0f Missing GitHub token, repo, or path.")

            st.session_state.current_node = next_stage
        else:
            st.session_state.approved[stage] = False
            st.session_state.feedback[stage] = reason
            st.session_state.logs.append(f"\u274c Rejected by AI: {stage}. Feedback saved.")
            st.session_state.current_node = fallback_stage
        st.rerun()
    else:
        st.session_state.paused_stage = stage
        st.session_state.logs.append(f"\u23f8\ufe0f Waiting for User Review at: {stage}")


def advance_node(user_input, user_file):
    node = st.session_state.current_node
    transitions = {
        "userstories_gen": lambda: run_generation("userstories", user_input, user_file),
        "userstories_review": lambda: run_review("userstories", "design_gen", "userstories_gen", user_input),
        "design_gen": lambda: run_generation("design", user_input, user_file),
        "design_review": lambda: run_review("design", "code_gen", "design_gen", user_input),
        "code_gen": lambda: run_generation("code", user_input, user_file),
        "code_review": lambda: run_review("code", "review_gen", "code_gen", user_input),
        "review_gen": lambda: run_generation("review", user_input, user_file),
        "review_review": lambda: run_review("review", "qa_gen", "code_gen", user_input),
        "qa_gen": lambda: run_generation("qa", user_input, user_file),
        "qa_review": lambda: run_review("qa", "END", "code_gen", user_input)
    }
    if node in transitions:
        transitions[node]()
    elif node == "END":
        st.success("\ud83c\udf89 Workflow complete! All stages approved.")
        st.session_state.logs.append("\ud83c\udfaf Workflow completed successfully. All stages approved.")
