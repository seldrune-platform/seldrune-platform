# Seldrune Core v0.1 Architecture

Seldrune is being built as an AI-native operating platform for research, software, automation, ventures, talent, and managed operations.

## v0.1 objective

Establish a small, reliable platform kernel before adding specialized products.

## Initial layers

1. **API layer** — FastAPI service endpoints and future webhooks.
2. **Configuration layer** — environment-driven application settings.
3. **Identity and access** — users, organizations, roles, approvals. Planned next.
4. **Task orchestration** — durable jobs, agent tasks, human approval checkpoints. Planned next.
5. **Agent registry** — definitions, capabilities, model/tool permissions, versions. Planned next.
6. **Knowledge layer** — structured memory, documents, retrieval, provenance. Planned later.
7. **Audit and observability** — every important action traceable and reviewable. Planned next.
8. **Product modules** — R&D, opportunity discovery, payroll, talent, client automation, and ventures built on the kernel rather than as disconnected systems.

## Engineering principles

- Cloud-first, but development must remain usable from Termux and ordinary laptops.
- Human approval for consequential financial, employment, security, legal, and production actions.
- No secrets committed to Git.
- Prefer modular monolith architecture initially; split services only when scale or isolation requires it.
- Every production feature should have tests, logging, and an explicit owner.
- Model providers must sit behind a model gateway so Seldrune is not locked to one AI vendor.

## Immediate roadmap

1. API foundation and CI.
2. PostgreSQL persistence and migrations.
3. User, organization, and RBAC models.
4. Audit log.
5. Agent registry and task execution model.
6. Human approval engine.
7. Model gateway.
8. Owner command-center API.
