# LiveShell mobile client and GPU gateway

## What this change adds

The Seldrune owner can open the Media Console at /media (/liveshell/mobile remains an alias), preview a phone camera and microphone, choose a 720p or 1080p capture target, select a supported GPU target, and negotiate a WebRTC session through Seldrune's authenticated API. Camera switching is supported on mobile browsers.

Seldrune proxies only WebRTC signaling. When a gateway is configured, camera and microphone media flow directly between the browser and the GPU gateway. The mobile page keeps a visible synthetic-media badge on transformed output. A worker must independently confirm that both submitted profiles are authorized and that its synthetic-media indicator is enabled; the API rejects a response that omits any of those confirmations.

The page distinguishes requested settings from returned measurements. Compatible same-origin Seldrune web apps can load /console-assets/seldrune-media.js to request the same approved, labeled camera and microphone stream by default. The app-cloning code does not currently inject this client automatically, so a cloned app's entry page must include it. Merely configuring a gateway does not mark HD output or production readiness as verified.

## GPU profile targets

The RTX 4090 is the baseline target requested by the owner. Its 24 GB memory capacity is suitable for an initial single-session profile subject to the selected models fitting in VRAM and passing real-device benchmarks. The RTX 5090 target provides 32 GB and additional compute headroom. These hardware specifications do not establish throughput for Seldrune's face and voice models.

The existing 720p30 baseline and 1080p30 performance tier remain targets. Production claims still require measured mobile video frames, 48 kHz audio, synchronized A/V, and the existing latency and consent evidence gates.

## Deployment configuration

Configure these server-side environment variables on Seldrune:

- SELDRUNE_LIVESHIFT_WORKER_URL: HTTPS URL for the cloud GPU gateway; HTTP is allowed only for localhost or private .internal service networking.
- SELDRUNE_LIVESHIFT_WORKER_TOKEN: secret bearer token used only by the Seldrune API when calling the gateway.

Do not put the worker token in browser JavaScript or in Git. The page remains preview-only when either value is missing.

## Gateway contract

Seldrune sends an authenticated POST /v1/sessions request with:

- organization_id and user_id, used to bind the session to its owner;
- a complete WebRTC offer;
- face and voice profile IDs;
- consent and synthetic-media indicator flags;
- requested video resolution, 48 kHz audio target, and GPU target profile.

The gateway returns JSON with session_id, answer containing type=answer and SDP, the matching face and voice profile IDs, face_profile_authorized=true, voice_profile_authorized=true, synthetic_media_indicator_enabled=true, and optionally the actual accelerator and returned width, height, and audio sample rate. Only then does the browser apply the answer.

Seldrune closes sessions with DELETE /v1/sessions/{session_id} and the original organization_id and user_id query values. The GPU gateway must authenticate Seldrune's bearer token, bind every session to both IDs, expire abandoned sessions, and reject profile IDs it cannot verify. Configure STUN/TURN on the gateway for mobile and carrier NAT traversal; the current browser proof includes a STUN server, not a production TURN service.

## Remaining production work

The gateway endpoint and GPU runtime must be deployed separately and configured before the live start button becomes available. A real compatible face model and streaming voice model must be loaded on the worker, with rights and authorization checked for every profile. The current repository provides the LiveShell processor contracts but does not include a production voice-conversion model or a running GPU session gateway. The mobile page therefore does not claim that a face or voice transformation is complete.

Run the phone proof on an RTX 4090 first. Record returned video dimensions and frame rate, 48 kHz audio, A/V drift, client p95 latency, GPU inference latency, model hashes, profile authorization, and synthetic-media indicator verification. Promote 1080p or RTX 5090 profiles only from measured results.
