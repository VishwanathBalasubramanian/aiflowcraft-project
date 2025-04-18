# main.py (AIFlowCraft - Split Node LangGraph Flow with Live Logs)

import streamlit as st
import time
import graphviz
import streamlit.components.v1 as components
from orchestrator.orchestrator import run_generation, run_review, advance_node
# === Init session state ===
def init():
    if "workflow_started" not in st.session_state:
        st.session_state.workflow_started = False
    if "current_node" not in st.session_state:
        st.session_state.output = {}
        st.session_state.approved = {}
        st.session_state.feedback = {}
        st.session_state.review_mode = {
            "userstories": "AI",
            "design": "AI",
            "code": "AI",
            "review": "AI",
            "qa": "AI"
        }
        st.session_state.current_node = "userstories_gen"
        st.session_state.logs = []
        st.session_state.paused_stage = None
        st.session_state.config = {"groq_api_key": None, "db_type": "none", "db_path": ""}

init()

# === Sidebar ===
st.sidebar.title("🔧 Configuration")
st.session_state.config['groq_api_key'] = st.sidebar.text_input("Groq API Key", type="password", help="Used to access Groq LLMs. Required to generate outputs.")

# === Review Mode Configuration ===
with st.sidebar.expander("🧠 Review Mode Settings", expanded=True):
    stage_labels = {
    "userstories": "User Stories",
    "design": "Design",
    "code": "Coding Requirements",
    "review": "Code Quality",
    "qa": "QA"
    }

    for stage in ["userstories", "design", "code", "review", "qa"]:
        st.session_state.review_mode[stage] = st.radio(
            f"{stage_labels[stage]} Review",
            ["AI", "User"],
            index=0,
            key=f"mode_{stage}",
            help=f"Choose whether the {stage_labels[stage]} stage should be reviewed by AI or manually by you."
        )
    


with st.sidebar.expander("🗄️ Advanced Settings: Database", expanded=False):
    uploaded_db = st.file_uploader("Upload SQLite DB file", type=["db", "sqlite"], key="sqlite_upload", help="Upload a SQLite database file to use for reference data. If not provided, the flow will not use any reference data.")

    if uploaded_db:
        # Save file to a temporary location
        import tempfile
        import os
        import pandas as pd

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, uploaded_db.name)

        with open(temp_path, "wb") as f:
            f.write(uploaded_db.read())

        st.session_state.config["db_type"] = "sqlite"
        st.session_state.config["db_path"] = temp_path

        st.success(f"📁 DB Loaded: {uploaded_db.name}")

        # ✅ Optional Preview of tables
        import sqlite3
        try:
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
            table_names = [t[0] for t in tables]

            if table_names:
                st.markdown("### 🧾 Tables in DB:")
                for table in table_names:
                    st.write(f"- `{table}`")

                preview_table = st.selectbox("🔍 Preview Table", table_names)
                df_preview = pd.read_sql_query(f"SELECT * FROM {preview_table} LIMIT 5", conn)
                st.dataframe(df_preview)
            else:
                st.warning("No tables found in the database.")
        except Exception as e:
            st.error(f"⚠️ Failed to load DB tables: {e}")
        finally:
            conn.close()

    



# === GitHub Upload Configuration ===
with st.sidebar.expander("🌐 GitHub Upload (Optional)", expanded=False):
    enable_github = st.checkbox("Upload code to GitHub after QA", value=False)
    github_token = st.text_input("GitHub Token", type="password", help="Personal Access Token (PAT) with repo scope.")
    repo_name = st.text_input("GitHub Repo Slug", help="Format: username/repo (e.g., VishwanathBalasubramanian/aiflowcraft-generated)")
    target_path = st.text_input("Path to save file", help="Path to save the generated code (e.g., code/final_script.py)", value="code/generated_script.py")

    st.session_state.config["github"] = {
        "enabled": enable_github,
        "token": github_token,
        "repo": repo_name,
        "path": target_path
    }



# === Header ===
st.markdown("""
<div style='text-align: center; margin-top: 10px; margin-bottom: 40px;'>
    <div style='font-size: 60px;'>🧠</div>
    <div style='font-size: 48px; font-weight: 900; color: white; letter-spacing: -1px;'>AIFlowCraft</div>
    <div style='font-size: 22px; color: #CCCCCC; font-weight: 400;'>Human-AI Workflow Engine</div>
</div>
""", unsafe_allow_html=True)


def strip_unicode_emojis(text):
    return ''.join(c for c in text if c.isascii())

user_input_raw = st.text_area("📥 Enter your project brief:", key="user_input_text", help="Enter a brief description of your project. This will be used to generate the user stories, design, code, and review.")
user_input = strip_unicode_emojis(user_input_raw)
user_file = st.file_uploader("Upload a Word/PDF file", type=["pdf", "docx"], key="doc_file", help="Upload a Word or PDF file containing additional project details. This will be used to generate the user stories, design, code, and review.")

col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 Start Workflow", key="start_workflow"):
        if st.session_state.config['groq_api_key'] and user_input:
            st.session_state.workflow_started = True
            st.session_state.current_node = "userstories_gen"
            st.session_state.paused_stage = None
            st.rerun()
        else:
            st.warning("⚠️ Please provide both Groq API key and user input before starting.")
with col2:
    if st.button("🔁 Reset Workflow", key="reset_workflow"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# === Graphviz Flow ===
with st.expander("📌 Workflow Diagram"):
    dot = graphviz.Digraph()
    dot.attr(rankdir='HR')
    stages = ["userstories", "design", "code", "review", "qa"]
    dot.node("Start")
    dot.edge("Start", "userstories_gen")
    dot.node("END")
    for stage in stages:
        dot.node(f"{stage}_gen", f"{stage.title()} Gen")
        dot.node(f"{stage}_review", f"{stage.title()} Review")
        dot.edge(f"{stage}_gen", f"{stage}_review", label="Generated")
        if stage in ["review", "qa"]:
            dot.edge(f"{stage}_review", "code_gen", label="✖ Rejected")
        else:
            dot.edge(f"{stage}_review", f"{stage}_gen", label="✖ Rejected")
    dot.edge("userstories_review", "design_gen", label="✔ Approved")
    dot.edge("design_review", "code_gen", label="✔ Approved")
    dot.edge("code_review", "review_gen", label="✔ Approved")
    dot.edge("review_review", "qa_gen", label="✔ Approved")
    dot.edge("qa_review", "END", label="✔ Approved")
    st.graphviz_chart(dot)

# === Live Log ===
st.markdown("---")
st.markdown("### 🟢 Live Log")
if st.session_state.logs:
    latest_log = next((log for log in reversed(st.session_state.logs) if any(kw in log for kw in ["▶️", "⏸️", "✅", "❌"])), st.session_state.logs[-1])
    st.info(latest_log)


with st.expander("📜 Consolidated Workflow Logs"):
    for line in st.session_state.logs:
        st.write(line)
        
# === Trigger Node Execution ===
if st.session_state.get("workflow_started") and st.session_state.get("current_node") != "END" and st.session_state.get("paused_stage") is None:
    advance_node(user_input, user_file)


# === User Review UI ===
stage = st.session_state.paused_stage
if stage:
    st.subheader(f"✍️ User Review for {stage.title()}")
    feedback = st.text_area("Provide feedback (if rejecting):", key=f"fb_{stage}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"✅ Approve {stage.title()}"):
            st.session_state.approved[stage] = True
            st.session_state.feedback[stage] = ""
            next_map = {
                "userstories": "design_gen",
                "design": "code_gen",
                "code": "review_gen",
                "review": "qa_gen",
                "qa": "END"
            }
            st.session_state.current_node = next_map.get(stage, "END")
            st.session_state.paused_stage = None
            st.rerun()
    with col2:
        if st.button(f"❌ Reject {stage.title()}"):
            st.session_state.approved[stage] = False
            st.session_state.feedback[stage] = feedback
            st.session_state.current_node = "code_gen" if stage in ["review", "qa"] else f"{stage}_gen"
            st.session_state.paused_stage = None
            st.rerun()

# === Workflow Summary ===
st.markdown("---")
st.markdown("### 📊 Workflow Summary")
summary_cols = st.columns(5)
for i, stage in enumerate(["userstories", "design", "code", "review", "qa"]):
    status = st.session_state.approved.get(stage)
    if status is True:
        summary_cols[i].success(f"✔ {stage.title()}")
    elif status is False:
        summary_cols[i].error(f"✖ {stage.title()}")
    else:
        summary_cols[i].info(f"🔒 {stage.title()}")

# === Output Tabs ===

tabs = st.tabs([
    "📋 User Stories",
    "📐 Design",
    "💻 Code",
    "🔍 Review",
    "✅ QA"
])
for i, stage in enumerate(["userstories", "design", "code", "review", "qa"]):
    with tabs[i]:
        st.markdown(f"### 🧠 AI Generated {stage.title()} Output")
        out = st.session_state.output.get(stage, "")
        if out:
            st.markdown("```markdown" + out + "```")
        else:
            st.info("ℹ️ Waiting for the flow to Start.")
        
         # 💡 Show feedback used for this stage, if any
        feedback_used = st.session_state.feedback.get(stage, "")
        if feedback_used:
            st.markdown(f"#### 💡 Feedback Used")
            st.info(feedback_used)
            
        # ✅ Show approval decision and reason if available
        decision = st.session_state.approved.get(stage)
        if decision is True:
            reason = st.session_state.get("review_reasons", {}).get(stage, "")
            st.markdown("#### ✅ Approved by AI/User")
            st.success(reason)
        elif decision is False:
            reason = st.session_state.feedback.get(stage, "")
            st.markdown("#### ❌ Rejected by AI/User")
            st.error(reason)
