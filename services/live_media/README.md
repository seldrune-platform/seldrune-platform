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
| `SELDRUNE_LIVE_TURN_PROVIDER` | `coturn` (default) or `cloudflare`. Cloudflare issues short-lived credentials from the gateway. |
| `SELDRUNE_LIVE_GATEWAY_TURN_TRANSPORT` | `provider` (default), `udp`, or `tcp`. Restrict gateway-side TURN selection when the host cannot use UDP; browser ICE still receives the provider's full URL list. |
| `SELDRUNE_LIVE_TURN_URLS_JSON` | Coturn only: JSON array of `turn:` or `turns:` relay URLs. |
| `SELDRUNE_LIVE_TURN_SHARED_SECRET` | Coturn only: `static-auth-secret`; at least 32 random bytes. It stays inside the gateway. |
| `SELDRUNE_CLOUDFLARE_TURN_KEY_ID` | Cloudflare only: 32-character TURN key ID. |
| `SELDRUNE_CLOUDFLARE_TURN_API_TOKEN` | Cloudflare only: server-side TURN key token. Never send it to browser code or logs. |
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

## RunPod Pod deployment settings

The live worker is a long-running Pod service on TCP port 8765. Use a RunPod API key
only from the operator or deployment environment for creating/managing the Pod; the
key is not a Pod runtime variable and must not be placed in the image or worker secrets.

In RunPod **Credentials → Secrets**, create these entries. RunPod requires names to
start with `RUNPOD_SECRET_`; the worker resolves that prefix automatically:

| RunPod secret name | Value |
| --- | --- |
| `RUNPOD_SECRET_SELDRUNE_LIVE_WORKER_TOKEN` | At least 32 random bytes; must match the gateway's `SELDRUNE_LIVE_WORKER_TOKEN`. |
| `RUNPOD_SECRET_SELDRUNE_LIVE_TICKET_SECRET` | At least 32 random bytes; must match the gateway's `SELDRUNE_LIVE_TICKET_SECRET`. |
| `RUNPOD_SECRET_SELDRUNE_LIVE_TLS_CERT` | TLS certificate chain PEM for the worker hostname. |
| `RUNPOD_SECRET_SELDRUNE_LIVE_TLS_KEY` | Matching unencrypted private-key PEM. |

Inline TLS PEM is loaded through an anonymous in-memory file; alternatively, set the
unprefixed `SELDRUNE_LIVE_TLS_CERT` and `SELDRUNE_LIVE_TLS_KEY` variables to mounted
certificate file paths. The certificate hostname must match the gateway's
`SELDRUNE_LIVE_WORKER_TLS_NAME`.

Set these non-secret Pod environment values to the import paths and policy supplied by
the deployment:

- `SELDRUNE_FACE_TRANSFORM_ADAPTER`
- `SELDRUNE_VOICE_TRANSFORM_ADAPTER`
- `SELDRUNE_SYNTHETIC_VIDEO_LABELER`
- `SELDRUNE_FACE_QUALITY_EVALUATOR`
- `SELDRUNE_VOICE_QUALITY_EVALUATOR`
- `SELDRUNE_LIVE_REALISM_POLICY_JSON`
- `SELDRUNE_LIVE_WORKER_HOST=0.0.0.0`
- `SELDRUNE_LIVE_WORKER_PORT=8765`

Adapter and evaluator values must resolve to installed async callables, and the
transform adapter modules must each expose an async `prepare_profile` function.
Mount reviewed private profile media at `/workspace/seldrune-live-profiles`; do not
put profile media in the image. Expose the worker's TCP port 8765 to the gateway,
use a certificate valid for the exposed hostname, and provision an accelerator that
the worker recognizes before enabling live sessions.

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
from the requested profile. Realism evidence must come from an actual output evaluator.
The worker disclosure stage validates the transformed JPEG and disclosure configuration,
while the participant-visible marker is rendered exactly once at the WebRTC gateway's
final outbound video boundary. This service does not claim HD quality, FPS, voice
similarity, latency or production readiness from signaling alone.

Install only the media dependencies with the gateway Dockerfile. The normal Seldrune
API image remains independent of aiortc.

## Voice styling

`voice_style_adapter.py` supports bounded live PCM styling and per-profile
`pitch_semitones` controls from -8 to +8. Its streaming pitch shifter is adapted
from the locally available MIT-licensed OpenVoiceChanger source; see
`OPENVOICECHANGER-LICENSE`. This is a same-speaker effect and does not synthesize
or imitate a different enrolled speaker. Set the value in the private
`voice-style.json` for that approved profile.


## Change the visible disclosure wording

The final participant-visible marker is rendered by `output_marker.py`; its wording
is kept in `synthetic_disclosure.py`. The worker-side
`synthetic_video_labeler.py` validates the transformed JPEG and disclosure
configuration without adding a second badge. To change the wording, edit
`VISIBLE_DISCLOSURE_LABEL` and choose one of these clear labels:
`AI MODIFIED`, `AI-ALTERED VIDEO`, or `SYNTHETIC MEDIA`.

Blank text and wording that does not identify altered or synthetic media are
rejected, so the worker cannot start with an empty or misleading label. There is
no disable setting. Session consent and profile authorization remain separate
required checks. Verify changes with
`pytest -q tests/test_synthetic_video_disclosure.py`.
