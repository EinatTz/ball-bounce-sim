"""
conftest.py — adds the project root to sys.path so tests can import
source modules directly without an installed package.
"""
import sys
from pathlib import Path

# Project root is one level up from this file (tests/conftest.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
