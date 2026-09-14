# DataMind AI — Vercel Frontend + Render Backend

This is the production-style restructuring of the original DataMind AI Streamlit project.

## Architecture

Next.js frontend → Vercel → FastAPI backend → Render → LangGraph → Python / SQL / Dashboard agents → Gemini + DuckDB + Pandas.

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --port 8000
```

Render:
- Root Directory: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Add `GOOGLE_API_KEY`
- Add `FRONTEND_URL` after Vercel deployment

Test `/health`.

## Frontend

```powershell
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Vercel:
- Root Directory: `frontend`
- Framework: Next.js
- Environment: `NEXT_PUBLIC_API_URL=https://YOUR-RENDER-URL.onrender.com`

## Features

- Executive dashboard
- AI Analyst
- Natural-language Python/Pandas
- SQL/DuckDB
- Data Explorer
- CSV/XLSX upload
- LangGraph routing
- Gemini synthesis
- REST API

## Security

The Python endpoint uses AST validation and restricted builtins for a portfolio/demo environment. It is **not a true sandbox**. Before exposing arbitrary code execution to untrusted public users, move execution into an isolated container/worker with CPU, memory, timeout, filesystem and network restrictions.

Never expose `GOOGLE_API_KEY` in `NEXT_PUBLIC_*` variables.
