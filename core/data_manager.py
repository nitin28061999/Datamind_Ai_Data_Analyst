import io
import os
import pandas as pd
import duckdb

class DataManager:
    def __init__(self):
        self.df = None
        self.name = None

    @property
    def rows(self): return 0 if self.df is None else len(self.df)
    @property
    def cols(self): return 0 if self.df is None else len(self.df.columns)

    def _normalize(self, df):
        df = df.copy()
        for c in df.columns:
            if "date" in c.lower() or "time" in c.lower():
                converted = pd.to_datetime(df[c], errors="coerce")
                if converted.notna().mean() >= 0.7:
                    df[c] = converted
        return df

    def load_path(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            raise ValueError("Only CSV and Excel files are supported.")
        self.df = self._normalize(df)
        self.name = os.path.basename(path)
        return self.df

    def load_uploaded(self, uploaded):
        raw = uploaded.getvalue()
        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(raw))
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            raise ValueError("Only CSV and Excel files are supported.")
        self.df = self._normalize(df)
        self.name = uploaded.name
        return self.df

    def profile(self):
        df = self.df
        info = []
        for c in df.columns:
            info.append({
                "column": c,
                "dtype": str(df[c].dtype),
                "missing": int(df[c].isna().sum()),
                "unique": int(df[c].nunique(dropna=True)),
            })
        return {
            "rows": len(df),
            "columns": len(df.columns),
            "missing_cells": int(df.isna().sum().sum()),
            "duplicate_rows": int(df.duplicated().sum()),
            "columns_info": info,
        }

    def query_sql(self, sql):
        con = duckdb.connect()
        try:
            con.register("dataset", self.df)
            return con.execute(sql).df()
        finally:
            con.close()
