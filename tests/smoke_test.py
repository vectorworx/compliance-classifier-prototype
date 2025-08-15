# tests/smoke_test.py
# Tags: #cctest #ccproof
import os, sqlite3, shutil, subprocess, sys, json, glob
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable


def _reset_outputs():
    out = REPO / "data" / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("findings_*"):
        try:
            f.unlink()
        except Exception:
            pass

    db = REPO / "data" / "cc_audit.sqlite"
    if db.exists():
        try:
            db.unlink()
            return
        except PermissionError:
            # Windows sometimes holds a handle briefly; fall back to truncating
            try:
                with sqlite3.connect(db) as cx:
                    cx.execute("PRAGMA journal_mode=WAL;")  # tolerate concurrent readers
                    cx.execute("DELETE FROM events;")
                    cx.execute("VACUUM;")
            except sqlite3.Error:
                # If schema isn't there yet, just remove the file on next run
                pass


def _ensure_docs():
    docs_dir = REPO / "data" / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "sample.txt").write_text(
        "We notify the Supervisory Authority within seventy-two hours of any personal data breach.\n"
        "All users must use MFA.\n",
        encoding="utf-8",
    )


def _run(cmd):
    print("→", " ".join(cmd))
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr)
    assert res.returncode == 0, f"Command failed: {' '.join(cmd)}"
    return res.stdout


def test_gdpr_run_creates_outputs():
    _reset_outputs()
    _ensure_docs()
    _run([PY, "cc_mvp.py", "--regime", "GDPR"])
    # outputs exist
    outs = list((REPO / "data" / "outputs").glob("findings_gdpr_*.csv"))
    assert outs, "No GDPR CSV output created"
    # audit exists
    db = REPO / "data" / "cc_audit.sqlite"
    assert db.exists(), "Audit DB not created"
    with sqlite3.connect(db) as cx:
        n = cx.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert n > 0, "No events logged to audit DB"


def test_soc2_run_executes():
    _reset_outputs()
    _ensure_docs()
    _run([PY, "cc_mvp.py", "--regime", "SOC2"])
    outs = list((REPO / "data" / "outputs").glob("findings_soc2_*.csv"))
    # SOC2 might not hit critical rules on sample.txt; just ensure file exists OR graceful no-output
    db = REPO / "data" / "cc_audit.sqlite"
    assert db.exists(), "Audit DB not created for SOC2"


# tests/smoke_test.py
# Tags: #cctest #ccproof
import os, sys, subprocess, sqlite3, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

OUTPUT_DIR = REPO / "data" / "outputs"
DB_PATH = REPO / "data" / "cc_audit.sqlite"
DOCS_DIR = REPO / "data" / "docs"

# --- Helpers -----------------------------------------------------------------


def _safe_unlink(path: Path) -> None:
    """Attempt to delete a file; ignore if missing or locked (Windows)."""
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except PermissionError:
        # On Windows, a brief retry can help if a handle is still closing.
        time.sleep(0.2)
        try:
            path.unlink()
        except Exception:
            # Give up silently; caller may fall back to truncate
            pass
    except Exception:
        # Best-effort cleanup; tests should remain resilient
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
            # Be tolerant if schema doesn't exist yet.
            try:
                cx.execute("PRAGMA journal_mode=WAL;")
                cx.execute("DELETE FROM events;")
                cx.execute("VACUUM;")
            except sqlite3.OperationalError:
                # Table not created yet; nothing to clear.
                pass
    except sqlite3.Error:
        # If the DB is corrupt or locked beyond our control, last resort: attempt unlink once.
        _safe_unlink(DB_PATH)


def _reset_outputs() -> None:
    """Clean output artifacts and audit DB content in a cross-platform, lock-tolerant way."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUTPUT_DIR.glob("findings_*"):
        _safe_unlink(f)
    # Prefer truncation over deletion to avoid file-lock races on Windows
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
    # Make output deterministic in CI/Windows consoles
    env.setdefault("PYTHONUTF8", "1")
    print("→", " ".join(cmd))
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
    # Show stdout/stderr for debugging if something goes wrong
    if res.stdout:
        print(res.stdout)
    if res.returncode != 0:
        if res.stderr:
            print(res.stderr)
    assert res.returncode == 0, f"Command failed: {' '.join(cmd)}"
    return res.stdout


# --- Tests -------------------------------------------------------------------


def test_gdpr_run_creates_outputs():
    _reset_outputs()
    _ensure_docs()
    _run([PY, "cc_mvp.py", "--regime", "GDPR"])

    # CSV output exists
    outs = list(OUTPUT_DIR.glob("findings_gdpr_*.csv"))
    assert outs, "No GDPR CSV output created"

    # Audit DB exists and has events
    assert DB_PATH.exists(), "Audit DB not created"
    with sqlite3.connect(DB_PATH) as cx:
        n = cx.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert n > 0, "No events logged to audit DB"


def test_soc2_run_executes():
    _reset_outputs()
    _ensure_docs()
    _run([PY, "cc_mvp.py", "--regime", "SOC2"])

    # SOC2 may or may not produce rule hits on sample; ensure run completed and DB exists.
    assert DB_PATH.exists(), "Audit DB not created for SOC2"

    # If outputs were produced, at least the CSV should be present.
    # We do not require it (rules may not match), but this helps catch regressions that prevent writing.
    any_soc2_csv = any(OUTPUT_DIR.glob("findings_soc2_*.csv"))
    # Soft assertion style: if not produced, that's acceptable; the main success criteria is process completed + DB exists.
    if not any_soc2_csv:
        # Ensure we at least didn't create stray files of other regimes here by mistake.
        assert not list(
            OUTPUT_DIR.glob("findings_gdpr_*.csv")
        ), "Unexpected GDPR outputs found during SOC2 test run"
