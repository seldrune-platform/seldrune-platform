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

This v1 compiler is an execution contract generator, not yet the full contract
chain runner. The next runtime layer should consume these ordered contracts,
resolve bindings only from persisted tool outputs, apply every acceptance
predicate, and write the final cognitive verification only after the whole
chain succeeds.


## Executable Contract Chain Runner v1

The Stage Compiler contract is now consumed by a bounded runtime chain runner.
The runner does not trust model prose or reconstruct missing evidence from
guesses. It advances only through persisted model input, governed ToolRuns, and
explicit acceptance predicates.

For repository-engineering contracts the runtime now:

1. requires structured model output matching the compiler response schema;
2. resolves wildcard artifact bindings for repeated governed file writes;
3. resolves later step inputs only from persisted earlier ToolRun outputs;
4. reuses persisted ToolRuns by contract step marker instead of duplicating
   side effects after a retry;
5. stops on missing bindings, unavailable tools, provider-pending states,
   failed acceptance checks, or required approval;
6. resumes an existing pending high-risk ToolRun only through the existing
   approval path;
7. independently revalidates every persisted succeeded ToolRun before granting
   cognitive mission completion; and
8. records the full contract-chain state in the mission task output for console
   telemetry and later recovery.

GitHub workflow dispatch now performs bounded post-dispatch run discovery because
GitHub's dispatch endpoint normally returns HTTP 204 without a workflow run ID.
The discovered run ID becomes the persisted binding for the subsequent
workflow-status acceptance step. If discovery cannot resolve a run, the chain
remains unresolved rather than inventing an identifier.

The final merge remains a high-risk governed tool action. A repository stage
cannot become runtime-verified until the exact persisted merge ToolRun succeeds
after the CI acceptance step has succeeded. Model-produced code remains an
input to that chain and is never treated as completion evidence by itself.
