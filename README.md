# Seldrune Platform

Core platform for the **Seldrune AI-native virtual organization**.

Seldrune is a reusable operating layer for governed AI work across research, software engineering, automation, ventures, talent, managed operations, and future products.

## Current milestone — Seldrune v1.4

The platform has progressed beyond the original foundation milestone and now includes production-oriented organization, agent, security, governance, audit, billing, orchestration, and deployment-integrity capabilities.

Current platform capabilities include:

- governed external action runtime with deterministic owner-action compilation, provider receipts, bootstrap/preflight, and runtime defaults
- Seldrune Face v0.2 authorized frame/stream execution components with evidence-gated production claims
- Aetherion Reality Compiler v0.2 with bounded digital-twin simulation and truth-gated evidence boundaries
- explicit V22–V100 technical evolution contracts and an evidence-driven V100 owner-console control deck
- organization identity, membership administration, RBAC, invitations, tenant isolation, email verification, and account recovery
- rotating refresh sessions, server-side logout/session revocation, login throttling, TOTP MFA, and one-time MFA recovery codes
- security-event monitoring with owner attention integration
- agent registry, model policy, tool grants, immutable configuration revisions, and governed restore
- orchestration, human approval checkpoints, recovery runs, and project delivery workflows
- tool gateway, knowledge/memory, research connectors, signed inbound webhooks, secret references, and provider-based managed-secret resolution
- audit explorer, AI usage/cost reporting, budget authority, project/department attribution, and accounting integrity
- owner attention, browser/web-push notification infrastructure, and executive operating surfaces
- PostgreSQL/Alembic migrations, automated tests, GitHub Actions CI, and Render deployment configuration
- strict schema-aware deployment readiness with non-secret release provenance

### Deployment integrity

The v1.0.1 production-recovery patch added real PostgreSQL migration and production-startup gates after a migration-version-length defect kept production pinned to v0.85. v1.1 builds on that recovery by making readiness verify that the running database is at the exact Alembic head expected by the code and by exposing release provenance when the deployment platform provides it.

## Local development

The optional [Cloud GPU OS control plane](backend/README.md) and
[Expo mobile shell](mobile-os/README.md) are independent Node packages for an
on-demand RunPod workstation. Their Render Blueprint is `backend/render.yaml`;
the root Blueprint continues to deploy the Python platform.

Requires Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn backend.app.main:app --reload
```

Open:

- API docs: `http://127.0.0.1:8000/docs`
- Owner console: `http://127.0.0.1:8000/console`
- Diagnostics: `http://127.0.0.1:8000/api/v1/status`
- Strict readiness: `http://127.0.0.1:8000/api/v1/ready`

Run quality checks:

```bash
ruff check .
pytest -q
```

## Production deployment

The Render web service runs database migrations before starting the API:

```bash
alembic upgrade head && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}
```

`/api/v1/status` always provides informational diagnostics, including application version, environment, model-provider state, schema revision state, and non-secret release provenance when available. `/api/v1/ready` is the deployment health endpoint: in production it returns HTTP 503 unless the database is reachable, the configured model provider is available, and the database revision matches the code's Alembic head.

## Security

Never commit passwords, API keys, access tokens, private certificates, MFA recovery codes, or production secrets. Use `.env` for local development and managed secret storage or secret references for production systems.

See [`docs/architecture.md`](docs/architecture.md) for the broader platform direction and [`docs/identity-access.md`](docs/identity-access.md) for identity/security controls.
