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
