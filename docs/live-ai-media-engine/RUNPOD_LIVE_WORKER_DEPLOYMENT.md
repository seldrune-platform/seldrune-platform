# RunPod LiveShell worker deployment

This image packages the authenticated audio/video worker entrypoint from
`services.live_media.runpod_live_worker`. It uses the CUDA-enabled PyTorch 2.8
RunPod base image and listens on TLS TCP port 8765. The existing
`seldrune-faceswap-worker` image remains the separate HTTP worker for uploaded
jobs; it does not implement this live media protocol.

## Build and publish

From the repository root:

```sh
docker build -f services/live_media/Dockerfile.runpod-live \
  -t ghcr.io/seldrune-platform/seldrune-liveshell-worker:local .
```

The `Build LiveShell RunPod worker image` workflow builds the image on pull
requests without publishing it. A push to `main` publishes
`ghcr.io/seldrune-platform/seldrune-liveshell-worker:latest` and an immutable
`sha-<commit>` tag to GHCR. Configure RunPod's container registry credentials
for that private package, then select the immutable SHA tag for a pod.

## Pod and adapter setup

Use a supported CUDA GPU and expose TCP port 8765. The gateway connects to the
worker's DNS name using TLS and verifies the certificate hostname. Keep the pod
stopped when no session needs it.

The live image now installs the pinned FaceFusion revision already used by
Seldrune's uploaded-video worker and exposes the Apache-2.0 `ghost_1_256`
face-swap path through `services.live_media.facefusion_live_adapter`. The
built-in audio path is a 48 kHz same-speaker voice-style transform; it does not
clone another person's voice. Final video is visibly labeled before its quality
evaluator runs.

Keep profile media outside the image on a private RunPod volume mounted at
`/workspace/seldrune-live-profiles`. Do not put model credentials, private
keys, consent documents, or profile media in the image or Git history.

The worker must receive these settings through the RunPod secret/environment
configuration:

| Setting | Required value |
| --- | --- |
| `SELDRUNE_LIVE_WORKER_TOKEN` | Strong service token shared with the gateway |
| `SELDRUNE_LIVE_TICKET_SECRET` | Strong ticket-signing secret shared with the gateway |
| `SELDRUNE_FACE_TRANSFORM_ADAPTER` | Import path in `module:async_callable` form |
| `SELDRUNE_VOICE_TRANSFORM_ADAPTER` | Import path in `module:async_callable` form |
| `SELDRUNE_SYNTHETIC_VIDEO_LABELER` | Compatibility-named fail-closed disclosure validator in `module:async_callable` form; it must not alter pixels |
| `SELDRUNE_FACE_QUALITY_EVALUATOR` | Post-label face evaluator in `module:async_callable` form |
| `SELDRUNE_VOICE_QUALITY_EVALUATOR` | Final-audio evaluator in `module:async_callable` form |
| `SELDRUNE_LIVE_REALISM_POLICY_JSON` | Calibrated evaluator policy with pass thresholds |
| `SELDRUNE_LIVE_TLS_CERT` | Path to the worker TLS certificate |
| `SELDRUNE_LIVE_TLS_KEY` | Path to the matching private key |

For the built-in adapters, use:

```text
SELDRUNE_FACE_TRANSFORM_ADAPTER=services.live_media.facefusion_live_adapter:transform_face
SELDRUNE_VOICE_TRANSFORM_ADAPTER=services.live_media.voice_style_adapter:transform_voice
SELDRUNE_SYNTHETIC_VIDEO_LABELER=services.live_media.synthetic_video_labeler:label_jpeg
SELDRUNE_FACE_QUALITY_EVALUATOR=services.live_media.live_quality_evaluators:evaluate_face
SELDRUNE_VOICE_QUALITY_EVALUATOR=services.live_media.live_quality_evaluators:evaluate_voice
```

Each authorized profile is provisioned as a directory named by its opaque
profile ID. A face profile contains `face.jpg` (or jpeg/png/webp). A voice
style profile contains `voice-style.json` with only `gain_db`, `presence`,
and `warmth`; the adapter enforces bounded values and preserves 48 kHz sample
count and timing. The rolling evaluators report an explicit `warming` state
until 30 video frames and one second of audio have actually been observed; they
do not invent a full quality window on the first packet. Windows are isolated
by live session ID and profile, so each new call starts a fresh warmup.

The worker listens on `0.0.0.0:8765` by default. Set
`SELDRUNE_LIVE_WORKER_PORT` only when the pod and gateway are configured for
the same port. The gateway's `SELDRUNE_LIVE_WORKER_HOST`,
`SELDRUNE_LIVE_WORKER_TLS_NAME`, and `SELDRUNE_LIVE_WORKER_REGION` must point
to this pod and match its certificate.

Startup intentionally fails when any adapter, TLS file, token, ticket secret,
CUDA device, or calibrated policy is missing. A successful build or worker
handshake proves packaging and protocol readiness only; it is not a transformed
media or quality result. Do not claim live or HD readiness until an authorized
phone/desktop session returns measured transformed video and audio and passes
the configured evaluator gates.
