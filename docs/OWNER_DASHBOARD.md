# Owner Dashboard and Decision Briefs

Version 0.13 gives an organization owner a compact operational view of strategic commands.

- `GET /api/v1/organizations/{organization_id}/owner-dashboard` returns command, approval,
  execution, model-usage, token, estimated-cost, and recent-command metrics.
- `GET /api/v1/organizations/{organization_id}/owner-commands/{run_id}/brief` returns progress,
  unmatched-agent and failed-step risks, bounded output excerpts, and the recommended next action.

Both endpoints are owner-only and compute from the existing governed runtime, so they introduce no
duplicate state or migration burden.
