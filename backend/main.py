from io import BytesIO
from typing import TypedDict
import ast, os, re, uuid
import pandas as pd
import duckdb
import plotly.express as px
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FRONTEND_URL = os.getenv("FRONTEND_URL", "*")
MAX_ROWS = int(os.getenv("MAX_ROWS", "250000"))

app = FastAPI(title="DataMind AI Analyst API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL != "*" else ["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

sessions = {}

def session(sid):
    if sid not in sessions:
        sessions[sid] = {"df": None, "filename": None, "history": []}
    return sessions[sid]

def profile(sid):
    s = session(sid)
    if s["df"] is None: raise ValueError("No dataset loaded.")
    df = s["df"]
    return {
        "filename": s["filename"], "rows": len(df), "columns": len(df.columns),
        "duplicates": int(df.duplicated().sum()),
        "missing_cells": int(df.isna().sum().sum()),
        "numeric_columns": [str(c) for c in df.select_dtypes("number").columns],
        "columns_detail": [
            {"name": str(c), "dtype": str(df[c].dtype),
             "missing": int(df[c].isna().sum()),
             "unique": int(df[c].nunique(dropna=True))}
            for c in df.columns
        ],
    }

@app.get("/")
def root(): return {"service": "DataMind AI Analyst API", "status": "running"}

@app.get("/health")
def health(): return {"status": "healthy"}

@app.post("/api/session")
def create_session():
    sid = str(uuid.uuid4()); session(sid)
    return {"session_id": sid}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...), session_id: str = Form(...)):
    try:
        data = await file.read()
        if len(data) > 25 * 1024 * 1024:
            raise ValueError("File exceeds 25 MB limit.")
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(BytesIO(data))
        elif file.filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(BytesIO(data))
        else:
            raise ValueError("Only CSV and Excel files are supported.")
        if len(df) > MAX_ROWS:
            raise ValueError(f"Dataset exceeds {MAX_ROWS:,} rows.")
        for c in df.columns:
            if any(x in str(c).lower() for x in ("date", "time", "timestamp")):
                parsed = pd.to_datetime(df[c], errors="coerce")
                if parsed.notna().mean() >= .7: df[c] = parsed
        s = session(session_id); s["df"] = df; s["filename"] = file.filename; s["history"] = []
        return profile(session_id)
    except Exception as e:
        raise HTTPException(400, str(e))

def run_sql(sid, sql):
    s = session(sid)
    if s["df"] is None: raise ValueError("No dataset loaded.")
    q = sql.strip().rstrip(";"); up = q.upper()
    if not (up.startswith("SELECT") or up.startswith("WITH")): raise ValueError("Only SELECT/WITH SQL is allowed.")
    if any(x in up for x in ("INSERT","UPDATE","DELETE","DROP","ALTER","CREATE","COPY","ATTACH","DETACH","INSTALL","LOAD")):
        raise ValueError("Unsafe SQL statement blocked.")
    con = duckdb.connect(":memory:")
    try:
        con.register("dataset", s["df"])
        return con.execute(q).df()
    finally: con.close()

BLOCKED = {"eval","exec","compile","open","__import__","input","globals","locals","vars","breakpoint"}
def validate_python(code):
    for n in ast.walk(ast.parse(code, mode="exec")):
        if isinstance(n, (ast.Import, ast.ImportFrom)): raise ValueError("Imports are not allowed. Use preloaded pd, px and df.")
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in BLOCKED:
            raise ValueError(f"Blocked function: {n.func.id}")

def run_python(sid, code):
    s = session(sid)
    if s["df"] is None: raise ValueError("No dataset loaded.")
    validate_python(code)
    safe = {"len":len,"min":min,"max":max,"sum":sum,"round":round,"abs":abs,
            "sorted":sorted,"str":str,"int":int,"float":float,"list":list,
            "dict":dict,"set":set,"tuple":tuple,"range":range,"enumerate":enumerate,"zip":zip}
    loc = {"df":s["df"].copy(),"pd":pd,"px":px}
    exec(code, {"__builtins__":safe, "pd":pd, "px":px, "df":s["df"].copy()}, loc)
    result, fig = loc.get("result"), loc.get("fig")
    if isinstance(result, pd.DataFrame):
        result = result.head(100).where(pd.notna(result), None).to_dict("records")
    elif isinstance(result, pd.Series):
        result = result.head(100).reset_index().where(pd.notna(result), None).to_dict("records")
    return {"result": result, "chart": fig.to_dict() if fig is not None else None, "code": code}

class State(TypedDict, total=False):
    session_id: str; question: str; mode: str; result: object; code: str; sql: str; chart: object; answer: str

class Analyst:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(model=MODEL, google_api_key=API_KEY, temperature=0) if API_KEY else None
        g = StateGraph(State)
        g.add_node("route", self.route); g.add_node("sql", self.sql); g.add_node("python", self.python)
        g.add_node("dashboard", self.dashboard); g.add_node("synthesize", self.synthesize)
        g.set_entry_point("route")
        g.add_conditional_edges("route", lambda s:s["mode"], {"sql":"sql","python":"python","dashboard":"dashboard"})
        for n in ("sql","python","dashboard"): g.add_edge(n,"synthesize")
        g.add_edge("synthesize", END); self.graph = g.compile()

    def ask(self, prompt):
        if not self.llm: raise RuntimeError("GOOGLE_API_KEY is not configured on the backend.")
        return self.llm.invoke(prompt).content

    def route(self, st):
        q=st["question"].lower()
        if any(x in q for x in ("sql","select","join","group by")): m="sql"
        elif any(x in q for x in ("dashboard","kpi","chart","visual","trend")): m="dashboard"
        else: m="python"
        return {"mode":m}

    def sql(self, st):
        df=session(st["session_id"])["df"]
        sql=self.ask(f"Generate ONLY one read-only DuckDB SQL query using table dataset. Columns: {list(df.columns)}. Question: {st['question']}").replace("```sql","").replace("```","").strip()
        return {"sql":sql,"result":run_sql(st["session_id"],sql).head(100).to_dict("records")}

    def python(self, st):
        df=session(st["session_id"])["df"]
        code=self.ask(f"""Generate ONLY executable pandas code. Preloaded: df, pd, px. NEVER import. NEVER use files, network, OS or subprocess. Put final value/table in result and optional Plotly figure in fig. Columns: {list(df.columns)}. Question: {st['question']}""").strip()
        code=re.sub(r"^```(?:python)?","",code); code=re.sub(r"```$","",code).strip()
        o=run_python(st["session_id"],code)
        return {"code":o["code"],"result":o["result"],"chart":o["chart"]}

    def dashboard(self, st):
        df=session(st["session_id"])["df"]; nums=list(df.select_dtypes("number").columns)
        cats=list(df.select_dtypes(exclude="number").columns)
        chart=None
        if nums and cats:
            x,y=cats[0],nums[0]; z=df.groupby(x,dropna=False)[y].sum().reset_index().sort_values(y,ascending=False).head(10)
            chart={"type":"bar","x":x,"y":y,"data":z.to_dict("records")}
        return {"result":{"rows":len(df),"columns":len(df.columns),"missing":int(df.isna().sum().sum())},"chart":chart}

    def synthesize(self, st):
        if st["mode"]=="dashboard": return {"answer":"Dashboard analysis generated from the uploaded dataset."}
        if not self.llm: return {"answer":"Analysis completed. Configure GOOGLE_API_KEY for AI-generated explanations."}
        return {"answer":self.ask(f"Give a concise business explanation. Question: {st['question']} Result: {str(st.get('result'))[:10000]}. Do not invent numbers.")}

analyst=Analyst()

class Query(BaseModel):
    session_id: str
    question: str
class CodeQuery(BaseModel):
    session_id: str
    code: str
class SQLQuery(BaseModel):
    session_id: str
    sql: str

@app.get("/api/profile/{sid}")
def get_profile(sid): 
    try: return profile(sid)
    except Exception as e: raise HTTPException(404,str(e))

@app.post("/api/analyze")
def analyze(q: Query):
    if session(q.session_id)["df"] is None: raise HTTPException(400,"Upload a dataset first.")
    try:
        out=analyst.graph.invoke({"session_id":q.session_id,"question":q.question})
        return {k:out.get(k) for k in ("mode","answer","result","chart","code","sql")}
    except Exception as e: raise HTTPException(400,str(e))

@app.post("/api/python")
def python_query(q: CodeQuery):
    try: return run_python(q.session_id,q.code)
    except Exception as e: raise HTTPException(400,str(e))

@app.post("/api/sql")
def sql_query(q: SQLQuery):
    try: return {"sql":q.sql,"result":run_sql(q.session_id,q.sql).head(100).to_dict("records")}
    except Exception as e: raise HTTPException(400,str(e))
