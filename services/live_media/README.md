# Live Media service

The live media plane contains the RunPod worker protocol and an aiortc WebRTC gateway.
The gateway is a separate, single-instance service; the existing Seldrune API proxies
signaling requests to it and does not carry RTP media.

## WebRTC gateway

Build with `Dockerfile.webrtc-gateway`. The service exposes:

- `POST /v1/sessions`: authenticates the Seldrune API, authorizes both profiles,
  verifies explicit disclosure flags, creates a short-lived signed worker ticket,
  connects to the RunPod worker over hostname-validated TLS, and answers the SDP offer.
- `GET /v1/ice-servers`: authenticates the Seldrune API and returns STUN plus
  short-lived Coturn credentials for the browser. Responses are not cacheable.
- `DELETE /v1/sessions/{session_id}`: closes a session only for its organization and user.
- `GET /healthz` and `GET /readyz`: process health and configuration readiness.

Configure these gateway environment variables:

| Variable | Purpose |
| --- | --- |
| `SELDRUNE_LIVESHIFT_WORKER_TOKEN` | Shared secret with the Seldrune API's gateway client; use at least 32 random bytes. |
| `SELDRUNE_PROFILE_AUTHORIZER` | Use `services.live_media.seldrune_profile_authorizer:authorize_profiles` to check Seldrune's reviewed registry, or inject another trusted adapter. |
| `SELDRUNE_PROFILE_AUTHORIZATION_URL` | HTTPS or private-network base URL for the Seldrune API. |
| `SELDRUNE_PROFILE_AUTHORIZATION_TOKEN` | At least 32 random bytes; must match the backend's `SELDRUNE_LIVE_PROFILE_AUTHORIZER_TOKEN`. |
| `SELDRUNE_LIVE_WORKER_TOKEN` | Separate service secret shared with the RunPod live worker. |
| `SELDRUNE_LIVE_TICKET_SECRET` | At least 32 random bytes shared with the RunPod worker for single-session tickets. |
| `SELDRUNE_LIVE_WORKER_HOST` | Private or public DNS name for the worker's TLS TCP listener. |
| `SELDRUNE_LIVE_WORKER_PORT` | Worker TCP port (default 8765). |
| `SELDRUNE_LIVE_WORKER_TLS_NAME` | Expected certificate hostname; defaults to the worker host. |
| `SELDRUNE_LIVE_WORKER_REGION` | Worker region label bound to the session. |
| `SELDRUNE_LIVE_ICE_SERVERS_JSON` | Optional JSON array of STUN entries and gateway-only static ICE entries. Do not put static TURN entries here when dynamic TURN is enabled. |
| `SELDRUNE_LIVE_TURN_URLS_JSON` | Optional JSON array of `turn:` or `turns:` relay URLs for Coturn REST authentication. |
| `SELDRUNE_LIVE_TURN_SHARED_SECRET` | Coturn `static-auth-secret`; at least 32 random bytes. It stays inside the gateway. |
| `SELDRUNE_LIVE_TURN_CREDENTIAL_TTL_SECONDS` | Lifetime of generated browser and gateway credentials (default 3900); must exceed the configured session lifetime by at least 300 seconds and may be at most 86700. |
| `SELDRUNE_LIVE_MAX_SESSIONS` | Local session capacity (default 1). |
| `SELDRUNE_LIVE_MAX_INFLIGHT` | Shared audio/video worker requests (1 or 2; default 2). |
| `SELDRUNE_LIVE_SESSION_TTL_SECONDS` | Session cleanup lifetime (default 3600). |

The gateway profile check remains mandatory. This repository provides a Seldrune-backed
registry at `/liveshell/profiles`: users submit an opaque profile ID, an evidence reference,
a SHA-256 digest, and an expiry. An organization owner or admin must review the referenced
consent record and approve from a different account than the requester. The registry stores
only the reference and digest, not raw face or voice media. Configure the built-in adapter
and matching service tokens in the gateway and backend. The per-session consent and
synthetic-media disclosure checks remain separate. Do not set an allow-all authorizer.

The authenticated Seldrune API proxies `/v1/ice-servers` to the gateway and returns
only derived, expiring browser credentials with `Cache-Control: no-store`. Configure
TURN URLs and the shared secret together; the generated credential lifetime must exceed
the gateway session lifetime by five minutes. Set Coturn's `static-auth-secret` to the same
server-side value. A real Coturn relay still needs to be provisioned and tested from
the target mobile networks before claiming universal connectivity. Keep this service
to one instance while session state is in memory. A WebRTC peer that stays
disconnected for 15 seconds releases its gateway and GPU worker session; a
reconnection within that window preserves the call. Failed or closed peers
release immediately. The browser uses the same grace window and stops local
camera and microphone capture when the connection does not return.

## RunPod worker wire format

The WebRTC gateway sends raw media bytes through the authenticated worker protocol:

- Video input/output: JPEG encoded from RGB with width, height, pixel format and
  frame-rate metadata attached to each worker request. This keeps 1080p traffic within
  the bounded worker payload contract.
- Audio input/output: packed little-endian signed 16-bit PCM at 48 kHz, mono or stereo;
  sample rate and channel count accompany each request.

Face and voice adapter functions may accept `(payload, profile_id, metadata)` or a
`metadata=`/`media_metadata=` keyword. Two-argument adapters remain supported, but
cannot use orientation or channel metadata. Output buffers must use the same wire formats; video output dimensions must match the
returned worker metadata.

Worker readiness requires strict realism evidence and reports the CUDA device profile
read from PyTorch. The gateway rejects a worker if its reported accelerator differs
from the requested profile. Realism evidence must come from an actual output evaluator;
this service does not claim HD quality, FPS, voice similarity, latency or production
readiness from signaling alone.

Install only the media dependencies with the gateway Dockerfile. The normal Seldrune
API image remains independent of aiortc.
