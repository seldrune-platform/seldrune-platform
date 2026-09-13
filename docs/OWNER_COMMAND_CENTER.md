# Owner Command Center

Version 0.12 adds an owner-only strategic command surface over the existing orchestrator.

1. `POST /api/v1/organizations/{organization_id}/owner-commands` turns one objective into a matched multi-agent plan.
2. Inspect the returned steps, agent matches, and unmatched capabilities.
3. `POST .../owner-commands/{run_id}/approve` records explicit owner approval.
4. `POST .../owner-commands/{run_id}/execute` runs the approved plan sequentially with audit records and upstream context.

Commands are stored as orchestration runs with governed metadata, so the feature reuses task execution, memory, tools, audit, retry, and status behavior instead of creating a parallel runtime.

Only an organization owner may create, list, approve, or execute owner commands. Execution before approval returns HTTP 409.
