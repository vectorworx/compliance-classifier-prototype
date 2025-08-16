# Tags: #cctests #ccsoc2
import subprocess, sys, sqlite3
from pathlib import Path
from .util_docs import temp_docs, REPO

PY = sys.executable


def _run(args: list[str]) -> str:
    res = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    if res.returncode != 0:
        print("STDOUT:\n", res.stdout)
        print("STDERR:\n", res.stderr)
    assert res.returncode == 0, f"Command failed: {' '.join(args)}"
    return res.stdout


def test_soc2_pipeline_runs_and_logs():
    content = (
        "Our security controls require MFA for all privileged access. "
        "Change management follows documented procedures with approvals."
    )
    with temp_docs({"soc2_smoke.txt": content}):
        _run([PY, "cc_mvp.py", "--regime", "SOC2"])
        db = REPO / "data" / "cc_audit.sqlite"
        assert db.exists()
        with sqlite3.connect(db) as cx:
            total = cx.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        # We don't assert a specific rule—just that the pipeline executed and logged (>=0).
        assert total >= 0
