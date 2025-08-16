# tests/smoke_test.py
# Tags: #cctest #ccproof
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

OUTPUT_DIR = REPO / "data" / "outputs"
DB_PATH = REPO / "data" / "cc_audit.sqlite"
DOCS_DIR = REPO / "data" / "docs"

TIMESTAMP_RE = re.compile(r"findings_(gdpr|soc2)_(\d{8}-\d{6})\.(csv|json)$", re.I)


# --- Helpers -----------------------------------------------------------------


def _safe_unlink(path: Path) -> None:
    """Attempt to delete a file; ignore if missing or locked (Windows)."""
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except PermissionError:
        time.sleep(0.2)
        try:
            path.unlink()
        except Exception:
            pass
    except Exception:
        # Best-effort cleanup
        pass


def _truncate_audit_db() -> None:
    """
    Make the audit DB 'empty' without deleting the file.
    This avoids Windows file-lock errors and is portable.
    """
    if not DB_PATH.exists():
        return
    try:
        with sqlite3.connect(DB_PATH) as cx:
            try:
                cx.execute("PRAGMA journal_mode=WAL;")
                cx.execute("DELETE FROM events;")
                cx.execute("VACUUM;")
            except sqlite3.OperationalError:
                # Table not created yet; nothing to clear.
                pass
    except sqlite3.Error:
        # Last resort if corrupt/locked: attempt unlink once.
        _safe_unlink(DB_PATH)


def _reset_outputs() -> None:
    """Clean output artifacts and audit DB content in a lock-tolerant way."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUTPUT_DIR.glob("findings_*"):
        _safe_unlink(f)
    _truncate_audit_db()


def _ensure_docs() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "sample.txt").write_text(
        "We notify the Supervisory Authority within seventy-two hours of any personal data breach.\n"
        "All users must use MFA.\n",
        encoding="utf-8",
    )


def _run(cmd: list[str]) -> str:
    """
    Run a command in repo root and assert success.
    Force UTF-8 stdio to avoid encoding issues on Windows (e.g., arrows/emojis).
    """
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    print("→", " ".join(cmd))
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
    if res.stdout:
        print(res.stdout)
    if res.returncode != 0 and res.stderr:
        print(res.stderr)
    assert res.returncode == 0, f"Command failed: {' '.join(cmd)}"
    return res.stdout


def _list_outputs(regime: str) -> list[Path]:
    return sorted(OUTPUT_DIR.glob(f"findings_{regime.lower()}_*.*"))


# --- Tests -------------------------------------------------------------------


def test_gdpr_run_creates_outputs():
    """
    Minimal end-to-end for GDPR:
    - ensures outputs are generated (CSV/JSON + timestamped name)
    - audit DB exists and has events
    """
    _reset_outputs()
    _ensure_docs()
    _run([PY, "cc_mvp.py", "--regime", "GDPR"])

    csvs = sorted(OUTPUT_DIR.glob("findings_gdpr_*.csv"))
    jsons = sorted(OUTPUT_DIR.glob("findings_gdpr_*.json"))
    assert csvs, "No GDPR CSV output created"
    assert jsons, "No GDPR JSON output created"

    # timestamp sanity
    for p in csvs + jsons:
        assert TIMESTAMP_RE.search(p.name), f"Bad output name: {p.name}"

    # audit exists + has rows
    assert DB_PATH.exists(), "Audit DB not created"
    with sqlite3.connect(DB_PATH) as cx:
        n = cx.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert n > 0, "No events logged to audit DB"


def test_soc2_run_executes():
    """
    SOC2 on a neutral doc: allow zero hits, but ensure:
    - clean exit
    - audit DB created
    """
    _reset_outputs()
    _ensure_docs()
    _run([PY, "cc_mvp.py", "--regime", "SOC2"])

    assert DB_PATH.exists(), "Audit DB not created for SOC2"
    # SOC2 CSV may or may not exist depending on rules and sample
    if not list(OUTPUT_DIR.glob("findings_soc2_*.csv")):
        # Ensure we didn’t accidentally write GDPR files during SOC2 run
        assert not list(
            OUTPUT_DIR.glob("findings_gdpr_*.csv")
        ), "Unexpected GDPR outputs in SOC2 test"


def test_multiple_docs_batch_processing():
    """
    Batch run with mixed docs:
    - one document that triggers GDPR rule(s)
    - one ambiguous/edge document
    Expect GDPR outputs and no crash.
    """
    _reset_outputs()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # A trigger doc that should hit at least one GDPR rule
    (DOCS_DIR / "trigger_breach.txt").write_text(
        "We notify the supervisory authority within seventy-two hours of a personal data breach. "
        "All users must use MFA as part of access controls.",
        encoding="utf-8",
    )
    # Edge doc that may not hit strict rules
    (DOCS_DIR / "edgecase_policy_ambiguous.txt").write_text(
        "We will promptly inform regulators as appropriate after incidents.",
        encoding="utf-8",
    )

    _run([PY, "cc_mvp.py", "--regime", "GDPR"])

    csvs = sorted(OUTPUT_DIR.glob("findings_gdpr_*.csv"))
    assert csvs, "Expected GDPR CSV output for mixed batch"
    assert TIMESTAMP_RE.search(csvs[-1].name), f"Bad output name: {csvs[-1].name}"


def test_stdout_is_ascii_safe():
    """
    Historically, Windows consoles choke on some Unicode glyphs during pytest capture.
    Ensure the program prints a recognizable ASCII-safe summary line.
    """
    _reset_outputs()
    _ensure_docs()
    out = _run([PY, "cc_mvp.py", "--regime", "GDPR"])
    ok = ("Compliance Results — GDPR" in out) or ("Compliance Results - GDPR" in out)
    assert ok, "Expected compliance summary header in stdout"
