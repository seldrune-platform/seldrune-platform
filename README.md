# Seldrune Platform

Core platform for the **Seldrune AI-native virtual organization**.

Seldrune is being developed as a reusable operating layer for research, software engineering, automation, ventures, talent, managed operations, and future products.

## Current milestone — Core v0.1

The first milestone intentionally stays small:

- FastAPI backend foundation
- environment-based configuration
- service status endpoint
- automated tests
- GitHub Actions CI
- architecture and engineering principles

The next milestone adds PostgreSQL, migrations, organizations/users, RBAC, and audit logging before the first agent framework is introduced.

## Local development

Requires Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn backend.app.main:app --reload
```

Open:

- API docs: `http://127.0.0.1:8000/docs`
- Status: `http://127.0.0.1:8000/api/v1/status`

Run quality checks:

```bash
ruff check .
pytest -q
```

## Security

Never commit passwords, API keys, access tokens, private certificates, or production secrets. Use `.env` locally and a managed secret store in cloud environments.

See [`docs/architecture.md`](docs/architecture.md) for the platform direction.
