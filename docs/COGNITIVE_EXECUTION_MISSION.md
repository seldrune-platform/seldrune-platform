# Seldrune Cognitive Execution Mission

## Purpose

The cognitive mission is the first Seldrune execution exercise that converts one
owner instruction into a persistent, dependency-aware development program.

It does not claim neural-network training or autonomous consciousness. It is a
deterministic planning and execution-control layer that uses the existing
Seldrune task, orchestration, audit, tool, and model infrastructure.

## Single-go execution architecture

One owner instruction is processed as three linked operations:

1. **Architecture** — build the complete milestone graph and validate that it is
   acyclic.
2. **Dependency preparation** — calculate which incomplete stages have all
   prerequisites satisfied and may be queued in parallel.
3. **Console deployment** — persist one master task, queue dependency-ready
   child tasks idempotently, and render completed, remaining, paused, blocked,
   and ready stages in the owner console.

The API does not mark work complete merely because a task was queued. Completed
roadmap weight is granted only to milestones explicitly recorded as completed
with evidence references.

## Progress model

Each workstream owns 100 milestone-weight points. Workstream weights also sum to
100, so the overall percentage is computed as:

`sum(workstream_completion * workstream_weight / 100)`

The v2 roadmap snapshot reports 61.0% completed and 39.0% remaining.

This percentage is a roadmap measure, not a benchmark of general intelligence,
model quality, or consciousness.

## Current workstreams

- UNARCHI cognitive intelligence
- multi-model intelligence bus
- owner console and execution control
- Live Face and Voice platform
- cost and local-processing control
- universal tool and provider gateway
- autonomous product factory

The Live Face and Voice track is intentionally paused by owner instruction.
Paused stages remain visible in the graph but are excluded from the parallel
ready wave.

## Parallel readiness

A pending stage is ready when:

- every declared dependency is completed;
- its workstream is not paused; and
- the stage itself is not paused.

The first mission snapshot exposes four parallel-ready stages:

- UNARCHI v0.31 renewed-degradation recovery cycle;
- unified multi-provider model router;
- local PDF label editing;
- provider connector expansion.

They are queued as ordinary Seldrune tasks. Queueing is idempotent for the
current master mission task.

## Execution boundary

The mission uses `single_go_intent=true`, automatic dependency evaluation, and
automatic queueing of ready stages.

It deliberately keeps `auto_execute_external_actions=false`. External or
high-impact execution still requires a connected provider, applicable policy,
and verifiable completion evidence. This prevents the console from reporting a
planned or queued action as completed.

## One-Go Execution Controller

Cognitive Execution v2 adds the One-Go controller. One owner action can now:

1. synchronize the durable master mission;
2. queue dependency-ready work without duplicating existing stage tasks;
3. route automatic stages to active agents using capability and prior-task
   evidence;
4. execute registered low-risk tools or model work through the existing
   Seldrune runtimes;
5. distinguish execution from verified completion;
6. accept a tool receipt only when it belongs to a persisted succeeded ToolRun,
   is tied to the same task and organization, matches the task's declared tool
   contract, and matches the receipt derived from that ToolRun;
7. recompute roadmap progress from newly verified stages;
8. unlock the next dependency wave and continue within configured wave and task
   limits.

Model output by itself is explicitly unverified. It can produce analysis or a
proposal, but it cannot increase roadmap completion.

Owner-gated and external-resource stages are not automatically executed. Tools
that require approval remain blocked until their existing approval path is
satisfied.

The controller also respects the organization governance policy. When
autonomous execution is disabled, a One-Go request performs no execution. The
configured maximum steps per command caps the controller task limit, while
metered model calls continue to use Seldrune's AI spend governor.

## Executable Stage Compiler v1

The next architecture layer is now implemented as a compiler rather than a
free-form prompt. Every queued mission stage can carry a
`compiled_execution_contract` that classifies the work and describes the
machine-executable evidence chain needed for completion.

Repository-engineering stages compile into a bounded sequence:

1. produce repository artifacts as structured model output;
2. inspect the configured repository;
3. create a deterministic feature branch;
4. bind generated artifact paths and contents into governed file writes;
5. open a merge-eligible pull request;
6. dispatch the repository CI workflow;
7. verify that the exact workflow run concludes successfully; and
8. merge the exact tested head through the governed high-risk merge tool.

Deployment stages compile into a Render deployment receipt followed by a
deployment-status verification step. Repository stages cannot become complete
before the tested pull request is actually merged. The merge action remains
high-risk and uses the existing approval path. Stages that need GPU/external
resources or explicit owner approval remain gated by their existing execution
mode.

The compiler records tool availability, missing required inputs, runtime
bindings, approval/risk metadata, and acceptance checks. A binding such as a
workflow run ID is deliberately unresolved until the preceding tool actually
returns it. Model-produced code or analysis still cannot complete a stage by
itself.

## Compiled Contract Runner v1

The compiled-contract runtime is now implemented on top of the compiler. One-Go
routes compiled stages through persisted child tasks instead of terminalizing
the parent stage from a free-form model response.

The runner:

- preflights unavailable tools and fixed missing inputs before model spend;
- requests schema-constrained model output for repository artifacts;
- rejects absolute, traversal, and `.git` artifact paths and bounds artifact
  count/content size;
- persists every model/tool step as a child task so execution can resume after
  interruption without repeating accepted side effects;
- resolves downstream bindings only from accepted upstream outputs;
- verifies the exact persisted ToolRun, tool id, receipt, and acceptance
  predicate for every machine step;
- distinguishes pending CI/deploy state from terminal acceptance failure;
- never auto-approves high-risk workflow dispatch or merge actions;
- requires the exact tested PR head to be merged before repository work can
  become runtime-verified; and
- derives a SHA-256 chain receipt from the parent task, contract version, model
  task, and canonical ToolRun receipts.

Stored `cognitive_verification` flags are not trusted on their own. One-Go and
mission progress revalidate the underlying evidence before granting completion
credit or unlocking a dependency.

The remaining production gate is execution evidence from hosted CI. The code
must stay unmerged while repository CI runners fail before test steps begin.

## Contract Recovery Controller v1

One-Go now includes a bounded recovery layer above the compiled-contract runner.
It may re-advance an automatic contract for at most five recovery rounds in one
owner request. The default is three rounds.

Recovery is deliberately narrow:

- `step_limit`, pending acceptance, and already-running tool/model states may be
  rechecked;
- owner approval gates stop immediately;
- external-resource stages stop immediately;
- missing tools, unresolved fixed inputs, unresolved bindings, and missing
  capable agents stop as configuration blockers;
- terminal model, tool, child-task, parent-task, and acceptance failures are not
  retried; and
- the recovery controller never passes
  `confirmed_sensitive_action=True`, so high-risk actions remain on the normal
  approval path.

The controller reports every recovery round and a final blocker
classification. One-Go aggregates those rounds and exposes owner-approval,
configuration, external-resource, and still-retryable gate counts to the Owner
Console.

### GitHub workflow-dispatch binding

GitHub's workflow-dispatch endpoint commonly succeeds with HTTP 204 and no
workflow-run ID. A missing run ID would leave the compiled `verify-ci` binding
unresolvable even though CI was successfully dispatched.

The GitHub adapter now snapshots recent workflow-dispatch run IDs before
dispatch, performs the dispatch, then performs bounded run discovery on the same
workflow and branch. Only a newly observed run created at the dispatch boundary
is accepted as the runtime binding. If no new run can be resolved, the adapter
keeps the run ID unresolved instead of inventing one.

This recovery layer does not change the current merge gate: PRs #287, #288, and
#289 remain unmerged until hosted CI produces executable repository evidence.

## Verified upstream deployment handoff

Deployment contracts already bind Render's `commit_id` to
`upstream.verified_commit_sha`. The mission scheduler now supplies that binding
only from a dependency stage whose compiled contract is still independently
verifiable and whose persisted GitHub merge ToolRun reports `merged=true` with
a commit SHA.

When several dependency stages have verified merge receipts, the most recently
completed merge ToolRun is selected. This represents the newest verified commit
on the shared deployment branch after the prerequisite merges. The selected
evidence records the source stage, parent task, ToolRun, completion time, and
verification references.

Queued deployment tasks are recompiled with this evidence. If dependency
verification later stops validating, stale `upstream_evidence` is removed and
the deployment binding remains unresolved rather than deploying an assumed
commit.

## Hosted CI infrastructure classification

A completed GitHub Actions run with conclusion `failure` is no longer assumed
to be a repository failure before its job metadata is inspected. The workflow
status adapter checks the latest jobs and distinguishes a pre-step hosted-runner
failure from an executed repository check.

The narrow infrastructure signature is:

- the workflow is completed with conclusion `failure`;
- no job reports an allocated runner; and
- no job reports any executed steps.

That signature is emitted as
`failure_classification=hosted_runner_unavailable`. The compiled
`verify-ci` acceptance rule maps only that value to an external-resource
blocker. Runs that allocated a runner or executed repository steps continue
through the normal success/pending/failure acceptance logic.

Contract recovery treats this blocker as non-retryable within the bounded
One-Go loop. The Owner Console can therefore report that execution stopped on
an external CI resource without mislabeling unexecuted code as a failed test.
The CI success requirement itself is unchanged.

## GitHub Actions billing diagnostics

Pre-step GitHub Actions failures are refined by reading check-run annotations
when the connected GitHub credential can access them. The classifier recognizes
billing/spending-limit language separately from runner-capacity language.

The workflow status evidence can now include:

- `github_actions_billing_block` when annotations indicate a payment or
  Actions spending-limit problem;
- `github_actions_runner_unavailable` when annotations identify hosted runner
  acquisition/capacity failure; or
- `hosted_runner_unavailable` when the job has no runner and no executed steps
  but the annotation does not identify a more specific cause.

The adapter also returns a bounded failure detail and remediation hint. These
fields remain diagnostic only: no failure classification satisfies the CI
success acceptance rule, and no merge or deployment gate is bypassed.

The Owner Console recognizes the billing classification and tells the owner to
check the organization Actions budget and payment state before rerunning.

## Portable CI verification receipt

CircleCI and GitHub Actions now call the same repository-owned verifier:
`bash scripts/ci_verify.sh`. The verifier is provider-neutral and can also be
run by another isolated Linux/Python 3.12 runner with PostgreSQL.

The runner requires:

- `SELDRUNE_DATABASE_URL` for the application database;
- `SELDRUNE_CI_POSTGRES_DSN` for the PostgreSQL readiness probe; and
- `SELDRUNE_CI_RELEASE_SHA` for binding the evidence to an exact commit.

It performs the same evidence sequence regardless of provider: PostgreSQL
readiness, Ruff, pytest, Alembic upgrade to head, and a production-mode
`/api/v1/ready` smoke test. A successful run writes
`seldrune-ci-receipt.json` with the release SHA, check names, and readiness
payload.

Hosted CI providers upload/store that receipt after success. This creates a
portable evidence format without weakening the existing rule that merge and
deployment require a successful CI conclusion for the exact head.

## Signed portable CI attestation

Portable CI receipts can now be authenticated independently of the provider
that executed the verifier. When `SELDRUNE_CI_RECEIPT_HMAC_KEY` is present,
`scripts/ci_verify.sh` canonicalizes the successful receipt and emits an
HMAC-SHA256 signature beside the JSON receipt.

Seldrune exposes a low-risk `portable-ci/verify-receipt` tool backed by the
same secret through `SELDRUNE_CI_RECEIPT_HMAC_KEY`. The verifier rejects:

- unsigned or incorrectly signed receipts;
- any receipt changed after signing;
- non-success receipt states;
- missing PostgreSQL, Ruff, pytest, Alembic, or production-readiness checks;
- readiness payloads that are not production-ready; and
- readiness release SHAs that do not equal the signed receipt SHA.

A successful verification returns `conclusion=success`,
`signature_verified=true`, and a provider receipt id derived from the exact
release SHA plus the canonical receipt digest.

The signature mechanism is intentionally not a merge bypass. A bare JSON
object, owner-supplied success flag, or Railway service status is insufficient
to satisfy repository completion. The trusted verifier is the provider-neutral
building block for recovery when hosted CI is unavailable; merge/deployment
contracts continue to require exact-head evidence and their existing governed
approval path.

## Fail-closed portable CI fallback contract

Repository-engineering contracts keep GitHub Actions as the primary CI verdict.
The `verify-ci` step may name `verify-portable-ci` as a fallback only for
the explicit external-resource classifications already used for hosted-runner
or Actions billing/capacity failures.

The fallback is conditional and fail-closed:

- a normal GitHub CI failure stops the contract and cannot invoke the fallback;
- a successful GitHub CI verdict skips the portable verifier;
- an external-resource GitHub verdict may continue only to the declared
  `portable-ci/verify-receipt` step;
- the portable step reads a signed receipt and signature from
  `portable_ci_evidence` on the parent task;
- missing portable evidence or a missing verifier remains an external-resource
  gate rather than being retried as a code failure;
- merge SHA resolution prefers the successful GitHub head SHA and otherwise
  uses the successfully verified portable receipt head SHA;
- the final compiled-contract evidence verifier replays the conditional path,
  requires the fallback when the primary CI state was external-resource, and
  checks that the merge request SHA matches the selected verified CI output.

This does not weaken the merge action. `merge-verified-pull-request` remains
a high-risk action and its existing approval requirements still apply.

