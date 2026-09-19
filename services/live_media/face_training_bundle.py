"""Portable rights-gated input bundle for Seldrune Face GPU workers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from services.live_media.face_dataset import DatasetSplit, IdentityRecord, validate_manifest


@dataclass(frozen=True)
class FaceTrainingBundle:
    records: tuple[IdentityRecord, ...]
    capture_paths: dict[str, Path]

    def validate(self) -> None:
        validate_manifest(self.records)
        admitted = {capture for record in self.records for capture in record.capture_ids}
        if set(self.capture_paths) != admitted:
            raise ValueError("capture path mapping must exactly match admitted capture IDs")
        for capture_id, path in self.capture_paths.items():
            if not path.is_file():
                raise ValueError(f"capture file is missing for {capture_id}")


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def load_training_bundle(path: str | Path) -> FaceTrainingBundle:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    records = tuple(
        IdentityRecord(
            subject_id=item["subject_id"],
            consent_record=item["consent_record"],
            rights_basis=item["rights_basis"],
            capture_ids=tuple(item["capture_ids"]),
            allowed_purposes=tuple(item["allowed_purposes"]),
            provenance=item["provenance"],
            split=DatasetSplit(item["split"]),
            expires_at=_parse_datetime(item.get("expires_at")),
            revoked_at=_parse_datetime(item.get("revoked_at")),
        )
        for item in payload["identities"]
    )
    root = source.parent
    captures = {
        capture_id: (root / relative_path).resolve()
        for capture_id, relative_path in payload["captures"].items()
    }
    bundle = FaceTrainingBundle(records=records, capture_paths=captures)
    bundle.validate()
    return bundle
