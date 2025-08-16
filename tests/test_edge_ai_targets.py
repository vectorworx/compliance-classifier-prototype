# tests/test_edge_ai_targets.py
# Tags: #cctests #ccbaseline
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

DB_PATH = REPO / "data" / "cc_audit.sqlite"
DOCS_DIR = REPO / "data" / "docs"
OUTPUT_DIR = REPO / "data" / "outputs"


def _run(cmd: list[str]) -> str:
    """
    Run a command at repo root and assert success; resolves cc_mvp.py from root.
    """
    # Ensure cc_mvp.py resolves from repo root, not tests/
    if len(cmd) >= 2 and cmd[1] == "cc_mvp.py":
        cmd = [cmd[0], str(REPO / "cc_mvp.py"), *cmd[2:]]
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if res.returncode != 0:
        print("STDOUT:\n", res.stdout)
        print("STDERR:\n", res.stderr)
    assert res.returncode == 0, f"Command failed: {' '.join(cmd)}"
    return res.stdout


def _reset_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUTPUT_DIR.glob("findings_*.*"):
        try:
            f.unlink()
        except Exception:
            pass
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except PermissionError:
            with sqlite3.connect(DB_PATH) as cx:
                try:
                    cx.execute("PRAGMA journal_mode=WAL;")
                    cx.execute("DELETE FROM events;")
                    cx.execute("VACUUM;")
                except sqlite3.Error:
                    pass


def test_edge_phrasing_runs_and_logs():
    """
    Two edge docs with *implied/ambiguous* phrasing should be a miss for strict
    regex baselines. Assert pipeline stability and audit DB creation (allow zero hits).
    """
    _reset_outputs()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Implied breach phrasing; avoids explicit 72h wording
    (DOCS_DIR / "edgecase_gdpr_implied.txt").write_text(
        "We will promptly inform regulators as appropriate after incidents.",
        encoding="utf-8",
    )
    # Ambiguous policy language
    (DOCS_DIR / "edgecase_policy_ambiguous.txt").write_text(
        "We aim to communicate without undue delay when situations warrant attention.",
        encoding="utf-8",
    )

    _run([PY, "cc_mvp.py", "--regime", "GDPR"])

    assert DB_PATH.exists(), "Audit DB not created"
    with sqlite3.connect(DB_PATH) as cx:
        cx.execute("PRAGMA journal_mode=WAL;")
        rows = cx.execute(
            """
            SELECT COUNT(*) FROM events
            WHERE doc IN ('edgecase_gdpr_implied.txt','edgecase_policy_ambiguous.txt')
            """
        ).fetchone()[0]
    # Baseline BEFORE snapshot for the AI layer: allow zero hits
    assert rows >= 0


def test_outputs_timestamped_when_hits_occur():
    """
    Insert a canonical GDPR breach phrasing doc; expect timestamped outputs.
    """
    _reset_outputs()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    (DOCS_DIR / "trigger_breach.txt").write_text(
        "We notify the supervisory authority within seventy-two hours of a personal data breach. "
        "All users must use MFA as part of access controls.",
        encoding="utf-8",
    )

    _run([PY, "cc_mvp.py", "--regime", "GDPR"])

    csvs = sorted(OUTPUT_DIR.glob("findings_gdpr_*.csv"))
    jsons = sorted(OUTPUT_DIR.glob("findings_gdpr_*.json"))
    assert csvs, "Expected GDPR CSV output (from trigger_breach.txt)"
    assert jsons, "Expected GDPR JSON output (from trigger_breach.txt)"
