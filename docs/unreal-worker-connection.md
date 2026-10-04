# Unreal worker connection for Seldrune

Seldrune exposes Unreal Engine actions to Seldrune GPT through an authenticated worker adapter. The adapter does not install Unreal inside the Seldrune web service and does not depend on Runpod.

## Connect it

In **Connections**, choose **Unreal Engine Worker**, enter the worker's public HTTPS URL and bearer token, then use **Verify and connect**. Seldrune checks the authenticated `GET /v1/healthz` response before storing the connection encrypted in the organization vault. The worker must return:

```json
{"service":"seldrune-unreal-worker","status":"ready"}
```

The worker owns engine licensing, approved download sources, persistent storage, installation, and job execution. Seldrune never accepts arbitrary download URLs or shell commands from GPT.

## Worker API

- `GET /v1/healthz`: authenticated readiness check.
- `GET /v1/engine/status`: JSON fields `status`, `installed`, `version`, and optionally `storage_available_gb`.
- `POST /v1/engine/install`: accepts an optional `version` such as `5.4.4`; returns `202` JSON with `job_id`, `status`, and optionally `version`.

Seldrune GPT routes “check Unreal Engine status” to the read-only status action. Requests to download or install Unreal are queued only by a connected worker and the install action always requires owner approval because it consumes worker storage and bandwidth.

No Unreal worker is currently included in the Seldrune web deployment. This adapter becomes operational when a compatible HTTPS worker is connected.
