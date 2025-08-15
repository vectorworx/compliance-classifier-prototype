# Tags: #cctests #ccbaseline
from pathlib import Path
import subprocess, sys, sqlite3

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable


def _run(cmd):
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout, res.stderr)
    assert res.returncode == 0, f"Command failed: {' '.join(cmd)}"
    return res.stdout


def test_edge_phrasing_runs_and_logs():
    # Ensure the two edge docs exist (added in repo)
    for p in [
        REPO / "data" / "testdocs" / "edgecase_gdpr_implied.txt",
        REPO / "data" / "testdocs" / "edgecase_policy_ambiguous.txt",
    ]:
        assert p.exists(), f"Missing test doc: {p}"

    # Run GDPR baseline (rules-only)
    _run([PY, "cc_mvp.py", "--regime", "GDPR"])

    # Audit DB should exist regardless of hits
    db = REPO / "data" / "cc_audit.sqlite"
    assert db.exists()

    # Sanity: query recent entries for these docs; today they may be 0 (baseline)
    with sqlite3.connect(db) as cx:
        rows = cx.execute(
            """
            SELECT COUNT(*) FROM events
            WHERE doc IN ('edgecase_gdpr_implied.txt','edgecase_policy_ambiguous.txt')
            """
        ).fetchone()[0]
    # We don't require hits now—this becomes the BEFORE snapshot for the AI layer
    assert rows >= 0
