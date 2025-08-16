# tests/exemplars/test_regression_exemplars.py
# Tags: #cctests #ccbaseline
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import pytest

REPO = Path(__file__).resolve().parents[2]  # .../cc-prototype
PY = sys.executable
SCRIPT = REPO / "cc_mvp.py"  # absolute path to script


def _run(cmd: list[str]) -> str:
    """Run a command at repo root and assert success."""
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if res.returncode != 0:
        # Show both streams to help when something goes wrong
        print("STDOUT:\n", res.stdout)
        print("STDERR:\n", res.stderr)
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
    # copy exemplar into docs/
    [target] = sandbox_docs(f"exemplars/{doc}")
    assert target.exists(), f"Expected test doc was not copied: {target}"

    # run compliance classifier (absolute path to avoid cwd confusion)
    _run([PY, str(SCRIPT), "--regime", regime])

    # basic stdout sanity
    out = _run([PY, str(SCRIPT), "--regime", regime])
    assert f"Compliance Results — {regime}" in out or f"Compliance Results - {regime}" in out
