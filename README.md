# Compliance Classifier Prototype

[![CI](https://github.com/vectorworx/compliance-classifier-prototype/actions/workflows/ci.yml/badge.svg)](https://github.com/vectorworx/compliance-classifier-prototype/actions)
[![codecov - main](https://codecov.io/gh/vectorworx/compliance-classifier-prototype/branch/main/graph/badge.svg?token=27d63549-37a0-4838-9a5c-c7d6da051535&t=1)](https://app.codecov.io/gh/vectorworx/compliance-classifier-prototype/tree/main)

[![codecov - codecov-action-debug](https://codecov.io/gh/vectorworx/compliance-classifier-prototype/branch/codecov-action-debug/graph/badge.svg?token=27d63549-37a0-4838-9a5c-c7d6da051535&t=2)](https://app.codecov.io/gh/vectorworx/compliance-classifier-prototype/tree/codecov-action-debug)

> ⚠️ **Prototype Status:** Active development. Expect changes in structure and outputs.
> ✅ CI + Coverage reporting are live and stable.
> 📦 Demo outputs available via **Actions → latest run → Artifacts** (`findings-<run_id>`, `audit-db-<run_id>`).

---

## 📌 Compliance-First Document Classifier

AI-ready pipeline to scan contracts, policies, and compliance docs against GDPR, SOC 2, and related regimes. Produces an **append-only audit log** plus structured CSV/JSON findings.

---

## ✈️ Proof Block

- 📊 **Accuracy Goal:** 95% on standard clauses, 100% recall on critical
- ⏱️ **Processing Goal:** 2 hrs → <10 min per batch
- 🛡️ **Compliance Goal:** Zero violations in 1,000-doc test

---

## 🛫 Runway Check (Why Now?)

- Manual compliance review is **slow and error-prone**.
- GDPR/SOC 2 penalties make omissions costly.
- This prototype shows how **deterministic rules + AI augmentation** can shrink review time while strengthening audit readiness.

---

## 🗺️ Flight Plan

- **THEN:** Manual review, regex scripts, keyword search
- **NOW:** Deterministic rules + LLM-assisted extraction with audit trail

---

## 🛩️ Cockpit View (Architecture)

_(System diagram coming soon)_

- **Inputs:** PDFs, DOCX, TXT (sample docs included)
- **Engine:** Rule-based baseline, LLM layer planned
- **Outputs:** Timestamped CSV/JSON + append-only SQLite log
- **Dashboard:** Streamlit app (read-only, local demo)

---

## ✅ Pre-Flight Checklist

- [x] CI & coverage reporting wired up
- [x] Baseline GDPR/SOC2 rules implemented
- [ ] Expand test corpus
- [ ] Add AI-assisted mode
- [ ] Publish performance benchmarks

---

## 📄 Findings Format — Vectorworx OneBlock

Every run produces a `findings_<regime>_<timestamp>.csv` file.

**Example row:**

```csv
rule_id,label,severity,start,end,snippet,doc
GDPR-BREACH-72H,Breach Notification (72h),critical,3,60,"We notify the authority within seventy-two hours of a breach.",sample.txt
```

**Columns:**

- `rule_id` → unique compliance rule
- `label` → human-readable name
- `severity` → critical/high/medium/low
- `start` / `end` → character offsets
- `snippet` → triggering text
- `doc` → source filename

💡 **Pro tip (VS Code):** Install Rainbow CSV for instant column highlighting. Use CSV: Run SQL Query to slice findings interactively.

---

## 📊 Audit Dashboard (Local Demo)

Run a Streamlit dashboard over the audit log:

```sh
pip install streamlit
streamlit run streamlit_app.py
```

The dashboard shows KPIs, per-rule counts, per-doc counts, and exportable CSVs.

---

## 🚀 Quickstart

### Local Setup

```sh
# 1) Create venv
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # macOS/Linux

# 2) Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt \
  || pip install pdfplumber python-docx PyYAML pandas pytest streamlit

# 3) Run baseline scan
python cc_mvp.py --regime GDPR
# or
python cc_mvp.py --regime SOC2
```

**Outputs:**

- CSV/JSON findings → `data/outputs/`
- Audit log → `data/cc_audit.sqlite`

### Codespaces (One-Click)

```sh
python demo.py
streamlit run dashboard.py   # Open forwarded Port 8501
```

---

## 📈 Current Baseline Results (Sample)

- 📄 Docs scanned: 3
- 🔎 Findings: 2 (1 critical GDPR breach clause detected)
- ⬇ Outputs: CSV + JSON in `/data/outputs/`
- 🧾 Audit trail: SQLite log with run_id + timestamp

---

## 🛬 Roadmap

- Broaden rule set (HIPAA, ISO 27001)
- Integrate LLM explanation layer
- Add production connectors (S3, GDrive)
- Deployable dashboard (Streamlit/Gradio)

---

## 📝 Post-Flight Debrief

This repo is a prototype — proving deterministic compliance scanning works at speed, and laying the runway for AI-assisted classification with explainability and audit-grade outputs.
