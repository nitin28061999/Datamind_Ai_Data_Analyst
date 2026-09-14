import json
import re
import pandas as pd
import plotly.express as px

from core.security import validate_python, validate_sql

class AnalystEngine:
    def __init__(self, llm):
        self.llm = llm

    def _schema(self, df):
        return "\n".join(f"- {c}: {df[c].dtype}, sample={df[c].dropna().head(2).tolist()}" for c in df.columns)

    def classify(self, question):
        q = question.lower()
        if any(x in q for x in ["sql", "query", "select", "join", "group by"]):
            return "sql"
        if any(x in q for x in ["dashboard", "kpi", "visual", "chart", "plot"]):
            return "dashboard"
        return "python"

    def python_analysis(self, df, question, safe_mode=True):
        prompt = f"""
You are a senior Python data analyst.
Dataset columns:
{self._schema(df)}

Question: {question}

Return ONLY executable Python statements, no markdown.
Rules:
- A pandas DataFrame named df already exists.
- Do not import anything.
- Do not access files, network, OS, subprocesses, environment variables, or Python internals.
- Store the final tabular answer in a variable named result.
- If a chart is useful, create Plotly figure in variable fig only if plotly.express is already available; otherwise omit it.
"""
        code = self.llm.extract_code(self.llm.generate(prompt), "python")
        validate_python(code)
        env = {"df": df.copy(), "pd": pd}
        # Plotly is injected only as a controlled library object.
        env["px"] = px
        exec(code, {"__builtins__": {}}, env)
        result = env.get("result")
        fig = env.get("fig")
        if result is not None and not isinstance(result, pd.DataFrame):
            if isinstance(result, pd.Series):
                result = result.to_frame()
            else:
                result = pd.DataFrame({"result": [result]})
        answer = self.summarize(question, result, "Python")
        return {"answer": answer, "code": code, "language": "python", "mode": "python", "table": result, "figure": fig}

    def sql_analysis(self, df, question):
        prompt = f"""
You are a senior SQL analyst using DuckDB.
A table named dataset contains this dataframe.
Columns:
{self._schema(df)}

Question: {question}

Return ONLY one read-only SQL query.
Rules: SELECT/WITH only. No mutation. Use DuckDB SQL.
"""
        sql = self.llm.extract_code(self.llm.generate(prompt), "sql")
        validate_sql(sql)
        from core.data_manager import DataManager
        # execute without relying on global state
        import duckdb
        con = duckdb.connect()
        try:
            con.register("dataset", df)
            result = con.execute(sql).df()
        finally:
            con.close()
        answer = self.summarize(question, result, "SQL")
        return {"answer": answer, "code": sql, "language": "sql", "mode": "sql", "table": result, "figure": self.auto_chart(result)}

    def summarize(self, question, result, mode):
        if result is None or result.empty:
            return "The analysis returned no rows."
        preview = result.head(20).to_dict(orient="records")
        prompt = f"""
You are a business analyst. Explain the result of this {mode} analysis.
Question: {question}
Result: {json.dumps(preview, default=str)}
Give 2-5 concise business insights. Do not invent values not present in the result.
"""
        try:
            return self.llm.generate(prompt)
        except Exception:
            return f"Analysis completed successfully using {mode}. The result is shown below."

    def auto_chart(self, result):
        if result is None or result.empty or len(result.columns) < 2:
            return None
        cols = list(result.columns)
        numeric = [c for c in cols if pd.api.types.is_numeric_dtype(result[c])]
        categorical = [c for c in cols if c not in numeric]
        if numeric and categorical:
            return px.bar(result.head(20), x=categorical[0], y=numeric[0], title=f"{numeric[0]} by {categorical[0]}")
        if len(numeric) >= 2:
            return px.scatter(result, x=numeric[0], y=numeric[1])
        return None

    def answer(self, df, question, safe_mode=True):
        mode = self.classify(question)
        if mode == "sql":
            return self.sql_analysis(df, question)
        if mode == "dashboard":
            return {"answer": "Use the Dashboard tab for the automatically generated executive dashboard.", "mode": "dashboard", "table": None, "figure": None}
        return self.python_analysis(df, question, safe_mode=safe_mode)
