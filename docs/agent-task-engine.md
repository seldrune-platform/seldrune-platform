# Agent and Task Engine v0.4

This milestone adds the basic runtime records needed for Seldrune agents and work items.

Agents belong to an organization and store a name, slug, status, capabilities, and runtime
configuration.

Tasks belong to an organization and store an objective, input, priority, optional assigned agent,
status, output, errors, and timestamps.

Supported task states are queued, assigned, running, succeeded, failed, and cancelled. State
changes are validated so tasks cannot jump directly between incompatible states.

Task events record creation, assignment, and status changes. The existing audit log also records
important agent and task actions.

Organization RBAC is reused. Agent management requires `agents:manage`; normal task operations
require `agents:run`.

The next milestone can build orchestration and agent selection on top of these records.
