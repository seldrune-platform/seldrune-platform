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
