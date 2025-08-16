# Compliance Classifier Prototype

[![CI](https://github.com/vectorworx/compliance-classifier-prototype/actions/workflows/ci.yml/badge.svg)](https://github.com/vectorworx/compliance-classifier-prototype/actions)
[![codecov](https://codecov.io/gh/vectorworx/compliance-classifier-prototype/branch/main/graph/badge.svg)](https://codecov.io/gh/vectorworx/compliance-classifier-prototype)

> CI runs a demo on each push and uploads outputs as artifacts:
> **Actions → latest run → Artifacts** → `findings-<run_id>` and `audit-db-<run_id>`.

# Compliance-First Document Classifier (GDPR + SOC 2)

## Proof Block

📊 **Target Accuracy:** 95% on standard terms, 100% recall on critical
⏱️ **Target Processing Time:** 2 hrs → <10 min per batch
🛡️ **Target Compliance:** Zero violations in 1,000-doc test

---

## Runway Check (Why Now?)

Legal and compliance teams waste hours manually scanning contracts, policies, and agreements for key clauses.
Regulations like GDPR and SOC 2 make omissions costly — in fines and reputation.
This prototype shows how AI can reduce review time while improving accuracy and audit readiness.

## Flight Plan

**THEN:** Manual review, regex scripts, basic keyword search
**NOW:** LLM-powered extraction with explainability + audit trail

## Cockpit View (Architecture)

_(Diagram to be added in later commit)_

## Pre-Flight Checklist

- [ ] Dependencies list
- [ ] API keys required
- [ ] Example documents included
- [ ] Performance baseline metrics

## Implementation

_(Coming in later commits)_

## Flight Data (Results)

_(Coming in later commits)_

## Black Box Recovery

_(Coming in later commits)_

## Scale Path

_(Coming in later commits)_

## Post-Flight Debrief

_(Coming in later commits)_

## 📄 How to Read the Findings CSV — Vectorworx OneBlock

Every run of the Compliance Classifier produces a `findings_<regime>_<timestamp>.csv` file in the project root.

Example row:
`rule_id,label,severity,start,end,snippet,doc`
`GDPR-BREACH-72H,Breach Notification (72h),critical,3,60,"We notify the supervisory authority within seventy-two hours of a personal data breach. All users must use MFA as part of access controls.",sample.txt`

**Column meanings:**

- `rule_id` → Unique ID for the compliance rule triggered.
- `label` → Human-readable name of the rule.
- `severity` → Risk level (`critical`, `high`, `medium`, `low`).
- `start` / `end` → Character offsets in the source document for the match.
- `snippet` → Exact text fragment that triggered the match.
- `doc` → File name of the source document.

**Pro tips (VS Code):** Install **Rainbow CSV**, open the file, and you’ll see columns colorized for quick scanning. Use `CTRL+SHIFT+P → CSV: Run SQL Query` to filter findings interactively.

**Why this matters in production:**

- CSVs are lightweight, portable, and quick to review.
- They serve as **ground truth baseline** before adding AI classification.
- They’re easy to feed into dashboards, BI tools, or downstream analytics.

### 📊 Audit Dashboard (Read‑Only)

Run a local Streamlit dashboard over the append‑only SQLite audit log:

```bash
pip install streamlit
streamlit run streamlit_app.py
```

## ✅ Results (Baseline Before AI)

This section shows the first end‑to‑end run of the Compliance Classifier on a small, controlled document set. It’s our **baseline** (rules‑only) before layering in AI.

---

### Mini Proof Block (Sample Output)

PROOF BLOCK — GDPR

📄 Docs scanned: 3
🔎 Findings: 2 | 🔥 Critical: 1 | ⬆ High: 0
🏷️ Top rule hit: GDPR-BREACH-72H ×1
⬇ Output: data/outputs/findings_gdpr_20250815-153200.csv
⬇ Output: data/outputs/findings_gdpr_20250815-153200.json
🧾 Audit run_id: 3a3f7b1c-2d9b-4b33-b6e8-0a1b0e34d2f1

**What this means:**

- The engine detected the **72‑hour breach notification clause** in `breach_gdpr.pdf` (critical).
- `clean_soc2.txt` produced **no GDPR findings** (as expected).
- `edgecase_gdpr.txt` avoided the exact pattern (by design) — this becomes a great **test case for the AI layer**.

---

### Dashboard Snapshot

> _Read‑only Streamlit dashboard over the append‑only SQLite audit log._

- **Filters:** regime, rule_id, document, date range
- **KPIs:** total findings, unique docs, unique rules hit
- **Tables:** recent findings, per‑rule counts, per‑doc counts
- **Export:** download filtered CSV

**Run locally:**

```bash
streamlit run dashboard.py

Files Produced

CSV/JSON findings (timestamped): data/outputs/findings_<regime>_<timestamp>.csv|.json

Append‑only audit log: data/cc_audit.sqlite (queried by the dashboard)

Why This Matters

Deterministic baseline: Rules give us a fast, auditable ground truth with zero token cost.

Paper trail: Every run is logged with run_id, version, and timestamp in SQLite — easy to prove and replay.

Ready for AI: Ambiguous/edge cases (like the “promptly inform regulators” phrasing) become targets for the upcoming LLM pass with confidence + rationale.
```

## Build • Test • Demo

[![CI](https://github.com/vectorworx/compliance-classifier-prototype/actions/workflows/ci.yml/badge.svg)](../../actions)

### 1) Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
python -m pip install --upgrade pip
pip install -r requirements.txt || pip install pdfplumber python-docx PyYAML pandas pytest streamlit
```

## 🚀 Quickstart — Local & Codespaces (Vectorworx One‑Block)

Production‑first setup that runs in minutes. This section is self‑contained and ready to paste into your README.

---

### Local Setup

```bash
# 1) Create & activate virtual environment
python -m venv .venv
# Windows (Git Bash/PowerShell):
source .venv/Scripts/activate
# macOS/Linux:
# source .venv/bin/activate

# 2) Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt \
  || pip install pdfplumber python-docx PyYAML pandas pytest streamlit

# 3) (Optional) Enable AI-assisted mode for later
cp .env.example .env
# Fill in OPENAI_API_KEY / ANTHROPIC_API_KEY (keep .env local; never commit)

# 4) Run the compliance classifier (rules-only baseline)
python cc_mvp.py --regime GDPR
# or
python cc_mvp.py --regime SOC2

## What you’ll see (baseline):

Timestamped CSV/JSON in data/outputs/

Append‑only audit log in data/cc_audit.sqlite

Console summary with top rules and preview snippets

☁️ ## One‑Click Codespaces (Zero‑install)

Inside the Codespace terminal:

# Demo run: scans sample docs and writes outputs + audit log
python demo.py

# Read‑only dashboard over the SQLite audit log
streamlit run dashboard.py   # Open forwarded Port 8501 in the "Ports" panel
```

# Trigger CI
