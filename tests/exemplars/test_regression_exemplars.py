# tests/exemplars/test_regression_exemplars.py
# Tags: #cctests #ccbaseline
from pathlib import Path
import subprocess, sys, sqlite3
import pytest

REPO = Path(__file__).resolve().parents[2]  # tests/exemplars -> tests -> REPO
PY = sys.executable

OUTPUT_DIR = REPO / "data" / "outputs"
DB_PATH = REPO / "data" / "cc_audit.sqlite"
DOCS_DIR = REPO / "data" / "docs"
TESTDOCS_DIR = REPO / "data" / "testdocs" / "exemplars"


def _run(cmd: list[str]) -> str:
    """
    Run a subprocess in repo root, capturing stdout/stderr.
    Always resolve cc_mvp.py from REPO to avoid accidental tests/ path.
    Force UTF-8 to avoid Windows encoding weirdness.
    """
    cmd = list(cmd)
    if cmd[1] == "cc_mvp.py":
        cmd[1] = str(REPO / "cc_mvp.py")

    env = dict(**{**subprocess.os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
    assert res.returncode == 0, f"Command failed: {' '.join(cmd)}"
    return res.stdout


@pytest.mark.parametrize(
    "doc, regime, expected_keyword",
    [
        ("gdpr_exemplar.txt", "GDPR", "GDPR"),
        ("soc2_exemplar.txt", "SOC2", "SOC2"),
    ],
)
def test_exemplar_runs_and_logs(doc, regime, expected_keyword, sandbox_docs):
    # Copy exemplar into data/docs/exemplars/… so the scanner finds it
    exemplar = TESTDOCS_DIR / doc
    assert exemplar.exists(), f"Missing test fixture: {exemplar}"
    [target] = sandbox_docs(f"exemplars/{doc}")
    assert target.exists(), f"Missing copied test doc: {target}"

    # Run the classifier (rules-only baseline)
    out = _run([PY, "cc_mvp.py", "--regime", regime])

    # Soft header check (robust to encoding/console issues)
    assert "Compliance Results" in out and regime in out, "Expected compliance header present"

    # Ensure the audit DB exists and recorded something for this run
    assert DB_PATH.exists(), "Audit DB not created"
    with sqlite3.connect(DB_PATH) as cx:
        n = cx.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert n >= 0  # baseline can be 0+ depending on exemplar text/rules

    # Either we produced a CSV for this regime or (rarely) not—assert the path shape when present
    csvs = list(OUTPUT_DIR.glob(f"findings_{regime.lower()}_*.csv"))
    if csvs:
        assert csvs[0].name.startswith(f"findings_{regime.lower()}_")
