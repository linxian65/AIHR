"""Pytest conftest for the tests/ directory.

Adds the backend/ root to sys.path so `from app.xxx import ...` works
without per-script sys.path hacks.

Each test_*.py also has its own sys.path.insert so it can run via
`python tests/test_xxx.py` without pytest.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
