#!/usr/bin/env python3
"""
setup.py

Cross-platform setup and run script. Works on Windows, macOS, and Linux.

Usage:
    python setup.py            # create venv, install deps, run simulation
    python setup.py run        # run the simulation
    python setup.py scenarios  # run all four demonstration scenarios and save plots
    python setup.py test       # run the full test suite
    python setup.py lint       # run the linter
    python setup.py clean      # remove venv and output folder
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

VENV        = Path("venv")
REQUIREMENTS = Path("requirements.txt")
# Sentinel written after a successful install — skips reinstall on next run
_SENTINEL   = VENV / ".installed"

# ---------------------------------------------------------------------------
# Resolve venv binary paths cross-platform
# ---------------------------------------------------------------------------

def _venv_bin(name: str) -> Path:
    if sys.platform == "win32":
        return VENV / "Scripts" / (name + ".exe")
    return VENV / "bin" / name

VENV_PYTHON = _venv_bin("python")
VENV_PIP    = _venv_bin("pip")
VENV_PYTEST = _venv_bin("pytest")
VENV_RUFF   = _venv_bin("ruff")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: list, **kwargs):
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        sys.exit(result.returncode)


def ensure_venv():
    """Create venv and install all dependencies — skipped if already done."""
    if _SENTINEL.exists():
        return  # already set up, nothing to do

    if not VENV_PYTHON.exists():
        print("Creating virtual environment...")
        run([sys.executable, "-m", "venv", str(VENV)])

    print("Installing dependencies...")
    run([str(VENV_PYTHON), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    run([str(VENV_PYTHON), "-m", "pip", "install", "--quiet",
         "-r", str(REQUIREMENTS), "pytest", "pytest-cov", "ruff"])

    _SENTINEL.touch()
    print("Setup complete.\n")

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_run():
    ensure_venv()
    run([str(VENV_PYTHON), "main.py"])

def cmd_scenarios():
    ensure_venv()
    run([str(VENV_PYTHON), "run_scenarios.py"])

def cmd_test():
    ensure_venv()
    run([str(VENV_PYTEST), "tests/", "-v"])

def cmd_lint():
    ensure_venv()
    run([str(VENV_RUFF), "check", "."])

def cmd_clean():
    for path in [VENV, Path("output"), Path("__pycache__"), Path(".pytest_cache")]:
        if path.exists():
            shutil.rmtree(path)
            print(f"Removed {path}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMMANDS = {
    "run":       cmd_run,
    "scenarios": cmd_scenarios,
    "test":      cmd_test,
    "lint":      cmd_lint,
    "clean":     cmd_clean,
}

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "run"

    if command not in COMMANDS:
        print(f"Unknown command: '{command}'")
        print(f"Available: {', '.join(COMMANDS)}")
        sys.exit(1)

    COMMANDS[command]()
