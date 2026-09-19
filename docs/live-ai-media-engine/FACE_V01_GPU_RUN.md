# Seldrune Face v0.1 GPU run gate

The GPU worker may train only from an admitted execution manifest and an explicit
rights-cleared training bundle. The bundle maps every immutable capture ID to a
local file and carries consent, provenance, purpose, split, expiry and revocation
metadata.

A successful run is not established by process exit alone. Success requires a
CUDA training result, at least one checkpoint, SHA-256 checkpoint evidence and a
validated GPU training receipt.

No dataset is bundled with the repository. Operators must supply captures for
which Seldrune has the required training rights and consent. Public availability
alone is not treated as permission.

## RTX PRO 6000 paired source/reference integration

The admitted worker path is now wired to the Seldrune-owned reference-image encoder and
reference-conditioned Face v0.1 model. The coordinator requires the
`rtx-pro-6000-blackwell` accelerator profile, builds source/reference batches from
rights-cleared captures of the same admitted identity, constructs the paired CUDA
runtime, and executes the paired training bridge under the execution manifest's
step/checkpoint/precision bounds.

This integration is a training-path gate, not evidence of a completed training run.
A real-output claim remains blocked until an RTX PRO 6000 run produces validated
trained checkpoint weights and a separate transformed-frame test verifies output
from those weights.

## Unified transformed-frame verification receipt

A real-output claim must now pass one receipt that binds ten gates to the same run:

1. a non-empty verification run identity;
2. a valid checkpoint-backed Face output manifest;
3. an ONNX artifact digest;
4. an inference model digest matching that ONNX artifact;
5. distinct input and output frame digests;
6. a rights-cleared reference-image digest;
7. measured identity similarity above the configured threshold;
8. bounded frame change and single-frame inference latency;
9. a continuous stream with the required transformed-frame ratio; and
10. verified identity authorization plus a verified synthetic-media indicator.

The receipt is a verification contract only. Default thresholds are policy defaults,
not evidence that any GPU run, checkpoint, ONNX export, frame transform, or live stream
has occurred.
