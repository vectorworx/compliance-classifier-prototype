# streamlit_app.py
# Tags: #ccdash #ccaudit #ccproof
#
# Read-only dashboard for cc_audit.sqlite
# - Filters: regime, rule_id, doc, date range
# - KPIs: total findings, docs scanned, unique rules hit
# - Tables: recent findings, per-rule counts, per-doc counts

from pathlib import Path
import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

DB_PATH = Path("data/cc_audit.sqlite")

st.set_page_config(
    page_title="Compliance Classifier — Audit Dashboard", page_icon="✅", layout="wide"
)

st.title("Compliance Classifier — Audit Dashboard")
st.caption("Append‑only audit log viewer • local & read‑only • built for fast demos")

# ---------- Safety checks ----------
if not DB_PATH.exists():
    st.warning(
        f"Database not found at `{DB_PATH}`. Run the scanner first (e.g., `python cc_mvp.py --regime GDPR`)."
    )
    st.stop()


# ---------- Load data ----------
@st.cache_data(ttl=30)
def load_events():
    with sqlite3.connect(DB_PATH) as cx:
        df = pd.read_sql_query(
            """
            SELECT
              id, ts, run_id, version, regime, doc, rule_id, label, severity, snippet
            FROM events
            ORDER BY id DESC
            """,
            cx,
        )
    # parse ts to datetime
    df["ts_dt"] = pd.to_datetime(df["ts"], errors="coerce")
    return df


df = load_events()
if df.empty:
    st.info("No events yet. Run a scan to populate the audit log.")
    st.stop()

# ---------- Sidebar filters ----------
st.sidebar.header("Filters")
regimes = sorted(df["regime"].dropna().unique().tolist())
rule_ids = sorted(df["rule_id"].dropna().unique().tolist())
docs = sorted(df["doc"].dropna().unique().tolist())

regime_sel = st.sidebar.multiselect("Regime", options=regimes, default=regimes)
rule_sel = st.sidebar.multiselect("Rule ID", options=rule_ids, default=rule_ids)
doc_sel = st.sidebar.multiselect("Document", options=docs, default=docs)

# Date range defaults to last 7 days
max_ts = df["ts_dt"].max()
min_ts = df["ts_dt"].min()
default_start = (max_ts - timedelta(days=7)) if pd.notnull(max_ts) else min_ts
start_dt, end_dt = st.sidebar.date_input(
    "Date range",
    value=(
        default_start.date() if pd.notnull(default_start) else datetime.utcnow().date(),
        max_ts.date() if pd.notnull(max_ts) else datetime.utcnow().date(),
    ),
)

# ---------- Apply filters ----------
mask = (
    df["regime"].isin(regime_sel)
    & df["rule_id"].isin(rule_sel)
    & df["doc"].isin(doc_sel)
    & (df["ts_dt"].dt.date >= start_dt)
    & (df["ts_dt"].dt.date <= end_dt)
)
view = df.loc[mask].copy()

# ---------- KPIs ----------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Findings", f"{len(view):,}")
col2.metric("Unique Docs", f"{view['doc'].nunique():,}")
col3.metric("Unique Rules Hit", f"{view['rule_id'].nunique():,}")
# latest run id in filtered set
latest_run = (
    view.sort_values("id", ascending=False)["run_id"].head(1).item() if not view.empty else "—"
)
col4.metric("Latest Run ID", latest_run)

st.divider()

# ---------- Tables ----------
left, right = st.columns([2, 1])

with left:
    st.subheader("Recent Findings")
    show_cols = ["ts", "regime", "doc", "severity", "rule_id", "label", "snippet"]
    st.dataframe(view[show_cols].head(300), use_container_width=True)

with right:
    st.subheader("Findings by Rule")
    by_rule = (
        view.groupby(["rule_id", "label"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    st.dataframe(by_rule, use_container_width=True, height=320)

    st.subheader("Findings by Document")
    by_doc = (
        view.groupby("doc", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    st.dataframe(by_doc, use_container_width=True, height=240)

# ---------- Download area ----------
st.divider()
st.subheader("Export Filtered Results")
csv_bytes = view.drop(columns=["ts_dt"]).to_csv(index=False).encode("utf-8")
st.download_button(
    "Download CSV",
    data=csv_bytes,
    file_name=f"cc_findings_filtered_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv",
    mime="text/csv",
)

st.caption(
    "Tip: keep this read‑only. Writes happen in the scanner; this app is for review and demos."
)
