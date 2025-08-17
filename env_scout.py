#!/usr/bin/env python3
"""
env_scout.py
-------------
Collects a safe, structured snapshot of your system + project to "level set"
environments for new contributors or new machines.

✅ Why this matters for SDET/QA/AI workflows:
- Reproducibility: Encodes critical env info (OS, paths, toolchain) so automated tests & agentic
  systems run identically across machines/CI.
- Drift detection: Makes it obvious when dev/CI diverge (e.g., Python/Node/Docker mismatches).
- Rapid onboarding: A single JSON/MD artifact becomes your "bootstrap brief" for any project.
- Security-aware: Redacts likely secrets, avoids reading .env contents, and lists only filenames
  for sensitive directories (e.g., ~/.ssh).

Usage:
  python env_scout.py --project-dir . --output-dir ./env_scout_out --max-depth 3 --full

Flags:
  --project-dir PATH   Project root to scan (default: current dir)
  --output-dir PATH    Where to write JSON/MD reports (default: ./env_scout_out)
  --max-depth N        Depth for project tree (default: 3)
  --full               Heavier checks (package manager inventories, etc.)
  --no-redact          Disable environment variable redaction (default: redact enabled)
  --include PATTERN    Extra glob(s) to include (repeatable)
  --exclude PATTERN    Extra glob(s) to exclude (repeatable)
"""

from __future__ import annotations
import argparse
import dataclasses
import datetime as dt
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# ---------------------------
# Utility helpers (robust, quiet, cross-platform)
# ---------------------------


def which(cmd: str) -> str | None:
    """Return the full path to an executable if found, else None."""
    return shutil.which(cmd)


def run_cmd(cmd: list[str], timeout: int = 10) -> tuple[int, str]:
    """
    Safely run an external command, capture combined stdout+stderr, return (code, text).
    - Never raises; returns non-zero code on failure.
    - Short timeouts by default to avoid hanging.
    """
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        return proc.returncode, proc.stdout.strip()
    except (FileNotFoundError, PermissionError) as e:
        return 127, f"{type(e).__name__}: {e}"
    except subprocess.TimeoutExpired:
        return 124, "TimeoutExpired"
    except Exception as e:
        return 1, f"Error: {e}"


def hash_file(path: Path, algo: str = "sha256", max_bytes: int = 2_000_000) -> str | None:
    """
    Hash file contents up to max_bytes for quick fingerprinting (avoids huge files).
    Useful to detect drift without storing content.
    """
    try:
        h = hashlib.new(algo)
        with path.open("rb") as f:
            remaining = max_bytes
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                h.update(chunk)
                remaining -= len(chunk)
        return f"{algo}:{h.hexdigest()}"
    except Exception:
        return None


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


# ---------------------------
# Redaction logic for env vars
# ---------------------------

SUSPECT_KEYS = re.compile(
    r"(?:KEY|SECRET|TOKEN|PASSWORD|PWD|PASS|CREDENTIAL|SESSION|BEARER|PRIVATE|API|AUTH|SIGNATURE)",
    re.IGNORECASE,
)

WHITELIST_ENV = {
    "PATH",
    "HOME",
    "USERPROFILE",
    "SHELL",
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "USERNAME",
    "TEMP",
    "TMP",
    "TERM",
    "PYENV_ROOT",
    "CONDA_DEFAULT_ENV",
    "VIRTUAL_ENV",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "LOCALAPPDATA",
    "APPDATA",
    "XDG_CONFIG_HOME",
}


def collect_env_vars(redact: bool = True) -> dict[str, Any]:
    """
    Collect environment variables with light redaction:
    - Always include WHITELIST_ENV
    - Include any others that do NOT match SUSPECT_KEYS
    - If redact=False, include all vars (still a good idea to keep .env files out of scope!)
    """
    env = dict(os.environ)
    result = {}
    for k, v in env.items():
        if not redact:
            result[k] = v
            continue

        if k in WHITELIST_ENV:
            result[k] = v
        elif SUSPECT_KEYS.search(k):
            result[k] = "<REDACTED>"
        else:
            # include non-suspect keys but truncate very long values
            val = v if len(v) <= 512 else v[:512] + "...<truncated>"
            result[k] = val
    return result


# ---------------------------
# System inventory
# ---------------------------


def detect_virtual_env() -> dict[str, Any]:
    return {
        "is_venv": bool(os.environ.get("VIRTUAL_ENV")),
        "venv_path": os.environ.get("VIRTUAL_ENV"),
        "conda_env": os.environ.get("CONDA_DEFAULT_ENV"),
        "pyenv_root": os.environ.get("PYENV_ROOT"),
    }


def basic_system_info() -> dict[str, Any]:
    uname = platform.uname()
    info = {
        "timestamp": now_iso(),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "platform": platform.platform(),
            "machine": uname.machine,
            "processor": uname.processor,
            "architecture": platform.architecture()[0],
        },
        "python": {
            "version": sys.version.split("\n")[0],
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "virtual_env": detect_virtual_env(),
        "hostname": socket.gethostname(),
    }

    # CPU + RAM best-effort without extra deps
    try:
        info["cpu_count"] = os.cpu_count()
    except Exception:
        info["cpu_count"] = None

    # RAM: psutil gives best data, fallback to None
    try:
        import psutil  # type: ignore

        info["ram_bytes"] = psutil.virtual_memory().total
    except Exception:
        info["ram_bytes"] = None

    # Disks (root + project later)
    try:
        root = (
            Path("/").resolve()
            if os.name != "nt"
            else Path(os.environ.get("SystemDrive", "C:") + "\\")
        )
        usage = shutil.disk_usage(str(root))
        info["disk_root"] = {
            "path": str(root),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        }
    except Exception:
        info["disk_root"] = None

    # Current shell (best effort cross-platform)
    info["shell"] = os.environ.get("SHELL") or os.environ.get("ComSpec") or None
    return info


# ---------------------------
# Toolchain + CLIs
# ---------------------------

TOOL_QUERIES = [
    (["git", "--version"], "git"),
    (["git", "lfs", "version"], "git_lfs"),
    (["python", "--version"], "python_cli"),
    (["pip", "--version"], "pip"),
    (["pipx", "--version"], "pipx"),
    (["poetry", "--version"], "poetry"),
    (["uv", "--version"], "uv"),
    (["conda", "--version"], "conda"),
    (["node", "--version"], "node"),
    (["npm", "--version"], "npm"),
    (["pnpm", "--version"], "pnpm"),
    (["yarn", "--version"], "yarn"),
    (["nvm", "--version"], "nvm"),
    (["java", "-version"], "java"),
    (["javac", "-version"], "javac"),
    (["mvn", "-v"], "maven"),
    (["gradle", "-v"], "gradle"),
    (["go", "version"], "go"),
    (["rustc", "--version"], "rustc"),
    (["cargo", "--version"], "cargo"),
    (["dotnet", "--info"], "dotnet"),
    (["powershell", "-Version"], "powershell"),
    (["pwsh", "--version"], "pwsh"),
    (["wsl.exe", "-l", "-v"], "wsl"),  # Windows only
    (["docker", "--version"], "docker"),
    (["docker", "compose", "version"], "docker_compose"),
    (["kubectl", "version", "--client", "--short"], "kubectl"),
    (["helm", "version", "--short"], "helm"),
    (["aws", "--version"], "awscli"),
    (["az", "version"], "azurecli"),
    (["gcloud", "--version"], "gcloud"),
    (["code", "--version"], "vscode"),
]


def collect_tools() -> dict[str, dict[str, Any]]:
    results = {}
    for cmd, key in TOOL_QUERIES:
        exe = which(cmd[0])
        if not exe:
            results[key] = {"found": False}
            continue
        code, out = run_cmd(cmd)
        results[key] = {"found": True, "code": code, "output": out}
    return results


# ---------------------------
# Git info (safe)
# ---------------------------


def collect_git_info(project_dir: Path) -> dict[str, Any]:
    def git(args: list[str], timeout=10) -> tuple[int, str]:
        return run_cmd(["git", *args], timeout=timeout)

    info = {"is_repo": False}
    code, out = git(["rev-parse", "--is-inside-work-tree"])
    if code != 0 or out.strip().lower() != "true":
        return info

    info["is_repo"] = True

    # Branch, commit, remotes
    _, branch = git(["rev-parse", "--abbrev-ref", "HEAD"])
    _, commit = git(["rev-parse", "HEAD"])
    _, status = git(["status", "--porcelain"])
    _, remote = git(["remote", "-v"])

    info["branch"] = branch.strip()
    info["commit"] = commit.strip()
    info["dirty_files"] = len([line for line in status.splitlines() if line.strip()])
    info["remotes"] = sorted({line.strip() for line in remote.splitlines()})
    info["hooks_present"] = sorted(
        [p.name for p in (project_dir / ".git" / "hooks").glob("*") if p.is_file()]
    )

    return info


# ---------------------------
# Project scan
# ---------------------------

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    ".tox",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".parcel-cache",
    ".cache",
    ".gradle",
    "target",
    ".idea",
    ".vscode",
    ".devcontainer",
}

CANDIDATE_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "setup.cfg",
    "setup.py",
    "tox.ini",
    ".python-version",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".editorconfig",
    ".pre-commit-config.yaml",
    ".gitignore",
    "Makefile",
    "README.md",
    "README.MD",
    "LICENSE",
    "LICENSE.md",
    "pom.xml",
    "build.gradle",
    "settings.gradle",
    "gradlew",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    ".tool-versions",  # asdf
]


def within_depth(root: Path, path: Path, max_depth: int) -> bool:
    rel = path.relative_to(root)
    return len(rel.parts) <= max_depth


def project_tree(
    root: Path, max_depth: int, includes: list[str], excludes: list[str]
) -> dict[str, Any]:
    """
    Returns a compact tree (dirs/files) limited by depth + glob patterns.
    """

    def is_ignored_dir(name: str) -> bool:
        if name in DEFAULT_IGNORE_DIRS:
            return True
        for pat in excludes:
            if fnmatch.fnmatch(name, pat):
                return True
        return False

    tree = {"root": str(root), "max_depth": max_depth, "entries": []}
    for dirpath, dirnames, filenames in os.walk(root):
        dirpath_p = Path(dirpath)
        # Prune depth
        try:
            if not within_depth(root, dirpath_p, max_depth):
                dirnames[:] = []  # stop descending
                continue
        except ValueError:
            # if path can't be made relative for some reason, skip
            continue

        # Prune ignored dirs in-place
        dirnames[:] = [d for d in dirnames if not is_ignored_dir(d)]

        # Keep a compact listing
        rel = str(dirpath_p.relative_to(root)) if dirpath_p != root else "."
        file_list = []

        for f in filenames:
            keep = True
            for pat in ["*.env*", "*.pem", "*.p12", "*.key", "*.crt", "*.der"]:
                if fnmatch.fnmatch(f, pat):
                    keep = False  # don't list sensitive files by default
                    break
            for pat in excludes:
                if fnmatch.fnmatch(f, pat):
                    keep = False
                    break
            if includes:
                # If includes provided, only keep files that match any include pattern
                keep = any(fnmatch.fnmatch(f, pat) for pat in includes)
            if keep:
                file_list.append(f)

        if file_list or dirnames:
            tree["entries"].append(
                {"dir": rel, "dirs": sorted(dirnames), "files": sorted(file_list)}
            )
    return tree


def project_fingerprints(root: Path) -> list[dict[str, Any]]:
    """
    Hashes key config files (first 2MB) to detect drift without including contents.
    """
    found = []
    for name in CANDIDATE_FILES:
        p = root / name
        if p.exists() and p.is_file():
            found.append({"file": str(p), "hash": hash_file(p), "size_bytes": p.stat().st_size})
    return found


def parse_dependencies(root: Path) -> dict[str, Any]:
    """
    Lightweight dependency extraction from manifest files.
    - Python: requirements*.txt (raw lines), pyproject (tool.poetry deps, PEP 621 suggests parsing TOML)
    - Node: package.json deps/devDeps
    Never executes installs; just parses.
    """
    deps: dict[str, Any] = {"python": {}, "node": {}}
    # Python requirements
    for req_name in ["requirements.txt", "requirements-dev.txt"]:
        req = root / req_name
        if req.exists():
            try:
                lines = []
                for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        lines.append(line)
                deps["python"][req_name] = lines
            except Exception:
                deps["python"][req_name] = "<unreadable>"

    # pyproject.toml (basic TOML parse without third-party libs)
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            # naive extraction (keeps this script dependency-free)
            poetry_deps = {}
            in_deps = False
            for line in content.splitlines():
                if line.strip().startswith("[tool.poetry.dependencies]"):
                    in_deps = True
                    continue
                if line.strip().startswith("[") and in_deps:
                    in_deps = False
                if in_deps:
                    m = re.match(r'\s*([A-Za-z0-9_.\-]+)\s*=\s*["\']?([^"\']+)["\']?', line)
                    if m:
                        poetry_deps[m.group(1)] = m.group(2)
            if poetry_deps:
                deps["python"]["pyproject.toml(tool.poetry.dependencies)"] = poetry_deps
        except Exception:
            deps["python"]["pyproject.toml"] = "<unreadable>"

    # Node package.json
    pkg = root / "package.json"
    if pkg.exists():
        try:
            j = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
            node_deps = {}
            for key in [
                "dependencies",
                "devDependencies",
                "optionalDependencies",
                "peerDependencies",
            ]:
                if key in j and isinstance(j[key], dict):
                    node_deps[key] = j[key]
            if node_deps:
                deps["node"]["package.json"] = node_deps
        except Exception:
            deps["node"]["package.json"] = "<unreadable>"

    return deps


def list_ssh_files() -> dict[str, Any]:
    """
    Lists filenames only in ~/.ssh (no contents). Useful to confirm key presence without secrets.
    """
    results = {"home": str(Path.home()), "ssh_dir": None, "files": []}
    ssh_dir = Path.home() / ".ssh"
    if ssh_dir.exists() and ssh_dir.is_dir():
        results["ssh_dir"] = str(ssh_dir)
        for p in ssh_dir.iterdir():
            if p.is_file():
                results["files"].append(p.name)
    return results


def network_info() -> dict[str, Any]:
    """
    Minimal network info (no external calls).
    """
    info = {"hostname": socket.gethostname()}
    try:
        info["fqdn"] = socket.getfqdn()
    except Exception:
        info["fqdn"] = None
    try:
        info["host_aliases"] = socket.gethostbyname_ex(info["hostname"])
    except Exception:
        info["host_aliases"] = None
    return info


# ---------------------------
# Optional heavier inventories (only under --full)
# ---------------------------

FULL_INVENTORY_CMDS = [
    (["pip", "list"], "pip_list"),
    (["conda", "list"], "conda_list"),
    (["npm", "ls", "-g", "--depth=0"], "npm_global"),
    (["pnpm", "ls", "-g", "--depth=0"], "pnpm_global"),
    (["yarn", "global", "list", "--depth=0"], "yarn_global"),
    (["brew", "list"], "brew_list"),  # macOS only (if present)
    (["choco", "list", "-lo"], "choco_list"),  # Windows only (if present)
    (["apt", "list", "--installed"], "apt_list"),  # Debian based; can be large
]


def collect_full_inventory() -> dict[str, Any]:
    results = {}
    for cmd, key in FULL_INVENTORY_CMDS:
        if not which(cmd[0]):
            continue
        code, out = run_cmd(cmd, timeout=25)
        # Trim very large outputs to keep report manageable
        if len(out) > 200_000:
            out = out[:200_000] + "\n...<truncated>"
        results[key] = {"code": code, "output": out}
    return results


# ---------------------------
# Writing reports
# ---------------------------


def write_reports(report: dict[str, Any], outdir: Path) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = outdir / f"env_scout_report_{stamp}.json"
    md_path = outdir / f"env_scout_report_{stamp}.md"

    # JSON (pretty)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown (concise)
    lines = []
    lines.append(f"# Environment & Project Report")
    lines.append(f"- Generated: `{report['meta']['timestamp']}`")
    lines.append(f"- Project: `{report['project']['root']}`")
    lines.append(f"- OS: `{report['system']['os']['platform']}`")
    lines.append(f"- Python: `{report['system']['python']['version']}`")
    lines.append("")
    lines.append("## Highlights")
    git = report.get("git", {})
    if git.get("is_repo"):
        lines.append(
            f"- Git: branch `{git.get('branch')}`, commit `{git.get('commit')[:12]}`; dirty files: {git.get('dirty_files')}"
        )
    else:
        lines.append("- Git: (not a repository)")
    lines.append(
        f"- Tooling discovered: {', '.join(sorted([k for k, v in report['tools'].items() if v.get('found')])) or '(none)'}"
    )
    lines.append(
        f"- Key manifests present: {', '.join(sorted({Path(fp['file']).name for fp in report['project']['fingerprints']}))}"
    )
    lines.append("")
    lines.append("## Project Tree (truncated)")
    for entry in report["project"]["tree"]["entries"][:25]:
        lines.append(f"- `{entry['dir']}`")
        if entry["files"]:
            lines.append(
                f"  - files: {', '.join(entry['files'][:8])}{' ...' if len(entry['files'])>8 else ''}"
            )
    lines.append("")
    lines.append("## Notes")
    lines.append("- Environment variables with suspicious names are redacted.")
    lines.append("- Sensitive files like `*.env` are not listed.")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return json_path, md_path


# ---------------------------
# Main
# ---------------------------


def main():
    ap = argparse.ArgumentParser(description="Environment & Project Bootstrap Scanner")
    ap.add_argument("--project-dir", default=".", type=str)
    ap.add_argument("--output-dir", default="./env_scout_out", type=str)
    ap.add_argument("--max-depth", default=3, type=int)
    ap.add_argument(
        "--full", action="store_true", help="Run heavier inventories (package managers, etc.)"
    )
    ap.add_argument(
        "--no-redact", action="store_true", help="Do NOT redact env vars (not recommended)"
    )
    ap.add_argument(
        "--include", action="append", default=[], help="Glob(s) to include in tree (repeatable)"
    )
    ap.add_argument(
        "--exclude", action="append", default=[], help="Glob(s) to exclude from tree (repeatable)"
    )
    args = ap.parse_args()

    project_root = Path(args.project_dir).resolve()
    outdir = Path(args.output_dir).resolve()
    redact = not args.no_redact

    # Collect
    system = basic_system_info()
    tools = collect_tools()
    env_vars = collect_env_vars(redact=redact)
    git = collect_git_info(project_root)
    proj_tree = project_tree(project_root, args.max_depth, args.include, args.exclude)
    proj_fps = project_fingerprints(project_root)
    deps = parse_dependencies(project_root)
    ssh = list_ssh_files()
    net = network_info()

    # Disk usage for project root too
    try:
        usage = shutil.disk_usage(str(project_root))
        proj_disk = {"total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free}
    except Exception:
        proj_disk = None

    report: dict[str, Any] = {
        "meta": {
            "timestamp": now_iso(),
            "tool": "env_scout",
            "version": "1.0.0",
        },
        "system": system,
        "env": env_vars,
        "tools": tools,
        "git": git,
        "project": {
            "root": str(project_root),
            "disk": proj_disk,
            "tree": proj_tree,
            "fingerprints": proj_fps,
            "dependencies": deps,
        },
        "security": {
            "ssh": ssh,
            "redaction_enabled": redact,
            "excluded_defaults": sorted(DEFAULT_IGNORE_DIRS),
        },
        "network": net,
    }

    if args.full:
        report["full_inventory"] = collect_full_inventory()

    json_path, md_path = write_reports(report, outdir)

    # Console summary
    print("\n=== env_scout summary ===")
    print(f"Project: {project_root}")
    print(f"OS: {system['os']['platform']}")
    print(f"Python: {system['python']['version']}")
    found_tools = [k for k, v in tools.items() if v.get("found")]
    print(f"Tools found: {', '.join(sorted(found_tools)) or '(none)'}")
    print(f"Git repo: {'yes' if git.get('is_repo') else 'no'}")
    print(f"Outputs:\n- JSON: {json_path}\n- Markdown: {md_path}")
    print("=========================\n")


if __name__ == "__main__":
    main()
