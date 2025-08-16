# tests/conftest.py
from __future__ import annotations

from pathlib import Path
import shutil
import sqlite3
import pytest

# ---- Paths (resolved once) ---------------------------------------------------
REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "outputs"
DB_PATH = REPO / "data" / "cc_audit.sqlite"
DOCS_DIR = REPO / "data" / "docs"
TESTDOCS_DIR = REPO / "data" / "testdocs"


# ---- Helpers -----------------------------------------------------------------
def _safe_unlink(p: Path) -> None:
    """Best-effort file removal (Windows locks tolerated)."""
    try:
        if p.exists():
            p.unlink()
    except PermissionError:
        # As a last resort, truncate if it’s the DB file that’s locked
        if p == DB_PATH:
            try:
                with sqlite3.connect(DB_PATH) as cx:
                    cx.execute("PRAGMA journal_mode=WAL;")
                    cx.execute("DELETE FROM events;")
                    cx.execute("VACUUM;")
            except sqlite3.Error:
                pass


def _clean_outputs_dir() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUT_DIR.glob("findings_*.*"):
        _safe_unlink(f)


def _clean_audit_db() -> None:
    if DB_PATH.exists():
        _safe_unlink(DB_PATH)


def _ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (REPO / "data").mkdir(parents=True, exist_ok=True)


# ---- Global per-test reset ---------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_env_between_tests():
    """
    Autouse fixture: each test starts from a known state.
    - clears timestamped CSV/JSON under data/outputs/
    - removes (or truncates) the SQLite audit DB
    - ensures required directories exist
    """
    _ensure_dirs()
    _clean_outputs_dir()
    _clean_audit_db()
    yield
    # Post-test: keep outputs/db for assertions made by tests


# ---- Public fixtures (import-free in tests) ----------------------------------
@pytest.fixture
def repo_root() -> Path:
    """Path to the repository root (Path)."""
    return REPO


@pytest.fixture
def temp_docs(tmp_path: Path) -> Path:
    """
    An isolated scratch 'docs' directory for tests that want to run the
    pipeline against a private area instead of the shared data/docs.
    NOTE: If your code reads strictly from data/docs/, prefer `sandbox_docs`.
    """
    d = tmp_path / "docs"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def sandbox_docs() -> callable:
    """
    Helper that copies named fixtures from data/testdocs/ into data/docs/.
    Usage in tests:
        def test_something(sandbox_docs):
            sandbox_docs("file1.txt", "edgecase_gdpr.txt")
            # run your pipeline which reads from data/docs/
    Returns a callable that raises if the source file is missing.
    """
    _ensure_dirs()

    def _copy(*names: str) -> list[Path]:
        copied: list[Path] = []
        for name in names:
            src = TESTDOCS_DIR / name
            if not src.exists():
                raise FileNotFoundError(f"Missing test fixture: {src}")
            dst = DOCS_DIR / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Binary-safe copy (works for .txt, .pdf, etc.)
            shutil.copy2(src, dst)
            copied.append(dst)
        return copied

    return _copy


# Ensure src modules are imported so coverage can measure them
import os, sys, importlib

# put ./src on the path (pytest.ini does this too; belt-and-suspenders)
HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "src")))

# import the modules that live directly under src/
for mod in ("audit", "engine", "env", "llm_layer"):
    try:
        importlib.import_module(mod)
    except Exception as e:
        # don't fail tests for import issues here; coverage just won't include that module
        print(f"[conftest] warning: could not import {mod}: {e}")

# optional: quiet noisy sqlite ResourceWarnings in CI
import gc, sqlite3, pytest


@pytest.fixture(autouse=True)
def _close_sqlite_handles():
    yield
    gc.collect()
    for obj in gc.get_objects():
        if isinstance(obj, sqlite3.Connection):
            try:
                obj.close()
            except Exception:
                pass
