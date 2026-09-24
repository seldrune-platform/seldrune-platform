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

The next major architecture work is the executable stage compiler: convert
development milestones such as repository engineering, provider setup, CI
verification, and deployment into explicit registered tool contracts with
machine-checkable acceptance evidence. That will let more One-Go work advance
from executed to verified without weakening the evidence boundary.
