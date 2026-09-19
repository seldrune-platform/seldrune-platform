"""Rights-gated source/reference pair construction for Face training."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .face_dataset import DatasetSplit, IdentityRecord
from .face_training_bundle import FaceTrainingBundle


@dataclass(frozen=True)
class FaceCapturePair:
    source_identity: IdentityRecord
    source_capture_id: str
    source_path: Path
    reference_capture_id: str
    reference_path: Path

    def validate(self) -> None:
        if self.source_identity.split is not DatasetSplit.TRAIN:
            raise ValueError("Face training pairs must use the training split")
        captures = set(self.source_identity.capture_ids)
        if self.source_capture_id not in captures or self.reference_capture_id not in captures:
            raise ValueError("pair capture is not admitted for this identity")
        if self.source_capture_id == self.reference_capture_id:
            raise ValueError("source and reference captures must be distinct")


def build_identity_pairs(bundle: FaceTrainingBundle) -> tuple[FaceCapturePair, ...]:
    bundle.validate()
    pairs: list[FaceCapturePair] = []
    for identity in bundle.records:
        if identity.split is not DatasetSplit.TRAIN or len(identity.capture_ids) < 2:
            continue
        captures = identity.capture_ids
        for index, source_id in enumerate(captures):
            reference_id = captures[(index + 1) % len(captures)]
            pair = FaceCapturePair(
                identity,
                source_id,
                bundle.capture_paths[source_id],
                reference_id,
                bundle.capture_paths[reference_id],
            )
            pair.validate()
            pairs.append(pair)
    if not pairs:
        raise ValueError("training requires identities with at least two admitted captures")
    return tuple(pairs)
