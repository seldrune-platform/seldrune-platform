# RunPod live-call bridge

## Status

The deployed RTX 4090 FaceSwap worker is an authenticated **uploaded-video job** service. Its current routes are `/health` and `/v1/jobs`; it does not accept live sessions or camera frames. The Seldrune mobile LiveShell page already has a WebRTC offer flow, but it forwards to a separate `SELDRUNE_LIVESHIFT_WORKER_URL` / `SELDRUNE_LIVESHIFT_WORKER_TOKEN` gateway. The FaceSwap job worker settings do not provide that gateway.

The existing worker must therefore remain the batch-video path until a streaming worker is built, tested, and deliberately deployed. Do not advertise live calls as connected just because the batch worker reports ready.

## Supported call path

For desktop Teams, Zoom, or another meeting client with normal camera selection:

1. The signed-in Seldrune owner console checks organization permission, face-use consent, and an authorized identity profile. It issues a short-lived session ticket bound to that user, organization, and profile. The long-lived worker token stays on the server.
2. A Seldrune desktop companion captures camera frames and sends them to the live GPU worker over an authenticated, encrypted, long-lived TCP connection. Frame sequence numbers and a bounded latest-frame queue prevent stale frames from accumulating.
3. The worker returns processed frames with a persistent, visible `AI-SYNTHETIC` label in the outgoing image. The companion exposes the returned image as a supported OS virtual camera. The user chooses that camera in Teams or Zoom's regular device settings.
4. Meeting microphone audio stays local and unmodified for this face-only milestone. Do not upload microphone audio or apply voice conversion.

A browser-only mobile page cannot register a system camera device for the native Android Teams or Zoom app. On phones, the initial supported option is a disclosed Seldrune browser Live Room. Native mobile-call camera integration needs a separately supported OS or conferencing API.

## RunPod transport constraint

RunPod documents a 100-second maximum connection time for HTTP proxy requests, no UDP connections for Pods, and recommends direct TCP exposure for long-lived WebSocket or non-HTTP traffic. The current port 8000 HTTPS proxy is suitable for the existing short control/job requests, not as the permanent media stream.

The live worker should use a separately configured TCP stream port with TLS, strict session authentication, per-session limits, and connection cleanup. Keep HTTPS port 8000 for control, job status, and health. Do not depend on WebRTC's usual UDP media path on a RunPod Pod.

References:

- [RunPod: Expose ports](https://docs.runpod.io/pods/configuration/expose-ports)
- [Zoom: System requirements](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060748)
- [Microsoft Teams: Manage call settings](https://support.microsoft.com/en-us/teams/calls-devices/manage-your-call-settings-in-microsoft-teams)

## Deployment boundary

The active RTX 4090 Pod is currently serving the batch worker on HTTP port 8000. Adding a streaming service requires a new worker image and an exposed TCP port. Keep the existing running Pod and its current port/image configuration intact while that image, client, and network path are being built and tested. Schedule any Pod reconfiguration only after the replacement is ready; a port reset can change the assigned public TCP mapping.

Do not set `SELDRUNE_LIVESHIFT_WORKER_URL` to the existing FaceSwap HTTP endpoint: the API shapes and transport are different, and that would report a configured gateway without providing live media.

## Acceptance checks before enabling calls

- Face-only flow does not request a voice profile or send microphone audio to the worker.
- Missing consent, expired tickets, wrong organization/user/profile, or a disabled disclosure indicator reject session creation.
- Frames are authenticated, encrypted in transit, bounded to supported dimensions/rate, timestamped, and processed with bounded backpressure.
- Every returned frame carries the visible synthetic-media label; the client has a clear stop control and releases the camera promptly.
- Disconnects, network loss, worker restart, and GPU overload recover without replaying stale frames or leaving sessions active.
- GPU tests report sustained frame rate, end-to-end frame latency percentiles, resolution, and reconnect behavior from a real authorized camera stream. HD readiness is not claimed until those measurements pass.
- The returned virtual camera appears in the desktop OS and can be selected in a Teams or Zoom preview/test call using the application's normal device selector.

Unit tests with a mock transform can validate framing, consent, cleanup, and backpressure. They are not evidence of working GPU inference or a usable live meeting call.
