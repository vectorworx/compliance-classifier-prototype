# Tags: #cctests #ccbaseline #ccgdpr
import subprocess, sys, sqlite3, re
from pathlib import Path
from .util_docs import temp_docs, REPO

PY = sys.executable


def _run(args: list[str]) -> str:
    res = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    if res.returncode != 0:
        # Bubble up stdout/stderr to help debug in CI if it fails
        print("STDOUT:\n", res.stdout)
        print("STDERR:\n", res.stderr)
    assert res.returncode == 0, f"Command failed: {' '.join(args)}"
    return res.stdout


def test_gdpr_breach_rule_hits_canonical_phrase():
    # Canonical “notify supervisory authority within seventy-two hours”
    content = (
        "In the event of a personal data breach, we notify the supervisory authority "
        "within seventy-two hours. Multi-factor authentication is required."
    )
    with temp_docs({"canonical_gdpr.txt": content}):
        _run([PY, "cc_mvp.py", "--regime", "GDPR"])
        # Assert the audit DB exists and contains an event for the doc under GDPR-BREACH-72H
        db = REPO / "data" / "cc_audit.sqlite"
        assert db.exists()
        with sqlite3.connect(db) as cx:
            n = cx.execute(
                "SELECT COUNT(*) FROM events WHERE doc=? AND rule_id=?",
                ("canonical_gdpr.txt", "GDPR-BREACH-72H"),
            ).fetchone()[0]
        assert n >= 1, "Expected GDPR-BREACH-72H to fire on canonical phrasing"


def test_gdpr_edge_phrase_is_baseline_miss_until_ai():
    # Edge phrasing—intentionally avoids the “72 hours / supervisory authority” regex
    content = (
        "If there is an impact, we will promptly inform relevant regulators without undue delay."
    )
    with temp_docs({"edge_gdpr.txt": content}):
        _run([PY, "cc_mvp.py", "--regime", "GDPR"])
        db = REPO / "data" / "cc_audit.sqlite"
        assert db.exists()
        with sqlite3.connect(db) as cx:
            n = cx.execute(
                "SELECT COUNT(*) FROM events WHERE doc=? AND rule_id=?",
                ("edge_gdpr.txt", "GDPR-BREACH-72H"),
            ).fetchone()[0]
        # Baseline expectation: 0 hits now; becomes >0 after --ai lands
        assert n == 0, "Edge phrasing should be a miss in rules-only baseline"
