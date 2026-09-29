"""Convert admitted source/reference pairs into trainable tensors."""

from __future__ import annotations

from .face_training_bundle import FaceTrainingBundle


def build_paired_batches(
    bundle: FaceTrainingBundle,
    *,
    input_size: int = 256,
) -> tuple:
    """Require a supervised cross-identity target before allocating tensors.

    The identity-pair manifest only links captures of the same subject. Its
    previous target=reference shortcut taught the model to copy the reference
    and cannot establish identity transfer.
    """
    bundle.validate()
    if input_size < 128 or input_size % 32:
        raise ValueError("input_size must be >=128 and divisible by 32")
    raise ValueError(
        "identity-transfer training requires source/reference/target capture "
        "provenance across admitted identities; same-subject pairs are insufficient"
    )
