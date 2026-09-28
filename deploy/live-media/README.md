# Live Media deployment

Control/signaling nodes can run on standard cloud compute. The WebRTC gateway
must run on a host that supports WebRTC ICE media traffic and outbound access to
the configured STUN/TURN servers. Media inference workers require CUDA-capable
GPU instances.

## Gateway image

The `Build LiveShell WebRTC gateway image` workflow builds
`Dockerfile.webrtc-gateway` on pull requests without publishing. A push to
`main` publishes these GHCR tags:

- `ghcr.io/seldrune-platform/seldrune-liveshell-webrtc-gateway:latest`
- `ghcr.io/seldrune-platform/seldrune-liveshell-webrtc-gateway:sha-<commit>`

The GHCR package is private by default. Configure a package-read credential on
the target host and deploy the immutable `sha-<commit>` tag. The gateway image
contains no model weights, identity media, or runtime secrets.

Run one gateway instance because session routing state is held in process
memory. Configure the required environment variables listed in
[`services/live_media/README.md`](../../services/live_media/README.md),
including the trusted profile authorizer, API and worker tokens, ticket secret,
worker DNS/TLS identity, and ICE servers. Do not use an allow-all profile
authorizer. Wait for `/readyz` to report ready before connecting the API.
`/healthz` only confirms that the process responds.

The browser currently supplies a STUN server. TURN credentials and browser-side
TURN relay configuration remain required for restrictive NATs and reliable
mobile connectivity. Do not claim universal connectivity until that path is
configured and tested.

## Production topology

1. Regional signaling/API service.
2. Regional TURN/STUN and WebRTC media ingress/egress.
3. Warm GPU worker pool with models resident in VRAM.
4. Session/cache service for ephemeral routing state.
5. Durable audit/consent metadata store.
6. Metrics/traces/log aggregation.

Autoscale on active sessions, GPU utilization, VRAM headroom, queue depth and
p95 inference latency. Never place long-lived identity media in ephemeral
routing state. Encrypt transport and storage; use short-lived credentials.
