# AI Data Analyst — LangChain + LangGraph + Langbase

A chat-based data analyst: upload a CSV, ask questions in plain English, get
answers grounded in real pandas computation (not hallucinated numbers).

## Architecture

```
User question
     │
     ▼
┌─────────────────┐
│ classify_intent  │  ← Gemini call (fast, local — no need to spend a Langbase call here)
└────────┬─────────┘
         │
   ┌─────┴──────┐
   │            │
data_question   greeting / unsupported
   │            │
   ▼            ▼
┌───────────┐ ┌──────────────┐
│plan_query │ │direct_response│
│(LangChain │ └──────────────┘
│tool-calling│
│  agent)   │
└─────┬─────┘
      ▼
┌────────────────────┐
│ synthesize_insight  │  ← routed through your datamind-ai-analyst Langbase pipe
└──────────┬──────────┘     (local fallback if LANGBASE_API_KEY is unset)
           ▼
          END
```

- **LangGraph** owns the control flow — a small state machine (`agent/graph.py`)
  that decides whether a message needs the data tools at all before spending a
  tool-calling round trip on it.
- **LangChain** provides the tool-calling agent and the four pandas tools
  (`agent/tools.py`): `get_data_summary`, `get_column_values`,
  `calculate_aggregate`, `run_pandas_query`. The last one is a constrained,
  read-only expression evaluator — no imports, file I/O, or mutation — so the
  LLM can query flexibly without arbitrary code execution risk.
- **Langbase** hosts the final answer-writing step as a versioned pipe:
  [`nitin28061999/datamind-ai-analyst`](https://langbase.com/nitin28061999/datamind-ai-analyst).
  Once the tool-calling agent produces a raw numeric result, it's handed to
  that pipe along with the original question — the pipe's system prompt (data
  analysis, KPI recommendations, SQL/Python where useful) turns the raw number
  into an analyst-style answer, and can be tuned in the Langbase UI with no
  code deploy. If `LANGBASE_API_KEY` isn't set, the app transparently falls
  back to an equivalent local Gemini prompt — **the demo works without the key
  filled in**, and switching over later is a config change, not a code change.
- **Gemini** (via `langchain-google-genai`) is the underlying LLM. Swap the
  model name in `.env` if you'd rather point this at a different provider
  later.
- **Streamlit** is the demo front end (`app.py`) — file upload, chat window,
  and an expandable "behind the scenes" panel showing exactly which tool ran
  and with what arguments, which is useful for the initial internal review
  since it makes the agent's reasoning inspectable rather than a black box.

## Project layout

```
ai-data-analyst/
├── app.py                   # Streamlit UI
├── agent/
│   ├── state.py             # LangGraph state schema
│   ├── tools.py             # pandas tools + in-memory DataStore
│   ├── langbase_client.py   # Langbase pipe wrapper + local fallback
│   └── graph.py             # the LangGraph workflow itself
├── data/sample_sales.csv    # demo dataset
├── requirements.txt
└── .env.example
```

## Setup

```bash
cd ai-data-analyst
python3 -m venv venv && source venv/bin/activate      # optional but recommended
pip install -r requirements.txt

cp .env.example .env
# edit .env and paste in a Gemini API key from https://aistudio.google.com/apikey
```

Run it:

```bash
streamlit run app.py
```

It opens at `http://localhost:8501`. Click **"Use sample dataset"** in the
sidebar, or upload your own CSV.

## Wiring up your Langbase pipe

Your pipe already exists: https://langbase.com/nitin28061999/datamind-ai-analyst

1. Open the pipe page, go to its **Settings → API keys** tab, and generate a
   **pipe** API key (this is different from your general Langbase account
   key — it's scoped to this one pipe).
2. Paste it into `.env` as `LANGBASE_API_KEY`. `LANGBASE_PIPE_URL` is already
   set to the correct endpoint (`https://api.langbase.com/v1/pipes/run`) in
   `.env.example`.
3. Restart the app. `synthesize_insight_node` in `agent/graph.py` will now
   route the final answer through your pipe and only fall back to the local
   Gemini prompt if that call errors out.

Leave `LANGBASE_API_KEY` blank for the initial demo if the key isn't ready
yet — everything still works end-to-end on the local fallback.

## Demo script for the internal walkthrough

A suggested 5-minute flow that shows off each layer without getting into the
weeds:

1. **Load data** — click "Use sample dataset" (or upload a real team CSV if
   you have one cleared to use).
2. **Simple aggregate** — ask *"What's the total revenue by region?"* — shows
   `calculate_aggregate` being called correctly.
3. **Filtered question** — ask *"How much revenue came from the North region
   from Electronics?"* — shows `run_pandas_query` composing a filter the
   simpler tool can't express, and open the "Behind the scenes" expander to
   show the exact pandas expression the model generated.
4. **Off-topic message** — type *"hi"* — shows the LangGraph intent-routing
   short-circuiting the tool-calling agent entirely, which is the efficiency
   argument for using a graph instead of always invoking the full agent.
5. **Talk architecture for 60 seconds** — point at the diagram above: LangGraph
   for control flow, LangChain for tool execution, Langbase for prompt
   management the team can edit without you. This is the pitch for why it's
   built this way rather than as one big prompt.

## Known limitations to mention proactively in the review

- `run_pandas_query` blocks a keyword list rather than running in a true
  sandbox — fine for an internal pilot with trusted users and non-sensitive
  data, but should move to a sandboxed executor (or a fixed query DSL) before
  handling untrusted input or sensitive datasets.
- No persistent chat memory across sessions yet — each Streamlit session
  starts fresh. LangGraph's checkpointing (`MemorySaver` / a Postgres/Redis
  checkpointer) is the natural next step if the team wants multi-turn
  follow-ups to reference earlier answers.
- Single-file CSVs only for now; multi-table joins would need a small
  extension to `DataStore` and a `list_loaded_tables` tool.

## Suggested next steps after the pilot

1. Add LangSmith tracing (you already have this partly scoped from the
   earlier `DataMind-AI` work) so every tool call and LLM turn is logged for
   debugging and cost tracking.
2. Add a `MemorySaver` checkpointer to LangGraph for multi-turn memory.
3. Wrap `build_graph()` in a small FastAPI endpoint so it can be called from
   Slack or an internal tool instead of only the Streamlit UI.
4. Move `run_pandas_query` to a sandboxed execution environment before
   pointing it at real production data.
