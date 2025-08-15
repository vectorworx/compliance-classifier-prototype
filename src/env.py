# src/env.py
# Tags: #ccenv
import os
from pathlib import Path


def load_env() -> None:
    """
    Loads variables from a local .env if present (dev),
    but does nothing in CI where GitHub injects env vars.
    Safe to call multiple times.
    """
    # Heuristic: GitHub Actions sets GITHUB_ACTIONS=true
    in_ci = os.getenv("GITHUB_ACTIONS", "").lower() == "true"
    if in_ci:
        return
    # Local dev: read .env if it exists
    env_path = Path(".env")
    if env_path.exists():
        try:
            from dotenv import load_dotenv  # python-dotenv

            load_dotenv(dotenv_path=env_path)
        except Exception:
            # Non-fatal; we still allow running with OS env only
            pass


def require(name: str) -> str:
    """Fetch an env var or raise a clear error if missing."""
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Set it in your local .env (ignored by git) or in GitHub Actions secrets."
        )
    return val
