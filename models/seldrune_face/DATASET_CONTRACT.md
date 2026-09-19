# Seldrune Face v0.1 — Rights-Cleared Dataset Contract

Status: **required before training**

Seldrune Face v0.1 may train only on identity data for which Seldrune has documented
rights and explicit authorization appropriate to the intended evaluation.

## Required record per identity

- `subject_id`: internal pseudonymous identifier; never use a person's name as the key.
- `consent_record`: immutable reference to the authorization/consent evidence.
- `rights_basis`: source and documented right to use the media for model training/evaluation.
- `capture_ids`: hashes or immutable IDs for every admitted image/video source.
- `allowed_purposes`: explicit permitted uses; v0.1 requires evaluation/training permission.
- `expires_at`: consent expiry when applicable.
- `revoked_at`: populated when authorization is withdrawn.
- `provenance`: acquisition source, ingestion time, and transformation history.

## Admission rules

Training ingestion MUST reject media when consent evidence is absent, rights are unclear,
the allowed purpose excludes training/evaluation, consent is expired/revoked, or source
provenance cannot be reconstructed.

Public availability alone is **not** a rights basis. Do not scrape faces merely because
they are accessible online. Third-party pretrained face-swap weights are not admitted
into Seldrune-owned checkpoints.

## Dataset splits

Identity subjects must not cross train/validation/test splits. Evaluation reports must
record the dataset manifest hash and checkpoint hash so results are reproducible.

## Removal

Revocation must block future training ingestion immediately. Affected checkpoints must be
traceable to their dataset manifest so retraining/remediation can be evaluated.

## First training gate

Before the first RTX PRO 6000 training run, produce:

1. a machine-readable manifest conforming to this contract;
2. a provenance/consent audit with zero rejected-rights exceptions;
3. deterministic train/validation/test subject splits;
4. manifest hash recorded with the experiment.

Until those artifacts exist, `face_model_loaded` and `first_frame_transformed` remain
false in LiveShift Mission Control.
