# Cloud GPU OS control plane

Node 24 / Express orchestrator for RunPod workstations selected from the account.
This service is independent of the existing Python `backend/app` platform.
Run exactly **one instance**: the lifecycle lock and login limiter are local to
the process. Horizontal replicas require a shared transactional lease and limiter.

## Run locally

```sh
cd backend
npm ci
cp .env.example .env
# Securely fill HOST_PASSWORD, JWT_SECRET and RUNPOD_API_KEY.
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

Expose the desktop service as HTTP port **3000** by default, with a
browser-compatible desktop streamer such as a properly configured
Selkies/webtop image. Set `RUNPOD_POD_ID=auto` to discover Pods in the RunPod
account after host login. A single Pod opens automatically; with multiple Pods,
the app asks which one to open. The selected Pod is resumed if stopped. The
control plane does not create, reset, migrate, or install software on Pods.
For a Kasm desktop exposed on port **6901**, set `STREAM_PORT=6901`; ports must
be integers from 1 to 65535.

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
| POST | `/api/login` | `{ "username": "admin", "password": "…", "podId": "optional" }` | Discover Pods; ask for a selection if multiple, then resume the selected Pod and return `token`, `podId`, `streamUrl` |
| GET | `/api/status` | bearer token | Desired state, observed container runtime, stream health, uptime, all GPU telemetry and first-GPU summary |
| POST | `/api/heartbeat` | bearer token, `{}` | Renew lease; only this endpoint and a successful login renew activity |
| POST | `/api/shutdown` | bearer token, `{}` | `podStop` acknowledgement, then revoke the session |

The stream URL is `https://<selected-pod-id>-<STREAM_PORT>.proxy.runpod.net`.
Login and status return the configured `streamPort`. The mobile client validates
the exact pod and port; it does not allow arbitrary stream domains.
JWT sessions are scoped to the selected Pod and stream port, so changing either
revokes old clients' access and heartbeat renewal.
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
Password verification derives 64-byte scrypt keys with a random process-local
salt (N=32768, r=8, p=1) and compares them in constant time. The configured
password remains a server-side environment secret.
Native clients send no Origin. Browser clients require an exact HTTPS origin
in `ALLOWED_ORIGINS` (comma-separated); CORS is not authentication.

## Pod shutdown and recovery

Automatic idle shutdown is **disabled by default**. Locking or closing the app
does not stop a Pod. The user can explicitly shut down the selected Pod from
the app's Start menu. Set `AUTO_STOP_IDLE=true` only when unattended shutdown is
intended.

Each selected Pod gets a separate lease file derived from `STATE_FILE`, containing
the Pod identity, epoch, activity flag and timestamp but no credentials. Store it
on persistent disk. Old lease files are left intact when selecting another Pod.
Run exactly one service instance; multiple readers/writers are unsupported.

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
It discovers Pods from the configured RunPod account, uses port `6901` for the
Kasm desktop stream, and disables automatic idle shutdown.
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
