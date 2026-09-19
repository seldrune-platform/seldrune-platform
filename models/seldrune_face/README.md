# Seldrune-owned face model

This directory is reserved for a Seldrune-trained, provider-independent face model. No third-party pretrained face-swap weights are included.

## Evaluation path

1. Use only datasets and identity material Seldrune has the right to use.
2. Record dataset provenance and consent/authorization metadata.
3. Train Seldrune-owned weights from an independently implemented architecture or components whose licenses permit the intended use.
4. Export the resulting model through the existing LiveShift inference backend.
5. Benchmark first-frame and streaming latency on the RTX PRO 6000 worker.

The repository license in LICENSE-EVALUATION applies only to Seldrune-owned code/weights placed here. It cannot relicense third-party material.
