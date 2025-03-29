import streamlit as st
import pandas as pd
import graphviz
import time
import os
import sqlite3

# === Agent Imports ===
from agents.user_input_agent import generate_user_stories
from agents.design_agent import generate_design_doc
from agents.code_agent import generate_code_snippet
from agents.review_agent import generate_review_summary
from agents.qa_agent import run_qa_check

# === AI Review Logic ===
from utils.review_utils import run_ai_review

# === Orchestrator ===
from orchestrator.langgraph_orchestrator import run_langgraph_workflow_with_logs

# === Page Config ===
st.set_page_config(page_title="AIFlowCraft", layout="wide")

# === Session Init ===
def init_session():
    for key in ["userstories", "design", "code", "review", "qa"]:
        st.session_state.setdefault("stage", {}).setdefault(key, False)
        st.session_state.setdefault("approved", {}).setdefault(key, None)
        st.session_state.setdefault("review_mode", {}).setdefault(key, "AI")
        st.session_state.setdefault("rejection_comments", {}).setdefault(key, "")
        st.session_state.setdefault(f"{key}_output", None)
        st.session_state.setdefault(f"{key}_review", None)

    st.session_state.setdefault("resume_stage", None)
    st.session_state.setdefault("workflow_started", False)
    st.session_state.setdefault("full_log", [])
    st.session_state.setdefault("user_input_text", "")
    st.session_state.setdefault("llm_data_file", None)
    st.session_state.setdefault("config", {'groq_api_key': None})
    st.session_state.setdefault("show_workflow", False)

init_session()

# === Sidebar ===
st.sidebar.title("🔧 Configuration")
st.session_state.config['groq_api_key'] = st.sidebar.text_input("Groq API Key", type="password")
st.sidebar.markdown("---")

# SQLite DB
use_db = st.sidebar.checkbox("Use SQLite DB as Reference")
if use_db:
    db_file = st.sidebar.file_uploader("Upload SQLite DB", type=["db"])
    if db_file:
        import tempfile
        temp_dir = tempfile.gettempdir()
        db_path = os.path.join(temp_dir, db_file.name)
        with open(db_path, "wb") as f:
            f.write(db_file.getbuffer())
        st.session_state.config["db_type"] = "sqlite"
        st.session_state.config["db_path"] = db_path
        st.sidebar.success(f"✅ DB uploaded: {db_path}")
    else:
        st.session_state.config["db_type"] = "sqlite"
        st.session_state.config["db_path"] = ""
        st.warning("⚠️ Please upload a SQLite .db file.")
else:
    st.session_state.config["db_type"] = "none"
    st.session_state.config["db_path"] = ""

# Review Mode Config
st.sidebar.markdown("---")
with st.sidebar.expander("🧠 Review Mode Configuration", expanded=True):
    for stage in ["userstories", "design", "code", "review", "qa"]:
        st.session_state.review_mode[stage] = st.radio(
            f"{stage.title()} Review Mode",
            ["AI", "User"],
            index=0,
            key=f"{stage}_review_mode"
        )

# === Main UI ===
st.title("🧠 AIFlowCraft - Agentic AI Workflow Builder")
st.header("📥 User Input")
st.session_state.config['user_input_text'] = st.text_area("Enter your input or brief here:")
user_file = st.file_uploader("Or upload a Word/PDF file", type=["pdf", "docx"], key="doc_upload")

# Buttons
col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 Start Workflow"):
        st.session_state.workflow_started = True
with col2:
    if st.button("🔄 Refresh Workflow"):
        preserved_keys = ["config", "llm_data_file"]
        for key in list(st.session_state.keys()):
            if key not in preserved_keys:
                del st.session_state[key]
        st.rerun()

# Workflow Graph
with st.expander("📊 Show Workflow Graph", expanded=st.session_state.get("show_workflow", False)):
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

# === Workflow Execution ===
if st.session_state.workflow_started:
    log_placeholder = st.empty()
    log_expander = st.expander("📜 Full Orchestration Log", expanded=True)
    spinner_placeholder = st.empty()

    try:
        results = {}
        seen_logs = set(st.session_state.get("full_log", []))
        if st.session_state.get("resume_stage"):
            seen_logs = set(st.session_state.get("full_log", []))
        else:
            st.session_state["full_log"] = []
        resume_stage = st.session_state.get("resume_stage")

        if resume_stage:
            st.markdown(f"🔁 **Resuming from stage:** `{resume_stage}`")
        else:
            st.markdown("🆕 **Starting full workflow from beginning**")
        st.markdown("⏳ Running orchestrated workflow...")

        # Process each partial result from the orchestrator stream
        for partial in run_langgraph_workflow_with_logs(
            user_input=st.session_state.config['user_input_text'],
            uploaded_file=user_file,
            config=st.session_state.config,
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
                "review": st.session_state.get("review_output"),
                "qa": st.session_state.get("qa_output"),
            }
        ):
            # Unwrap the state from LangGraph
            # Unified unwrapping logic for LangGraph results
            if "__state__" in partial:
                current_state = partial["__state__"]
            elif "__end__" in partial:
                current_state = partial["__end__"]
            elif "state" in partial:
                current_state = partial["state"]
            else:
                current_state = partial
  # Fallback if already unwrapped

            # Update logs
            if "log" in current_state:
                new_lines = [line for line in current_state["log"] if line not in seen_logs]
                if new_lines:
                    for line in new_lines:
                        st.session_state["full_log"].append(line)
                        seen_logs.add(line)
                    log_placeholder.markdown(f"**{new_lines[-1]}**")
                    with log_expander:
                        for line in st.session_state["full_log"]:
                            st.markdown(line)
                time.sleep(0.2)

            # Update outputs for each stage
            if "output" in current_state:
                for key, val in current_state["output"].items():
                    if isinstance(val, str) and val.strip():
                        st.session_state[f"{key}_output"] = val
                        st.session_state.stage[key] = True

            # Check for pause flag
            if current_state.get("pause"):
                # Save which stage is paused for manual review
                for stage, flag in current_state.get("pause_flags", {}).items():
                    if flag:
                        st.session_state["paused_stage"] = stage
                        st.warning(f"⏸️ Awaiting manual review at stage: `{stage}`")
                        break
                break  # Stop streaming if paused

            results.update(current_state)

        spinner_placeholder.empty()

        # Finalize approvals based on the last update
        for key in ["userstories", "design", "code", "review", "qa"]:
            approved = results.get("approved", {}).get(key)
            if approved is True:
                st.session_state.approved[key] = True
                st.session_state.stage[key] = True
            elif approved is False:
                st.session_state.approved[key] = False

        if all(st.session_state.approved.get(stage) is True for stage in ["userstories", "design", "code", "review", "qa"]):
            st.success("✅ Orchestration Complete")
            st.session_state.resume_stage = None
        else:
            st.warning("⚠️ Some stages are still pending. Workflow not fully complete.")

    except Exception as e:
        spinner_placeholder.empty()
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
    elif st.session_state.get(f"{stage}_output"):
        cols[idx].warning(f"⏳ {label}")
    else:
        cols[idx].info(f"🔒 {label}")


# === Display Tabs with Outputs ===
if st.session_state.workflow_started:
    tabs = st.tabs(["📚 User Stories", "📐 Design", "💻 Code", "🔍 Review", "✅ QA"])
    keys = ["userstories", "design", "code", "review", "qa"]

    for tab, key in zip(tabs, keys):
        with tab:
            st.subheader(f"🔎 {key.title()} Output")
            output = st.session_state.get(f"{key}_output")

            # Fallback for resume if output is not set
            if not output and st.session_state.get("resume_stage") == key:
                for line in reversed(st.session_state.get("full_log", [])):
                    if line.startswith(f"🧪 Raw {key} result:"):
                        output = line.replace(f"🧪 Raw {key} result:", "").strip()
                        break

            if output:
                if key == "code":
                    st.code(output, language="python")
                else:
                    st.markdown(output)
            else:
                st.warning(f"⚠️ No valid string output found for **{key}**.")

            # AI Review Summary (for AI mode)
            if st.session_state.review_mode.get(key) == "AI" and st.session_state.get(f"{key}_review"):
                st.markdown("### 🤖 Structured Review:")
                st.info(st.session_state.get(f"{key}_review"))

            # Manual Review UI for User mode
            if st.session_state.review_mode.get(key) == "User" and output:
                st.markdown("---")
                st.subheader(f"✍️ Manual Review for {key.title()} Stage")

                col1, col2 = st.columns(2)
                with col1:
                    st.session_state[f"{key}_approved"] = st.radio(
                        f"Do you approve the {key.title()} output?",
                        [None, True, False],
                        format_func=lambda x: "—" if x is None else ("✅ Approve" if x else "❌ Reject"),
                        key=f"{key}_approval_radio"
                    )

                with col2:
                    st.session_state[f"{key}_feedback"] = st.text_area(
                        "Enter feedback to reject (if applicable):",
                        key=f"{key}_feedback_text"
                    )

                if st.session_state[f"{key}_approved"] is not None:
                    st.markdown("✅ Decision recorded. Click 'Start Workflow' to resume.")
                else:
                    st.info("⏸️ Waiting for your approval/rejection decision...")


# Prevent auto-run if waiting for manual input
if any(
    st.session_state.review_mode.get(k) == "User" and st.session_state.get(f"{k}_approved") is None
    for k in ["userstories", "design", "code", "review", "qa"]
):
    st.warning("⏸️ Waiting for manual review decisions. Make your selections in the tabs.")
    st.stop()
