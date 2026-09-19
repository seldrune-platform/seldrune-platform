"""Deterministic digest verification for QNode reports."""

from __future__ import annotations

from hashlib import sha256

from .qnode import QNodeReport


def report_digest(reports: tuple[QNodeReport, ...]) -> str:
    payload = "|".join(
        f"{report.role.value}:{int(report.completed)}:{report.metric}"
        for report in sorted(reports, key=lambda item: item.role.value)
    )
    return sha256(payload.encode()).hexdigest()
