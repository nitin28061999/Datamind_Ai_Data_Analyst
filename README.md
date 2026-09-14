# DataMind AI — Advanced Multimode Data Analyst

An AI-powered analytics workspace built with Streamlit, Gemini, Pandas, DuckDB and Plotly.

## Modes

- **Dashboard** — automatic executive KPIs and charts
- **AI Analyst** — natural-language routing
- **Python** — LLM-generated read-only Pandas analysis
- **SQL** — LLM-generated read-only DuckDB SQL
- **Data Explorer** — inspect the loaded dataset
- **Profile** — schema, missing values and duplicates

## Architecture

User → Intent Router → Python Agent / SQL Agent / Dashboard → Validator → Execution → Result → Business Insight

## Run on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Put your Gemini API key in .env
python -m streamlit run app.py
```

## Important

Never commit `.env`. Generated Python is validated and executed with restricted builtins, but this is still a local analytical application, not a production sandbox. For untrusted users, move code execution into a real isolated container or replace code execution with a fixed analysis DSL.

## Suggested demo questions

Python:
- What are the top 5 brands by revenue?
- Calculate average margin by category.
- Find products below reorder level.
- Show the relationship between units and revenue.

SQL:
- Show monthly revenue.
- Give the top 10 cities by revenue.
- Calculate revenue and margin by category.

Dashboard:
- Load the sample dataset and open the Dashboard tab.
