import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from core.data_manager import DataManager
from core.llm import LLMClient
from core.agents import AnalystEngine
from core.dashboard import build_dashboard

load_dotenv()

st.set_page_config(
    page_title="DataMind AI | Advanced Data Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "dm" not in st.session_state:
    st.session_state.dm = DataManager()
if "llm" not in st.session_state:
    st.session_state.llm = LLMClient()
if "engine" not in st.session_state:
    st.session_state.engine = AnalystEngine(st.session_state.llm)
if "messages" not in st.session_state:
    st.session_state.messages = []

dm = st.session_state.dm
llm = st.session_state.llm
engine = st.session_state.engine

st.title("📊 DataMind AI")
st.caption("Advanced multimode AI Data Analyst • Python + SQL + Dashboards + AI Insights")

with st.sidebar:
    st.header("📁 Data")
    uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"])
    if uploaded:
        if st.button("Load dataset", use_container_width=True):
            try:
                dm.load_uploaded(uploaded)
                st.session_state.messages = []
                st.success(f"Loaded {dm.name}: {dm.rows:,} rows × {dm.cols} columns")
            except Exception as e:
                st.error(str(e))

    if st.button("Load sample FMCG data", use_container_width=True):
        sample = os.path.join(os.path.dirname(__file__), "data", "sample_sales.csv")
        if os.path.exists(sample):
            dm.load_path(sample)
            st.session_state.messages = []
            st.success("Sample dataset loaded.")
        else:
            st.error("data/sample_sales.csv not found.")

    st.divider()
    st.header("⚙️ Settings")
    llm.model = st.text_input("Gemini model", value=llm.model)
    show_code = st.checkbox("Show generated SQL/Python", True)
    safe_mode = st.checkbox("Safe execution mode", True, help="Only read-only analysis operations are allowed.")

if dm.df is None:
    st.info("Upload a CSV/Excel file or load the sample FMCG dataset to begin.")
    st.markdown("""
### What this version can do
- 📊 Automatically profile datasets and build executive dashboards
- 💬 Answer natural-language analytical questions
- 🐍 Generate and execute read-only Python/Pandas analysis
- 🗄️ Generate and execute read-only SQL with DuckDB
- 📈 Create dynamic charts
- 💡 Generate business insights and recommendations
- 🔍 Show the generated SQL/Python for transparency
""")
    st.stop()

tabs = st.tabs(["📊 Dashboard", "💬 AI Analyst", "🐍 Python", "🗄️ SQL", "🔍 Data Explorer", "📋 Profile"])

with tabs[0]:
    st.subheader("Executive Dashboard")
    dashboard = build_dashboard(dm.df)
    cols = st.columns(4)
    for col, (label, value) in zip(cols, dashboard["kpis"][:4]):
        col.metric(label, value)
    st.divider()
    for chart in dashboard["charts"]:
        st.plotly_chart(chart, use_container_width=True)

with tabs[1]:
    st.subheader("AI Analyst")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("code"):
                with st.expander("Behind the scenes"):
                    st.code(m["code"], language=m.get("language", "text"))

    prompt = st.chat_input("Ask about revenue, trends, customers, inventory, profit...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                try:
                    result = engine.answer(dm.df, prompt, safe_mode=safe_mode)
                    st.markdown(result["answer"])
                    if result.get("table") is not None:
                        st.dataframe(result["table"], use_container_width=True)
                    if result.get("figure") is not None:
                        st.plotly_chart(result["figure"], use_container_width=True)
                    if show_code and result.get("code"):
                        with st.expander(f"Generated {result.get('mode','analysis').upper()}"):
                            st.code(result["code"], language=result.get("language", "text"))
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "code": result.get("code"),
                        "language": result.get("language", "text"),
                    })
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

with tabs[2]:
    st.subheader("🐍 Python / Pandas Analyst")
    q = st.text_area("Python question", placeholder="Find the top 10 brands by total revenue and show a bar chart.")
    if st.button("Run Python analysis", key="python_run") and q:
        try:
            result = engine.python_analysis(dm.df, q, safe_mode=safe_mode)
            st.markdown(result["answer"])
            if result.get("table") is not None:
                st.dataframe(result["table"], use_container_width=True)
            if result.get("figure") is not None:
                st.plotly_chart(result["figure"], use_container_width=True)
            if show_code:
                st.code(result["code"], language="python")
        except Exception as e:
            st.error(f"Python analysis failed: {e}")

with tabs[3]:
    st.subheader("🗄️ SQL Analyst")
    q = st.text_area("SQL question", placeholder="Show monthly revenue for 2024.")
    if st.button("Generate & run SQL", key="sql_run") and q:
        try:
            result = engine.sql_analysis(dm.df, q)
            st.markdown(result["answer"])
            st.code(result["code"], language="sql")
            if result.get("table") is not None:
                st.dataframe(result["table"], use_container_width=True)
            if result.get("figure") is not None:
                st.plotly_chart(result["figure"], use_container_width=True)
        except Exception as e:
            st.error(f"SQL analysis failed: {e}")

with tabs[4]:
    st.subheader("🔍 Data Explorer")
    st.write(f"**Dataset:** {dm.name}")
    st.write(f"**Shape:** {dm.rows:,} rows × {dm.cols} columns")
    st.dataframe(dm.df.head(100), use_container_width=True)

with tabs[5]:
    st.subheader("📋 Dataset Profile")
    profile = dm.profile()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{profile['rows']:,}")
    c2.metric("Columns", profile["columns"])
    c3.metric("Missing cells", f"{profile['missing_cells']:,}")
    c4.metric("Duplicate rows", f"{profile['duplicate_rows']:,}")
    st.dataframe(pd.DataFrame(profile["columns_info"]), use_container_width=True)
