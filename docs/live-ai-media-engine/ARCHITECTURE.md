# Seldrune Live AI / Real-Time Media Engine

## Goal
Cloud-first, cross-platform real-time media transformation for authorized identities. Mobile phones and ordinary laptops act as thin clients; GPU-intensive inference runs on cloud workers.

## Pipeline
Client camera/mic -> WebRTC ingress -> session gateway -> consent/policy gate -> media router -> GPU scheduler -> face pipeline + voice pipeline -> A/V sync -> GPU encoder -> WebRTC egress -> supported conferencing/client integration.

## Components
- Client SDK: Web, Android, iOS, Windows/macOS companion.
- Session API: authenticated short-lived sessions, device capabilities, presets.
- WebRTC SFU/media gateway: ICE/STUN/TURN, adaptive bitrate, jitter buffers.
- GPU scheduler: warm workers, autoscaling, model residency, queue/backpressure.
- Face pipeline: detection, landmarks, tracking, authorized identity transform, blending, restoration, temporal consistency and color/lighting matching.
- Voice pipeline: VAD, denoise, authorized voice conversion, pitch/timbre controls, resampling and streaming synthesis.
- A/V synchronizer: timestamps, drift correction and bounded buffering.
- Safety: explicit enrollment/consent, revocation, audit trail, synthetic-media indicator/watermark policy, rate limits and abuse controls.
- Observability: latency/FPS/GPU/packet-loss metrics, traces and session health.

## Performance targets
Targets, not guarantees: 720p/30fps baseline; 1080p/30fps performance tier; adaptive degradation under network/GPU pressure. Minimize motion-to-photon and voice latency with regional GPU placement, persistent models, hardware encode/decode and WebRTC.

## Cross-platform
No discrete local GPU is required. Mobile and normal laptops capture/render locally while cloud workers perform expensive inference. Direct camera substitution in third-party mobile apps is platform/API dependent; use supported integrations rather than bypassing OS/app security.

## Deployment
Separate control plane from GPU media plane. Keep existing Seldrune services independent. Deploy GPU workers to a CUDA-capable provider; keep TURN/media nodes regionally close to users. Use Redis-compatible ephemeral session state and durable metadata/audit storage.

## Delivery phases
1. Contracts, session API, policy/consent, mock processors.
2. Browser WebRTC proof-of-concept.
3. GPU face worker.
4. Streaming voice worker and A/V sync.
5. Mobile/desktop clients.
6. Autoscaling, regional routing, observability, load/latency tests.
7. Supported conferencing integrations and production hardening.


## GPU target profiles

LiveShell uses the RTX 4090 as its baseline single-session target and the RTX
5090 as a higher-headroom target. NVIDIA specifications list 24 GB VRAM and
16,384 CUDA cores for the 4090, versus 32 GB VRAM and 21,760 CUDA cores for the
5090. Those specifications do not prove LiveShell throughput. Keep 720p30 as
the baseline target and enable 1080p30 only after measured phone-session
benchmarks pass.