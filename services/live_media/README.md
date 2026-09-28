# Live Media service

The live media plane contains the RunPod worker protocol and an aiortc WebRTC gateway.
The gateway is a separate, single-instance service; the existing Seldrune API proxies
signaling requests to it and does not carry RTP media.

## WebRTC gateway

Build with `Dockerfile.webrtc-gateway`. The service exposes:

- `POST /v1/sessions`: authenticates the Seldrune API, authorizes both profiles,
  verifies explicit disclosure flags, creates a short-lived signed worker ticket,
  connects to the RunPod worker over hostname-validated TLS, and answers the SDP offer.
- `DELETE /v1/sessions/{session_id}`: closes a session only for its organization and user.
- `GET /healthz` and `GET /readyz`: process health and configuration readiness.

Configure these gateway environment variables:

| Variable | Purpose |
| --- | --- |
| `SELDRUNE_LIVESHIFT_WORKER_TOKEN` | Shared secret with the Seldrune API's gateway client; use at least 32 random bytes. |
| `SELDRUNE_PROFILE_AUTHORIZER` | Trusted `module:function` adapter returning `ProfileAuthorization(face_profile_authorized=True, voice_profile_authorized=True)` only when both IDs belong to the user and organization. |
| `SELDRUNE_LIVE_WORKER_TOKEN` | Separate service secret shared with the RunPod live worker. |
| `SELDRUNE_LIVE_TICKET_SECRET` | At least 32 random bytes shared with the RunPod worker for single-session tickets. |
| `SELDRUNE_LIVE_WORKER_HOST` | Private or public DNS name for the worker's TLS TCP listener. |
| `SELDRUNE_LIVE_WORKER_PORT` | Worker TCP port (default 8765). |
| `SELDRUNE_LIVE_WORKER_TLS_NAME` | Expected certificate hostname; defaults to the worker host. |
| `SELDRUNE_LIVE_WORKER_REGION` | Worker region label bound to the session. |
| `SELDRUNE_LIVE_ICE_SERVERS_JSON` | Optional JSON array of STUN/TURN entries. TURN credentials are used by the gateway only. |
| `SELDRUNE_LIVE_MAX_SESSIONS` | Local session capacity (default 1). |
| `SELDRUNE_LIVE_MAX_INFLIGHT` | Shared audio/video worker requests (1 or 2; default 2). |
| `SELDRUNE_LIVE_SESSION_TTL_SECONDS` | Session cleanup lifetime (default 3600). |

The profile authorizer is deliberately mandatory. This repository does not provide a
profile database adapter, so the gateway remains unready until the deployment supplies
one. Do not set an allow-all authorizer.

Run this service on a host that supports WebRTC ICE media traffic and outbound
connectivity to the configured STUN/TURN servers. The browser currently supplies a
STUN server; browser-side TURN credentials and restrictive-NAT fallback still need
wiring before claiming universal mobile connectivity. Keep this service to one
instance while session state is in memory.

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
