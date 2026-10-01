# Runpod owner tools

Seldrune's built-in `runpod` provider connects the Owner Console to Runpod REST API v2. It exposes four governed tools:

- `runpod-list-pods` and `runpod-get-pod` read Pod state.
- `runpod-start-pod` and `runpod-stop-pod` request a lifecycle transition.

The read tools return a small allowlist of Pod fields. They omit Pod environment variables, SSH connection details, registry credentials, and command arguments. Start and stop are high-risk actions and always require a separate Owner Console approval. Starting a Pod may incur GPU charges. There is no create, restart, reset, or terminate tool in this integration.

## Save the Runpod API key in the Owner Console

Send the key to the existing verified-provider credential API over HTTPS while authenticated as an organization member with tool-management permission:

```http
POST /api/v1/organizations/{organization_id}/tool-bootstrap/credentials/verified
Content-Type: application/json
Authorization: Bearer <seldrune_access_token>

{
  "provider": "runpod",
  "secret_value": "<runpod_api_key>"
}
```

Verification makes only a read-only request to `GET https://api.runpod.io/v2/pods?limit=1`. Seldrune stores the credential encrypted in its Owner Console vault; the response contains only configuration status and verification metadata, not the key. To see provider readiness, use `GET /api/v1/organizations/{organization_id}/tool-bootstrap/status`.

If the key is supplied through deployment environment instead, set `SELDRUNE_RUNPOD_API_KEY` on both the Seldrune web service and worker, then call `POST /api/v1/organizations/{organization_id}/tool-bootstrap` to create the provider reference and tools. `RUNPOD_API_KEY` is accepted as an environment alias. Do not commit either value to Git.

## Use the tools

After configuration, list tools with `GET /api/v1/organizations/{organization_id}/tools`. Create a run through `POST /api/v1/organizations/{organization_id}/tool-runs`, using the selected tool ID and its declared input schema. For a start or stop run, the request remains pending until an authorized Owner separately approves it through `POST /api/v1/organizations/{organization_id}/tool-runs/{run_id}/approve`.

Runpod REST API v2 uses `https://api.runpod.io/v2` and Bearer API-key authentication. Seldrune uses the v2 Pods list, get, and state-transition endpoints.
