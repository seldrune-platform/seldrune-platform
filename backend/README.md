# Cloud GPU OS control plane

Node 24 / Express orchestrator for one dedicated, single-GPU RunPod workstation.
This service is independent of the existing Python `backend/app` platform.
Run exactly **one instance**: the lifecycle lock and login limiter are local to
the process. Horizontal replicas require a shared transactional lease and limiter.

## Run locally

```sh
cd backend
npm ci
cp .env.example .env
# Securely fill HOST_PASSWORD, JWT_SECRET, RUNPOD_API_KEY and RUNPOD_POD_ID.
npm run dev
```

Use a unique host password (12+ characters) and a random JWT key (32+ bytes).
For example, generate the JWT key with `openssl rand -hex 32`, then store it
securely. No default password or signing secret is accepted. The server listens
on port 10000 unless `PORT` is set. For mobile development, provide an HTTPS
endpoint with a valid certificate; the app deliberately refuses HTTP URLs.

Keep TLS verification and inherited proxy settings enabled. `npm start` enables
Node 24's environment proxy support for managed execution environments.

## Configure the workstation

Create/select a dedicated single-GPU RunPod pod, expose its desktop service as
HTTP port **3000**, and install a browser-compatible desktop streamer, such as
a properly configured Selkies/webtop image. Store the exact pod ID on Render.
The control plane resumes existing pods; it does not create, reset, migrate,
install software on, or terminate them. RunPod capacity must be available to resume.

**Secure the desktop streamer separately.** The RunPod HTTPS proxy URL can be
reached directly. The orchestrator JWT protects control endpoints, not this
stream. Configure the stream image's supported authentication before exposing
it. The app allows its login screen to appear when the health check receives
401/403. Do not embed stream credentials in the URL, injection script, or Expo
public variables. TLS on the proxy does not replace desktop authentication.

Container `runtime` is RunPod's observed runtime, not an in-container agent
health check. Stream health is a bounded HTTP HEAD check: only a 2xx response
is marked ready; redirects, 401, 403, 5xx and timeouts are not. A successful HEAD
does not prove that video/audio decode or remote input works on a phone. Images
which reject HEAD need an appropriate health endpoint/proxy configuration.

## HTTP contract

All bodies are JSON. Except for login and health, endpoints require
`Authorization: Bearer <token>`. API responses use `Cache-Control: no-store`.

| Method | Path | Request | Result |
| --- | --- | --- | --- |
| GET | `/healthz` | none | Local process health; no upstream requests |
| POST | `/api/login` | `{ "username": "admin", "password": "…" }` | Resume stopped pod; return `token`, `podId`, `streamUrl`, `expiresIn`, heartbeat/idle timing |
| GET | `/api/status` | bearer token | Desired state, observed container runtime, stream health, uptime, all GPU telemetry and first-GPU summary |
| POST | `/api/heartbeat` | bearer token, `{}` | Renew lease; only this endpoint and a successful login renew activity |
| POST | `/api/shutdown` | bearer token, `{}` | `podStop` acknowledgement, then revoke the session |

The stream URL is always `https://<RUNPOD_POD_ID>-3000.proxy.runpod.net`.
Telemetry percentages are clamped to 0–100; missing telemetry is `null`, not
fabricated zero. `memoryUtilPercent` is displayed as VRAM utilization, not MiB.
Errors are JSON: 401 for invalid/expired sessions, 429 for throttling, 400/413
for invalid bodies, 502 for provider/storage failures. Provider diagnostics and
credentials are never returned to clients. Upstream requests have timeouts;
mutations are not blindly retried after ambiguous delivery.

Login issues a 12-hour HS256 JWT with issuer/audience checks. Only the latest
login session remains valid. Shutdown or idle stop revokes it. The phone keeps
the token in memory; reopening the app requires login again. Host credentials
and JWT key rotation revoke access; rotate the JWT key after a suspected leak.
Native clients send no Origin. Browser clients require an exact HTTPS origin
in `ALLOWED_ORIGINS` (comma-separated); CORS is not authentication.

## Idle shutdown and recovery

A watchdog checks every **60 seconds**. At **300 seconds** without a login or
heartbeat it requests `podStop`. Status polling does not keep a GPU alive.
Typical stop initiation is 300–360 seconds after the last heartbeat; provider
failures can delay it. Failed stops remain eligible for the next tick.

The lease (pod identity, epoch, activity flag and timestamp; no credentials) is
atomically saved to `STATE_FILE`. Store it on persistent disk. The watchdog
reconciles an already-running configured pod even after process restart, so
this must be a dedicated workstation, not a shared pod controlled elsewhere.
An invalid/cross-pod lease fails startup; inspect/archive the file before changing
pod identity. Multiple readers/writers and shared-file replicas are unsupported.

The server cannot stop GPUs while Render is unavailable or suspended. Use the
paid always-on Blueprint plan, an independent billing alert, and RunPod-side
limits/automation as appropriate. Stopping retains the pod and may retain billable
storage; a successful API acknowledgement is not a guarantee of zero charges or
immediate physical shutdown. Check RunPod's console for final billing/state.

## Render Blueprint and deployment

Create a Render Blueprint from this repository and set **Blueprint Path** to
`backend/render.yaml`; the root `render.yaml` continues to deploy the Python
platform. This Blueprint uses a Starter service and 1 GB persistent disk (paid),
one replica, Node 24, frozen `npm ci`, `/healthz`, and manual/CI deployment.
Enter host and RunPod credentials in Render's secure environment settings;
`JWT_SECRET` is generated by Render. The disk backs `STATE_FILE` at `/var/data`.

The GitHub workflow validates both packages for PRs and main. For automatic
deployment after merging, put the Render service deploy hook in the GitHub
**production** environment secret `RENDER_DEPLOY_WEBHOOK_URL`. Configure any
required environment reviewers there. The deploy job sends only validated main
commits and never runs for PRs. A successful hook request means deployment was
accepted; inspect Render's rollout/health before considering it released.

```sh
npm test
npm run check
npm audit --omit=dev --audit-level=high
```

Tests exercise HTTP endpoints with injected RunPod/stream adapters and an
adjustable clock. They never start or stop a paid pod.
