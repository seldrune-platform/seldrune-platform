# Data and Security Foundation

Seldrune is designed as a multi-tenant platform. Every customer or internal business unit is represented by an organization, and user access is granted through organization memberships.

## Core identity model

- `organizations`: tenant boundary and business identity.
- `users`: human identities. Authentication credentials will live in an identity provider rather than this table.
- `memberships`: joins users to organizations and assigns a role.
- `audit_logs`: records security- and business-relevant actions.

## RBAC

Initial roles are `owner`, `admin`, `member`, and `auditor`. Permissions are defined in application code so they can be tested and reviewed. High-risk actions will later require an explicit approval policy in addition to ordinary RBAC.

## Database environments

Local development defaults to SQLite so a solo developer can run Seldrune immediately. Staging and production should use PostgreSQL through `SELDRUNE_DATABASE_URL`, for example a managed PostgreSQL service with TLS, backups, point-in-time recovery, private networking where available, and separate credentials per environment.

Database schema changes must go through Alembic migrations. Do not make manual production schema changes.

## Security rules

1. Never store passwords, API keys, access tokens, or private client secrets in GitHub.
2. Never include secrets in audit-log details.
3. Scope all future customer-owned records to an organization.
4. Treat audit records as append-only at the application layer.
5. Use least privilege for database and cloud identities.
6. Separate development, staging, and production databases.
7. Require human approval for destructive, financial, employment, privileged-access, and external-publication actions.
8. Add PostgreSQL row-level security as a defense-in-depth layer once tenant-scoped business tables are introduced.

## Migration commands

```bash
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

Production migrations should run from CI/CD or a controlled release job, not from an engineer's phone or laptop.
