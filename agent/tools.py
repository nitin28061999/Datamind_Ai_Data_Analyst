"""
Pandas-backed tools exposed to the LangChain tool-calling agent.

Design choices worth knowing for the demo:
- A single in-memory DataStore holds the currently loaded dataframe. This keeps
  the tool functions simple (no dataframe passed through the LLM call) and
  matches how the Streamlit session will use it.
- `run_pandas_query` intentionally does NOT allow arbitrary code execution.
  It evaluates a single expression with a locked-down builtins dict and a
  keyword blocklist, so the LLM can query the data flexibly without being able
  to import modules, write files, or mutate the dataframe. For a real
  production rollout, swap this for a vetted query DSL or a sandboxed process.
"""
import pandas as pd
from langchain_core.tools import tool


class DataStore:
    def __init__(self):
        self.df: "pd.DataFrame | None" = None
        self.file_name: "str | None" = None


store = DataStore()


def load_dataframe(path: str) -> str:
    """Not exposed to the LLM directly — called from the UI when a file is uploaded."""
    store.df = pd.read_csv(path)
    store.file_name = path
    return f"Loaded `{path}` — {store.df.shape[0]} rows x {store.df.shape[1]} columns."


@tool
def get_data_summary() -> str:
    """Return the shape, column names, dtypes, and a small sample of the currently loaded dataset."""
    if store.df is None:
        return "No dataset loaded."
    df = store.df
    return (
        f"Shape: {df.shape}\n\n"
        f"Columns & types:\n{df.dtypes.to_string()}\n\n"
        f"Sample rows:\n{df.head(3).to_string()}"
    )


@tool
def get_column_values(column: str) -> str:
    """Return up to 20 unique values for a given column name. Use this to discover valid filter values."""
    if store.df is None:
        return "No dataset loaded."
    if column not in store.df.columns:
        return f"Column '{column}' not found. Available columns: {list(store.df.columns)}"
    vals = store.df[column].dropna().unique()[:20]
    return f"Unique values in '{column}' (up to 20 shown): {list(vals)}"


@tool
def calculate_aggregate(column: str, operation: str, group_by: str = "") -> str:
    """
    Calculate an aggregate statistic on a numeric column.
    operation must be one of: sum, mean, median, min, max, count, std.
    group_by is optional — pass a column name to group before aggregating.
    """
    if store.df is None:
        return "No dataset loaded."
    df = store.df
    if column not in df.columns:
        return f"Column '{column}' not found. Available columns: {list(df.columns)}"
    valid_ops = {"sum", "mean", "median", "min", "max", "count", "std"}
    if operation not in valid_ops:
        return f"Invalid operation '{operation}'. Choose from {sorted(valid_ops)}."
    try:
        if group_by:
            if group_by not in df.columns:
                return f"Group-by column '{group_by}' not found."
            result = getattr(df.groupby(group_by)[column], operation)()
            return result.to_string()
        return str(getattr(df[column], operation)())
    except Exception as e:
        return f"Error computing aggregate: {e}"


@tool
def run_pandas_query(query_description: str, pandas_expression: str) -> str:
    """
    Evaluate a single, read-only pandas expression against the loaded dataframe (bound as `df`).
    query_description: a short plain-english note on what this computes (used for logging/UI).
    pandas_expression: e.g. "df[df['region']=='North']['revenue'].sum()".
    Only read-only expressions are allowed — no imports, exec, file I/O, or mutation.
    """
    if store.df is None:
        return "No dataset loaded."
    banned = [
        "import", "exec", "eval(", "os.", "sys.", "open(", "__",
        "subprocess", "to_csv", "to_excel", "drop(", "del ", "write",
    ]
    if any(b in pandas_expression for b in banned):
        return "Blocked: expression contains a disallowed operation."
    try:
        df = store.df  # noqa: F841 (referenced inside eval's local scope)
        result = eval(pandas_expression, {"__builtins__": {}}, {"df": df, "pd": pd})
        return f"[{query_description}] -> {result}"
    except Exception as e:
        return f"Error evaluating expression: {e}"


TOOLS = [get_data_summary, get_column_values, calculate_aggregate, run_pandas_query]
