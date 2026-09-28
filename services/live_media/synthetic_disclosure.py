"""Required participant-visible wording for LiveShell transformed video.

To customize the copy, change VISIBLE_DISCLOSURE_LABEL to one of the supported
clear disclosure phrases below. Blank or non-disclosure wording fails closed.
"""

from __future__ import annotations

DEFAULT_DISCLOSURE_LABEL = "AI MODIFIED"
SUPPORTED_DISCLOSURE_LABELS = frozenset(
    {
        "AI MODIFIED",
        "AI-ALTERED VIDEO",
        "SYNTHETIC MEDIA",
    }
)

# Edit this one setting to use another supported, clearly visible disclosure.
VISIBLE_DISCLOSURE_LABEL = DEFAULT_DISCLOSURE_LABEL


def validate_disclosure_label(label: str) -> str:
    """Normalize supported copy and reject blank or ambiguous labels."""
    if not isinstance(label, str):
        raise ValueError("live video requires an approved visible disclosure label")
    normalized = " ".join(label.split()).upper()
    if normalized not in SUPPORTED_DISCLOSURE_LABELS:
        raise ValueError("live video requires an approved visible disclosure label")
    return normalized


def get_visible_disclosure_label() -> str:
    """Return the configured disclosure or fail closed during worker startup."""
    return validate_disclosure_label(VISIBLE_DISCLOSURE_LABEL)
