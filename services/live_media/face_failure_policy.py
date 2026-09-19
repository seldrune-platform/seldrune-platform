"""Fail-closed policy for Face GPU execution."""
from __future__ import annotations

def safe_failure_message(error: Exception) -> str:
    name=type(error).__name__
    return f"{name}: Face GPU run failed; inspect protected worker logs"
