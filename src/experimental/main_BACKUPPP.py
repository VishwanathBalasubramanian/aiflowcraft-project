import streamlit as st
import pandas as pd
import graphviz
from io import StringIO

# Agent imports
from agents.user_input_agent import generate_user_stories
from agents.design_agent import generate_design_doc
from agents.code_agent import generate_code_snippet
from agents.review_agent import generate_review_summary
from agents.qa_agent import run_qa_check

# AI Review Logic
from utils.review_utils import run_ai_review

# Orchestrator
# from orchestrator.orchestrator_agent import run_orchestrator_with_live_logs
from orchestrator.langgraph_orchestrator import run_orchestrator_with_live_logs


# === Set page config ===
st.set_page_config(page_title="AIFlowCraft", layout="wide")

# === Initialize session state ===
def init_session():
    for key in ["userstories", "design", "code", "review", "qa"]:
        st.session_state.setdefault("stage", {}).setdefault(key, False)
        st.session_state.setdefault("approved", {}).setdefault(key, None)
        st.session_state.setdefault("review_mode", {}).setdefault(key, "AI")
        st.session_state.setdefault("rejection_comments", {}).setdefault(key, "")

    st.session_state.setdefault("resume_stage", None)
    st.session_state.setdefault("workflow_started", False)
    st.session_state.setdefault("full_log", [])
    st.session_state.setdefault("user_input_text", "")
    
    st.session_state.setdefault("config", {
        'groq_api_key': None,  # Initialize with a default value (None or an empty string)
    })
    # Initialize llm_data_file to None
    st.session_state.setdefault("llm_data_file", None)

    for key in ["userstories", "design", "code", "review", "qa"]:
        st.session_state.setdefault(f"{key}_output", None)
        st.session_state.setdefault(f"{key}_review", None)

init_session()

# === Sidebar Configuration ===
st.sidebar.title("🔧 Configuration")
st.session_state.config['groq_api_key'] = st.sidebar.text_input("Groq API Key", type="password")
st.sidebar.markdown("---")
st.sidebar.markdown("### 📂 Upload Excel/CSV for LLM Reference")
llm_file = st.sidebar.file_uploader("Upload file", type=["xlsx", "csv"])
if llm_file:
    st.session_state.llm_data_file = llm_file
    st.sidebar.success("File uploaded successfully!")

with st.sidebar.expander("🧠 Review Mode Configuration", expanded=True):
    st.markdown("### Select Review Mode for Each Stage:")
    for stage in ["userstories", "design", "code", "review", "qa"]:
        st.session_state.review_mode[stage] = st.radio(f"{stage.title()} Review Mode", ["AI", "User"], index=0)

# === Main UI ===
st.title("🧠 AIFlowCraft - Agentic AI Workflow Builder")

# === User Input Section ===
st.header("📥 User Input")
st.session_state.config['user_input_text'] = st.text_area("Enter your input or brief here:")
user_file = st.file_uploader("Or upload a Word/PDF file", type=["pdf", "docx"], key="doc_upload")

# === Start and Refresh Buttons ===
col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

with col1:
    valid_config = bool(st.session_state.config['groq_api_key'])
    valid_review_modes = all(st.session_state.review_mode.values())
    if valid_config and valid_review_modes:
        start_clicked = st.button("🚀 Start Workflow")
        if start_clicked:
            st.session_state.workflow_started = True

with col2:
    if st.button("🔄 Refresh Workflow"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

with col3:
    if st.button("📊 Show Workflow"):
        st.session_state.show_workflow = True

with col4:
    if st.button("🧹 Clear Workflow"):
        st.session_state.show_workflow = False

# === Show Workflow ===
if st.session_state.get("show_workflow"):
    st.subheader("📊 Workflow Visualization")
    dot = graphviz.Digraph()
    dot.node("Start")
    dot.node("UserStoriesAgent")
    dot.node("DesignAgent")
    dot.node("CodeAgent")
    dot.node("ReviewAgent")
    dot.node("QAAgent")
    dot.node("End")
    dot.edge("Start", "UserStoriesAgent")
    dot.edge("UserStoriesAgent", "DesignAgent", label="✔ Approve")
    dot.edge("UserStoriesAgent", "UserStoriesAgent", label="✖ Reject")
    dot.edge("DesignAgent", "CodeAgent", label="✔ Approve")
    dot.edge("DesignAgent", "DesignAgent", label="✖ Reject")
    dot.edge("CodeAgent", "ReviewAgent", label="✔ Approve")
    dot.edge("CodeAgent", "CodeAgent", label="✖ Reject")
    dot.edge("ReviewAgent", "QAAgent", label="✔ Approve")
    dot.edge("ReviewAgent", "CodeAgent", label="✖ Reject")
    dot.edge("QAAgent", "End", label="✔ Approve")
    dot.edge("QAAgent", "CodeAgent", label="✖ Reject")
    st.graphviz_chart(dot)

if st.session_state.workflow_started:
    log_placeholder = st.empty()
    log_expander = st.empty()
    with st.spinner("Running orchestrated workflow..."):
        try:
            results = {}
            seen_logs = set()
            if st.session_state.get("resume_stage"):
                seen_logs = set(st.session_state.get("full_log", []))
            else:
                st.session_state["full_log"] = []
            resume_stage = st.session_state.get("resume_stage")

            # ✅ Display resume status before running the orchestrator
            if resume_stage:
                st.markdown(f"🔁 **Resuming from stage:** `{resume_stage}`")
            else:
                st.markdown("🆕 **Starting full workflow from beginning**")
                
            for partial in run_orchestrator_with_live_logs(
                user_input=st.session_state.config['user_input_text'],
                uploaded_file=user_file,
                reference_file=st.session_state.llm_data_file,
                api_key=st.session_state.config['groq_api_key'],
                review_mode_user_stories=st.session_state.review_mode["userstories"],
                review_mode_design=st.session_state.review_mode["design"],
                review_mode_code=st.session_state.review_mode["code"],
                review_mode_review=st.session_state.review_mode["review"],
                review_mode_qa=st.session_state.review_mode["qa"],
                rejection_comments=st.session_state.rejection_comments,
                resume_stage=resume_stage,
                previous_outputs={
                "userstories": st.session_state.get("userstories_output"),
                "design": st.session_state.get("design_output"),
                "code": st.session_state.get("code_output"),
            }
            ):
                if "log" in partial:
                    new_lines = [line for line in partial["log"] if line not in seen_logs]
                    if new_lines:
                        for line in new_lines:
                            st.session_state["full_log"].append(line)
                            seen_logs.add(line)
                        log_placeholder.markdown(f"**{new_lines[-1]}**")
                results.update(partial)

            if st.session_state.get("full_log"):
                st.markdown("## 📜 Orchestration Log")
                for line in st.session_state["full_log"]:
                    st.write(line)

                # ✅ Append outputs, reviews, and feedbacks to the log
                keys = ["userstories", "design", "code", "review", "qa"]
                log_lines = []
                for key in keys:
                    output = st.session_state.get(f"{key}_output")
                    if output:
                        log_lines.append(f"🔎 Final Output ({key}): ✔️")

                    review = st.session_state.get(f"{key}_review")
                    if review:
                        log_lines.append(f"🔍 {review}")

                    feedback_log = st.session_state.get(f"{key}_feedback_log")
                    if feedback_log:
                        log_lines.append(feedback_log)

                # Show the extra details below the main log
                if log_lines:
                    st.markdown("## 📘 Final Stage Details")
                    for line in log_lines:
                        st.write(line)

            # === Resume Button after Failure ===
            if any("Max attempts for" in line for line in st.session_state["full_log"]):
                st.warning("⛔ Workflow halted due to max attempts.")
                if st.button("🔁 Resume from last failed stage", key="resume_failed_stage"):
                    stage_order = ["userstories", "design", "code", "review", "qa"]
                    last_failed = [s for s in stage_order if st.session_state.approved.get(s) is not True]
                    if last_failed:
                        st.session_state.resume_stage = last_failed[0]
                        st.session_state.workflow_started = True
                        st.rerun()

            for key in ["userstories", "design", "code", "review", "qa"]:
                if key in results and results[key].strip():
                    st.session_state[f"{key}_output"] = results[key]
                    st.session_state.stage[key] = True
                    st.session_state.approved[key] = True

            if all(st.session_state.approved.get(stage) is True for stage in ["userstories", "design", "code", "review", "qa"]):
                st.success("✅ Orchestration Complete")
                st.session_state.resume_stage = None
            else:
                st.warning("⚠️ Some stages are still pending. Workflow not fully complete.")

            if all(st.session_state.approved.get(stage) for stage in ["userstories", "design", "code", "review", "qa"]):
                st.session_state.resume_stage = None
        except Exception as e:
            st.error(f"❌ Failed to run orchestrator: {str(e)}")

# === Workflow Summary ===
st.markdown("---")
st.markdown("### 🧾 Workflow Summary")
cols = st.columns(len(st.session_state.stage))
for idx, (stage, status) in enumerate(st.session_state.stage.items()):
    label = stage.replace('_', ' ').capitalize()
    approval = st.session_state.approved[stage]
    if approval is True:
        cols[idx].success(f"✅ {label}")
    elif approval is False:
        cols[idx].error(f"❌ {label}")
    elif st.session_state.get(f"{stage}_output"):  # 🩹 Add this line
        cols[idx].warning(f"⏳ {label}")
    else:
        cols[idx].info(f"🔒 {label}")
        
# === Resume Button after Failure ===
if any("Max attempts for" in line for line in st.session_state["full_log"]):
    st.warning("⛔ Workflow halted due to max attempts.")
    if st.button("🔁 Resume from last failed stage"):
        stage_order = ["userstories", "design", "code", "review", "qa"]
        last_failed = [s for s in stage_order if st.session_state.approved.get(s) is not True]
        if last_failed:
            st.session_state.resume_stage = last_failed[0]
            st.session_state.workflow_started = True
            st.rerun()

# === Display Tabs with Outputs ===
if st.session_state.workflow_started:
    tabs = st.tabs(["📚 User Stories", "📐 Design", "💻 Code", "🔍 Review", "✅ QA"])
    keys = ["userstories", "design", "code", "review", "qa"]

    for tab, key in zip(tabs, keys):
        with tab:
            st.subheader(f"🔎 {key.title()} Output")
            output = st.session_state.get(f"{key}_output")

            if output:
                if key == "code":
                    st.code(output, language="python")
                else:
                    st.markdown(output)

            if st.session_state.review_mode.get(key) == "User" and st.session_state.stage.get(key):
                st.markdown("---")
                st.subheader(f"✍️ Manual Review for {key.title()} Stage")

                stage_order = ["userstories", "design", "code", "review", "qa"]
                current_index = stage_order.index(key)

                # Feedback input (only used if rejecting)
                feedback_key = f"{key}_feedback_tab"
                feedback = st.text_area("Enter feedback to reject (optional):", key=feedback_key)

                col1, col2 = st.columns(2)

                # Reject button logic for design stage
                with col1:
                    if st.button(f"❌ Reject {key.title()}", key=f"reject_{key}_tab"):
                        st.session_state.approved[key] = False
                        st.session_state.rejection_comments[key] = feedback
                        st.session_state[f"{key}_review"] = f"❌ Rejected by User\nReason: {feedback}"
                        st.session_state[f"{key}_feedback_log"] = f"[FEEDBACK → {key.upper()}]: {feedback}"

                        # ✅ Propagate rejection feedback to code if this is review or qa
                        if key == "review":
                            st.session_state.rejection_comments["code"] = feedback
                        elif key == "qa":
                            st.session_state.rejection_comments["code"] = feedback

                        # ✅ Always clear the rejected stage, even if previously approved
                        stage_order = ["userstories", "design", "code", "review", "qa"]
                        current_index = stage_order.index(key)

                        # Always reset rejected stage and downstream stages (even if previously approved)
                        for s in stage_order[current_index:]:
                            st.session_state.stage[s] = False
                            st.session_state.approved[s] = None
                            st.session_state.rejection_comments[s] = ""
                            st.session_state[f"{s}_output"] = None
                            st.session_state[f"{s}_review"] = None
                            st.session_state[f"{s}_feedback_log"] = None
  # Optional: clear stale feedback

                        st.session_state.resume_stage = key
                        st.session_state.workflow_started = True
                        st.rerun()





                with col2:
                    if st.button(f"✅ Approve {key.title()}", key=f"approve_{key}_tab"):
                        st.session_state.approved[key] = True
                        st.session_state.rejection_comments[key] = ""
                        if current_index + 1 < len(stage_order):
                            st.session_state.resume_stage = stage_order[current_index + 1]
                            st.session_state.workflow_started = True
                            st.rerun()
                        else:
                            st.session_state.stage[key] = True
                            st.session_state.resume_stage = None
                            st.success("✅ Workflow completed.")

        # Show AI review summary in tab if available
        if st.session_state.review_mode.get(key) == "AI" and st.session_state.get(f"{key}_review"):
            st.markdown("### 🤖 Structured Review:")
            st.info(st.session_state.get(f"{key}_review"))

# === Resume Button after Failure — render once after all tabs
if st.session_state.get("full_log"):
    if any("Max attempts for" in line for line in st.session_state["full_log"]):
        st.warning("⛔ Workflow halted due to max attempts.")
        if st.button("🔁 Resume from last failed stage", key="resume_failed_stage_bottom"):
            stage_order = ["userstories", "design", "code", "review", "qa"]
            last_failed = [s for s in stage_order if st.session_state.approved.get(s) is not True]
            if last_failed:
                failed_stage = last_failed[0]
                st.write(f"🔁 Will retry from failed stage: {failed_stage}")
                # Reset that stage & beyond
                for s in stage_order[stage_order.index(failed_stage):]:
                    st.session_state.stage[s] = False
                    st.session_state.approved[s] = None
                st.session_state.resume_stage = failed_stage
                st.session_state.workflow_started = True
                st.rerun()

