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
