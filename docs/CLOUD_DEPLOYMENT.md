# Secure Console Login and Cloud Deployment

Version 0.15 replaces manual token and organization entry with the existing audited email/password
login. The console discovers the owner's organization through `/auth/me`, keeps the short-lived token
in session storage, clears it on logout or HTTP 401, and rejects non-owner accounts.

## Container deployment

The production image runs database migrations before starting Uvicorn as a non-root user. Set:

- `SELDRUNE_ENVIRONMENT=production`
- `SELDRUNE_AUTH_SECRET_KEY` to a random value of at least 32 characters
- `SELDRUNE_DATABASE_URL` to a managed PostgreSQL connection string
- model-provider credentials in the hosting secret store

`render.yaml` provides an optional Render blueprint with a web service, health check, generated auth
secret, and managed PostgreSQL. The same Dockerfile can run on Cloud Run, Railway, Fly.io, Azure
Container Apps, AWS ECS, or another OCI-compatible host.
