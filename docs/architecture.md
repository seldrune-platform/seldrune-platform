# Seldrune Platform Architecture — v1.x

Seldrune is an AI-native operating platform for research, software engineering, automation, ventures, talent, managed operations, and future products. The platform remains a modular monolith so governance, identity, orchestration, audit, billing, and execution share one authoritative transactional boundary while the product is still evolving rapidly.

## Core architecture

### API and operator surfaces

FastAPI exposes the versioned `/api/v1` control plane. The repository also ships an owner console and runtime/status surfaces. Production API documentation can be disabled independently from the application endpoints.

### Identity and access

Identity is database-backed and organization-scoped. Seldrune currently provides:

- one-time owner bootstrap followed by invitation-based onboarding,
- organization roles and permission-based RBAC,
- password hashing and signed access tokens,
- rotating refresh-token families with replay detection,
- server-side access-token and refresh-session revocation,
- login brute-force throttling,
- TOTP MFA with one-time recovery codes,
- member administration with role ceilings,
- organization-scoped security events and audit trails.

Email verification and password/account recovery are implemented with one-time hashed tokens, expiry, replay protection, and refresh-session revocation after password reset.

### Organization kernel

Organizations contain governed operating structure such as departments, goals, projects, tasks, budgets, resources, and accountable owners or agents. Tasks can be authoritatively linked to projects so downstream model usage and project accounting can be reconciled without relying on free-form metadata.

### Agent, model, and tool governance

The Agent Registry stores governed agent definitions, model policy, runtime configuration, tool grants, and immutable configuration revisions. Model calls pass through a provider abstraction and are recorded for usage, latency, token, and cost analysis. Tool execution is constrained by both user RBAC and agent-level tool policy, with human approval checkpoints for consequential actions.

### Orchestration and execution

Seldrune supports durable tasks and higher-level orchestration while preserving explicit human control. Execution paths include approval-aware orchestration, recovery/resume behavior, project attribution, and owner-facing command/attention surfaces. Consequential workflows are designed to fail closed rather than bypass governance when required state is unavailable.

### Knowledge and research

The knowledge layer stores reusable organizational context and retrieval material. Research connectors and live connector policy provide governed access to external information sources while keeping provider credentials outside normal application records.

### Ingress, secrets, and external actions

Signed inbound webhooks provide authenticated ingress. Secret references identify externally supplied credentials without storing secret values in normal application tables. Runtime secret resolution uses a provider abstraction. Environment-backed references remain supported, and AWS Secrets Manager is available for production managed-secret resolution without persisting secret values in application tables.

### Audit, security, and observability

Security-relevant and governed actions are recorded with organization/user/resource attribution. The audit explorer, security center, owner-attention feeds, and privacy-safe push notifications provide operational visibility without embedding raw credentials, tokens, MFA codes, webhook signatures, or secret values.

### Billing and accounting integrity

Model invocations are visible through billing/usage reporting and can roll up by project and department. Unknown or unpriced model cost is preserved as unknown rather than silently treated as zero. Unresolved unpriced usage can block further governed budget execution until an authorized owner records an accounting correction.

## Deployment and readiness

Production uses PostgreSQL migrations through Alembic and starts by running `alembic upgrade head` before Uvicorn. CI exercises the same migration chain against PostgreSQL before a release can merge.

Seldrune exposes two health surfaces:

- `/api/v1/status` — informational diagnostics; it remains HTTP 200 so operators can inspect degraded state.
- `/api/v1/ready` — strict deployment readiness; it returns HTTP 503 unless the database is reachable, the configured model provider is available, and the production database revision matches the code's Alembic head.

Status responses include non-secret release provenance when available and expose only the current/expected schema revision, never database credentials or connection strings. Render uses `/api/v1/ready` as its health-check path.

## Engineering principles

- Cloud-first while keeping local development practical on ordinary laptops and Termux-class environments.
- Human approval for consequential financial, employment, security, legal, and production actions.
- No passwords, API keys, private certificates, access tokens, or production secret values committed to Git.
- Prefer a modular monolith until scale, isolation, or reliability requirements justify service separation.
- Treat PostgreSQL migrations, production startup, and strict readiness as release gates rather than assuming unit tests imply deployability.
- Keep model providers behind the model gateway so Seldrune is not locked to a single AI vendor.
- Preserve tenant isolation and auditability through every execution, billing, and administration path.
- Fail closed when security, approval, accounting, or schema state is incomplete.

## Current production-readiness priorities

The v1.x core now has identity, organization governance, agent/tool/model controls, orchestration, audit/security monitoring, billing integrity, deployment migration gates, one-time email verification and password/account recovery flows, and provider-based managed secret resolution including AWS Secrets Manager.

### v1.4 roadmap — production resilience

The next release phase focuses on proving operational resilience rather than adding another control-plane primitive:

1. integrate a real outbound email delivery provider with delivery-failure observability for verification and recovery flows,
2. automate PostgreSQL backup creation and document a tested restore procedure with explicit recovery objectives,
3. extend production observability with actionable health, error, latency, and saturation signals while preserving secret-safe telemetry,
4. validate scaling behavior and degraded-dependency recovery under representative load,
5. keep lint, full tests, PostgreSQL migration smoke, and production startup/readiness smoke as mandatory release gates.

Broad external customer access should remain gated on successful backup/restore validation and production observability evidence.

## Universal Organization OS north star

Seldrune is a universal AI-native organization operating system, not a domain-specific application. Domain factories such as software, automation, healthcare, research, business, talent, infrastructure, and game production are dynamically composed capabilities of the same organization kernel.

The target execution loop is:

1. accept an owner objective and determine measurable outcomes and constraints,
2. research unknown requirements and retrieve reusable organizational playbooks,
3. synthesize a temporary or durable organization graph of directors, specialist teams, agents, humans, tools, models, vendors, and infrastructure,
4. decompose the objective into dependency-aware work and execute safe independent work in parallel,
5. acquire or build missing tools/capabilities in isolated environments and register them only after verification,
6. continuously verify outputs with evidence, critics, tests, policy gates, budgets, and approval requirements,
7. deploy or operate verified deliverables through governed integrations,
8. recover from failures, measure outcomes, consolidate successful playbooks, and reuse learned capabilities.

### Universal factories

The kernel may instantiate Software, Automation, R&D, Business, Operations, Talent, Growth, Venture, Infrastructure, Creative/Game, and new domain factories discovered at runtime. Factories are organizational templates rather than hard-coded limits on what Seldrune can pursue.

### Self-expanding capability loop

When an objective requires an unavailable capability, Seldrune should research the requirement, identify suitable models/tools/APIs or implementation paths, create the missing capability in a sandbox, test and security-review it, register the verified capability, resume the blocked objective, and record evidence and a reusable playbook. Unknown capability must never be treated as successful capability merely because a model claims it exists.

### Development priorities after v1.4 resilience

1. hierarchical organization synthesis and recursive delegation,
2. dependency-aware parallel orchestration with bounded concurrency and budgets,
3. sandboxed tool/capability construction and verification,
4. software and automation factories as the first end-to-end production benchmarks,
5. human/vendor/workforce routing for objectives requiring real-world execution,
6. outcome-driven learning, playbook promotion, and capability evaluation,
7. elastic cloud/GPU worker scheduling and cost-aware execution,
8. domain-factory generation without coupling the core OS to any single industry.

Consequential production, financial, employment, security, and legal actions remain approval-gated even when planning and preparation are autonomous.
