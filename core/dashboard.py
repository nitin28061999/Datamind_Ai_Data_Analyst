import pandas as pd
import plotly.express as px

def _find(df, names):
    for n in names:
        for c in df.columns:
            if n in c.lower():
                return c
    return None

def build_dashboard(df):
    revenue = _find(df, ["revenue", "sales", "amount"])
    profit = _find(df, ["margin", "profit"])
    units = _find(df, ["units", "quantity"])
    date = _find(df, ["invoice_date", "date", "datetime"])
    category = _find(df, ["category", "product", "brand"])
    city = _find(df, ["city", "region", "state"])
    kpis = []
    if revenue: kpis.append(("Revenue", f"{df[revenue].sum():,.2f}"))
    if profit: kpis.append(("Profit/Margin", f"{df[profit].sum():,.2f}"))
    if units: kpis.append(("Units", f"{df[units].sum():,.0f}"))
    kpis.append(("Rows", f"{len(df):,}"))
    while len(kpis) < 4: kpis.append(("KPI", "—"))

    charts = []
    if date and revenue:
        temp = df[[date, revenue]].dropna().copy()
        temp[date] = pd.to_datetime(temp[date], errors="coerce")
        temp = temp.dropna().groupby(pd.Grouper(key=date, freq="ME"))[revenue].sum().reset_index()
        if not temp.empty:
            charts.append(px.line(temp, x=date, y=revenue, title="Revenue Trend"))
    if category and revenue:
        temp = df.groupby(category, as_index=False)[revenue].sum().nlargest(10, revenue)
        charts.append(px.bar(temp, x=category, y=revenue, title=f"Top {category} by Revenue"))
    if city and revenue:
        temp = df.groupby(city, as_index=False)[revenue].sum().nlargest(10, revenue)
        charts.append(px.bar(temp, x=city, y=revenue, title=f"Revenue by {city}"))
    return {"kpis": kpis, "charts": charts}
