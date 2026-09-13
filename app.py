import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent.graph import build_graph
from agent.tools import store, load_dataframe

st.set_page_config(page_title="AI Data Analyst", page_icon="📊", layout="wide")
st.title("📊 AI Data Analyst")
st.caption("LangChain (tools) + LangGraph (orchestration) + Langbase (hosted prompts)")

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header("1. Load your data")
    uploaded = st.file_uploader("Upload a CSV", type=["csv"])
    if uploaded is not None:
        path = f"/tmp/{uploaded.name}"
        with open(path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.success(load_dataframe(path))
    elif store.df is None:
        if st.button("Use sample dataset (sales data)"):
            st.success(load_dataframe("data/sample_sales.csv"))

    if store.df is not None:
        st.write(f"**Loaded:** `{store.file_name}`")
        st.dataframe(store.df.head(5), use_container_width=True)

    st.divider()
    st.caption("Upload a CSV to begin.")