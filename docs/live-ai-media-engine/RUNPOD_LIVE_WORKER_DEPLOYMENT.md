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

This base image deliberately contains no face/voice models or transform
adapters. Provide an audited adapter package and its dependencies in a derived
image, or mount importable adapter modules at `/opt/seldrune/adapters`. Model
weights should be stored outside the image and made available to those adapters
through a private mounted volume. Do not put model credentials, private keys,
consent documents, or profile media in the image or Git history.

The worker must receive these settings through the RunPod secret/environment
configuration:

| Setting | Required value |
| --- | --- |
| `SELDRUNE_LIVE_WORKER_TOKEN` | Strong service token shared with the gateway |
| `SELDRUNE_LIVE_TICKET_SECRET` | Strong ticket-signing secret shared with the gateway |
| `SELDRUNE_FACE_TRANSFORM_ADAPTER` | Import path in `module:async_callable` form |
| `SELDRUNE_VOICE_TRANSFORM_ADAPTER` | Import path in `module:async_callable` form |
| `SELDRUNE_SYNTHETIC_VIDEO_LABELER` | Import path in `module:async_callable` form |
| `SELDRUNE_LIVE_REALISM_POLICY_JSON` | Calibrated evaluator policy with pass thresholds |
| `SELDRUNE_LIVE_TLS_CERT` | Path to the worker TLS certificate |
| `SELDRUNE_LIVE_TLS_KEY` | Path to the matching private key |

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
