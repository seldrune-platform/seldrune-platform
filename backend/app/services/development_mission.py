from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.tasking import TERMINAL_TASK_STATUSES, TaskStatus
from backend.app.core.tools import ToolRunStatus
from backend.app.models.task import Task, TaskEvent
from backend.app.models.tool_run import ToolRun
from backend.app.services.cognitive_evidence import (
    verify_task_completion_evidence,
)
from backend.app.services.stage_compiler import compile_stage_execution_contract


MISSION_KIND = "seldrune_cognitive_development_mission"
MISSION_VERSION = "cognitive-execution-v2"
MASTER_TASK_TITLE = "Seldrune Master Development Mission"


@dataclass(frozen=True)
class StageDefinition:
    id: str
    title: str
    objective: str
    workstream: str
    weight: int
    status: str
    depends_on: tuple[str, ...]
    capabilities: tuple[str, ...]
    execution_mode: str = "automatic"
    evidence_refs: tuple[str, ...] = ()
    paused_reason: str | None = None


@dataclass(frozen=True)
class WorkstreamDefinition:
    id: str
    title: str
    weight: int
    paused: bool = False
    paused_reason: str | None = None


WORKSTREAMS = (
    WorkstreamDefinition("unarchi", "UNARCHI cognitive intelligence", 24),
    WorkstreamDefinition("model_bus", "Multi-model intelligence bus", 16),
    WorkstreamDefinition("console", "Owner console and execution control", 15),
    WorkstreamDefinition(
        "live_media",
        "Live face and voice platform",
        15,
        paused=True,
        paused_reason="Paused by owner while cognitive execution architecture is built.",
    ),
    WorkstreamDefinition("cost_control", "Cost and local-processing control", 8),
    WorkstreamDefinition("tooling", "Universal tool and provider gateway", 12),
    WorkstreamDefinition("factory", "Autonomous product factory", 10),
)


STAGES = (
    StageDefinition(
        "unarchi_v01_v30",
        "UNARCHI v0.01-v0.30 research checkpoints",
        "Preserve the merged cognitive kernel through renewed-degradation resolution.",
        "unarchi",
        75,
        "completed",
        (),
        ("reasoning", "validation"),
        evidence_refs=("git:main:unarchi-v0.30", "pr:285"),
    ),
    StageDefinition(
        "unarchi_v31",
        "UNARCHI v0.31 renewed-degradation recovery cycle",
        "Require a fresh recovery and independent holdout after second rollback.",
        "unarchi",
        4,
        "pending",
        ("unarchi_v01_v30",),
        ("reasoning", "validation", "engineering"),
    ),
    StageDefinition(
        "unarchi_v32",
        "UNARCHI v0.32 repeated episode isolation",
        "Prevent evidence reuse across repeated failure and recovery episodes.",
        "unarchi",
        4,
        "pending",
        ("unarchi_v31",),
        ("reasoning", "validation"),
    ),
    StageDefinition(
        "unarchi_v33",
        "UNARCHI v0.33 multi-hypothesis arbitration",
        "Arbitrate multiple competing causal models with explicit evidence.",
        "unarchi",
        3,
        "pending",
        ("unarchi_v32",),
        ("reasoning", "analysis"),
    ),
    StageDefinition(
        "unarchi_v34",
        "UNARCHI v0.34 hierarchical long-horizon planning",
        "Turn one objective into goals, subgoals, checkpoints, and replanning.",
        "unarchi",
        3,
        "pending",
        ("unarchi_v33",),
        ("planning", "reasoning"),
    ),
    StageDefinition(
        "unarchi_v35",
        "UNARCHI v0.35 resource-aware cognition",
        "Treat money, compute, latency, risk, and uncertainty as planning variables.",
        "unarchi",
        3,
        "pending",
        ("unarchi_v34",),
        ("planning", "cost-control"),
    ),
    StageDefinition(
        "unarchi_v36",
        "UNARCHI v0.36 scalable persistent memory",
        "Add long-term retrieval, consolidation, provenance, and bounded forgetting.",
        "unarchi",
        2,
        "pending",
        ("unarchi_v35",),
        ("memory", "engineering"),
    ),
    StageDefinition(
        "unarchi_v37",
        "UNARCHI v0.37 controlled environment interaction",
        "Feed verified tool outcomes back into the cognitive state.",
        "unarchi",
        2,
        "pending",
        ("unarchi_v36", "tool_gateway_core"),
        ("tools", "reasoning"),
    ),
    StageDefinition(
        "unarchi_v38",
        "UNARCHI v0.38 multimodal observations",
        "Normalize image, audio, video, documents, and structured data as evidence.",
        "unarchi",
        1,
        "pending",
        ("unarchi_v37", "model_router_unified"),
        ("multimodal", "engineering"),
    ),
    StageDefinition(
        "unarchi_v39",
        "UNARCHI v0.39 model and skill orchestration",
        "Select models and tools using capability, cost, confidence, and outcomes.",
        "unarchi",
        1,
        "pending",
        ("unarchi_v38", "model_router_recency"),
        ("orchestration", "reasoning"),
    ),
    StageDefinition(
        "unarchi_v40",
        "UNARCHI v0.40 full cognitive validation",
        "Run long-horizon adversarial and recovery benchmarks before v1.0.",
        "unarchi",
        2,
        "pending",
        ("unarchi_v39",),
        ("validation", "research"),
    ),
    StageDefinition(
        "model_gateway_core",
        "Internal model gateway",
        "Provide one normalized request and response interface for model providers.",
        "model_bus",
        20,
        "completed",
        (),
        ("models", "engineering"),
        evidence_refs=("code:backend/app/services/model_gateway.py",),
    ),
    StageDefinition(
        "model_orchestrator_core",
        "Evidence-weighted agent orchestration",
        "Route tasks to capable agents using verified task history.",
        "model_bus",
        20,
        "completed",
        ("model_gateway_core",),
        ("orchestration", "engineering"),
        evidence_refs=("code:backend/app/services/orchestrator.py",),
    ),
    StageDefinition(
        "tool_gateway_core",
        "Tool gateway and governed execution",
        "Execute registered tools with audit, approval, and budget controls.",
        "model_bus",
        15,
        "completed",
        (),
        ("tools", "engineering"),
        evidence_refs=("code:backend/app/services/tool_gateway.py",),
    ),
    StageDefinition(
        "model_router_unified",
        "Unified multi-provider model router",
        "Add direct and compatible provider adapters behind one capability contract.",
        "model_bus",
        20,
        "pending",
        ("model_gateway_core",),
        ("models", "engineering"),
    ),
    StageDefinition(
        "model_router_recency",
        "Recent-performance trust and drift routing",
        "Weight recent verified performance above stale lifetime reputation.",
        "model_bus",
        10,
        "pending",
        ("model_orchestrator_core", "model_router_unified"),
        ("reasoning", "analytics"),
    ),
    StageDefinition(
        "model_verifier_fallback",
        "Independent verifier and escalation loop",
        "Verify model outputs and escalate only when cheaper paths fail.",
        "model_bus",
        10,
        "pending",
        ("model_router_unified",),
        ("validation", "models"),
    ),
    StageDefinition(
        "local_model_pool",
        "Local and low-cost model pool",
        "Connect local OpenAI-compatible workers for cheap repetitive work.",
        "model_bus",
        5,
        "pending",
        ("model_router_unified",),
        ("models", "cost-control"),
    ),
    StageDefinition(
        "console_auth_commands",
        "Owner authentication, commands, audit, and runtime status",
        "Keep owner-scoped command and evidence controls operational.",
        "console",
        45,
        "completed",
        (),
        ("frontend", "backend"),
        evidence_refs=("code:backend/app/web/index.html", "code:owner_commands"),
    ),
    StageDefinition(
        "console_gpt",
        "Seldrune GPT owner studio",
        "Provide chat, attachments, and governed execution from the console.",
        "console",
        20,
        "completed",
        ("console_auth_commands",),
        ("models", "frontend"),
        evidence_refs=("code:backend/app/api/routes/seldrune_gpt.py",),
    ),
    StageDefinition(
        "console_cognitive_mission",
        "Cognitive mission board",
        "Persist the full roadmap, dependency graph, progress, and parallel-ready lanes.",
        "console",
        10,
        "completed",
        ("console_auth_commands",),
        ("planning", "frontend", "backend"),
        evidence_refs=("feature:cognitive-mission-board",),
    ),
    StageDefinition(
        "console_one_go_executor",
        "One-go execution controller",
        "Queue and execute eligible dependency-ready stages under policy and evidence gates.",
        "console",
        15,
        "completed",
        ("console_cognitive_mission",),
        ("orchestration", "tools"),
        evidence_refs=("feature:one-go-execution-controller",),
    ),
    StageDefinition(
        "console_observability",
        "Cognitive execution observability",
        "Show model routing, stage evidence, retries, cost, latency, and drift live.",
        "console",
        10,
        "pending",
        ("console_cognitive_mission", "model_router_recency"),
        ("frontend", "analytics"),
    ),
    StageDefinition(
        "live_media_architecture",
        "Live media architecture and evidence recorder",
        "Preserve the WebRTC, cloud GPU, session recorder, and verification design.",
        "live_media",
        25,
        "completed",
        (),
        ("media", "architecture"),
        evidence_refs=("pr:192", "milestone:STEP_150_ONNX_EXPORT"),
    ),
    StageDefinition(
        "live_face_runtime",
        "Commercially usable real-time face runtime",
        "Integrate a permitted face model and verify transformed live frames.",
        "live_media",
        25,
        "pending",
        ("live_media_architecture",),
        ("vision", "gpu"),
        execution_mode="external-resource",
        paused_reason="Track paused by owner.",
    ),
    StageDefinition(
        "live_voice_runtime",
        "Real-time voice conversion runtime",
        "Add low-latency voice conversion with verified audio metrics.",
        "live_media",
        15,
        "pending",
        ("live_media_architecture",),
        ("audio", "gpu"),
        execution_mode="external-resource",
        paused_reason="Track paused by owner.",
    ),
    StageDefinition(
        "live_av_sync",
        "Audio-video synchronization",
        "Synchronize transformed video and voice within measured latency limits.",
        "live_media",
        10,
        "pending",
        ("live_face_runtime", "live_voice_runtime"),
        ("media", "validation"),
        execution_mode="external-resource",
        paused_reason="Track paused by owner.",
    ),
    StageDefinition(
        "live_mobile_webrtc",
        "Mobile HD WebRTC client",
        "Deliver cloud inference to ordinary phones and laptops.",
        "live_media",
        15,
        "pending",
        ("live_av_sync",),
        ("webrtc", "mobile"),
        execution_mode="external-resource",
        paused_reason="Track paused by owner.",
    ),
    StageDefinition(
        "live_scale_release",
        "Production scaling and release",
        "Add concurrency, reconnect, commercial licensing, and release validation.",
        "live_media",
        10,
        "pending",
        ("live_mobile_webrtc",),
        ("deployment", "validation"),
        execution_mode="owner-gated",
        paused_reason="Track paused by owner.",
    ),
    StageDefinition(
        "pdf_local_exact",
        "Zero-cost exact PDF edits",
        "Use local parsing for deterministic text and numeric edits.",
        "cost_control",
        35,
        "completed",
        (),
        ("documents", "cost-control"),
        evidence_refs=("pr:261",),
    ),
    StageDefinition(
        "cost_meter_circuit",
        "AI spend meter and budget circuit breaker",
        "Track model cost and stop governed execution before budget overrun.",
        "cost_control",
        25,
        "completed",
        (),
        ("cost-control", "backend"),
        evidence_refs=("code:autonomous_execution", "code:owner-dashboard"),
    ),
    StageDefinition(
        "pdf_local_labels",
        "Local PDF label editing",
        "Finish ambiguity-safe field-label replacement without paid AI.",
        "cost_control",
        15,
        "pending",
        ("pdf_local_exact",),
        ("documents", "engineering"),
        execution_mode="owner-gated",
        evidence_refs=("draft-pr:262",),
    ),
    StageDefinition(
        "cost_aware_model_router",
        "Cost-aware cognitive model routing",
        "Choose the cheapest verified model path within quality and risk limits.",
        "cost_control",
        25,
        "pending",
        ("model_router_recency", "model_verifier_fallback"),
        ("cost-control", "models"),
    ),
    StageDefinition(
        "github_tooling",
        "GitHub connected execution",
        "Use repository evidence and governed GitHub actions from Seldrune.",
        "tooling",
        25,
        "completed",
        (),
        ("github", "tools"),
        evidence_refs=("integration:github",),
    ),
    StageDefinition(
        "tool_registry",
        "Universal tool registry and gateway",
        "Register and invoke tools with policy, secrets, and audit boundaries.",
        "tooling",
        30,
        "completed",
        (),
        ("tools", "backend"),
        evidence_refs=("code:tool_gateway", "code:tool_bootstrap"),
    ),
    StageDefinition(
        "provider_connectors",
        "Provider connector expansion",
        "Connect browser, cloud, email, storage, and deployment providers.",
        "tooling",
        20,
        "pending",
        ("tool_registry",),
        ("integrations", "engineering"),
    ),
    StageDefinition(
        "tool_outcome_memory",
        "Verified tool-outcome memory",
        "Feed external execution evidence into model trust and cognitive learning.",
        "tooling",
        15,
        "pending",
        ("provider_connectors", "unarchi_v37"),
        ("memory", "tools"),
    ),
    StageDefinition(
        "tool_recovery",
        "Cross-provider recovery",
        "Retry or reroute failed external actions without duplicating side effects.",
        "tooling",
        10,
        "pending",
        ("provider_connectors",),
        ("reliability", "tools"),
    ),
    StageDefinition(
        "factory_orchestration",
        "Project orchestration and delivery core",
        "Create tasks, route agents, track project delivery, and preserve evidence.",
        "factory",
        35,
        "completed",
        (),
        ("orchestration", "delivery"),
        evidence_refs=("code:orchestrator", "code:project_delivery"),
    ),
    StageDefinition(
        "factory_dependency_graph",
        "Dependency-aware parallel mission planning",
        "Compute readiness from dependencies and expose simultaneous safe lanes.",
        "factory",
        20,
        "completed",
        ("factory_orchestration",),
        ("planning", "orchestration"),
        evidence_refs=("feature:cognitive-mission-board",),
    ),
    StageDefinition(
        "factory_build_test",
        "Automated build-test-fix loop",
        "Create code, run tests, inspect failures, patch, and retry with evidence.",
        "factory",
        20,
        "pending",
        ("factory_dependency_graph", "model_verifier_fallback"),
        ("engineering", "validation"),
    ),
    StageDefinition(
        "factory_deploy",
        "Automated deployment verification",
        "Deploy approved builds and verify health, rollback, and evidence receipts.",
        "factory",
        15,
        "pending",
        ("factory_build_test", "provider_connectors"),
        ("deployment", "validation"),
    ),
    StageDefinition(
        "factory_acceptance",
        "Acceptance-driven autonomous delivery",
        "Continue until measurable acceptance criteria are met or policy blocks work.",
        "factory",
        10,
        "pending",
        ("factory_deploy", "unarchi_v34"),
        ("planning", "validation"),
    ),
)


def _validate_definitions() -> None:
    workstreams = {item.id: item for item in WORKSTREAMS}
    if sum(item.weight for item in WORKSTREAMS) != 100:
        raise ValueError("workstream weights must sum to 100")

    stages = {item.id: item for item in STAGES}
    if len(stages) != len(STAGES):
        raise ValueError("development mission stage IDs must be unique")

    for stream_id in workstreams:
        stage_weight = sum(
            item.weight for item in STAGES if item.workstream == stream_id
        )
        if stage_weight != 100:
            raise ValueError(
                f"stage weights for workstream {stream_id} must sum to 100"
            )

    for stage in STAGES:
        if stage.workstream not in workstreams:
            raise ValueError(f"unknown workstream {stage.workstream}")
        for dependency in stage.depends_on:
            if dependency not in stages:
                raise ValueError(
                    f"stage {stage.id} has unknown dependency {dependency}"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> None:
        if stage_id in visited:
            return
        if stage_id in visiting:
            raise ValueError("development mission dependency graph contains a cycle")
        visiting.add(stage_id)
        for dependency in stages[stage_id].depends_on:
            visit(dependency)
        visiting.remove(stage_id)
        visited.add(stage_id)

    for stage_id in stages:
        visit(stage_id)


_validate_definitions()


def build_development_mission(
    verified_stage_ids: set[str] | None = None,
    dynamic_evidence_refs: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    workstreams = {item.id: item for item in WORKSTREAMS}
    dynamically_verified = verified_stage_ids or set()
    dynamic_refs = dynamic_evidence_refs or {}
    completed = {
        stage.id
        for stage in STAGES
        if stage.status == "completed" or stage.id in dynamically_verified
    }

    stage_rows: list[dict[str, Any]] = []
    ready_stage_ids: list[str] = []
    blocked_stage_ids: list[str] = []
    paused_stage_ids: list[str] = []

    for stage in STAGES:
        stream = workstreams[stage.workstream]
        dependencies_complete = all(
            dependency in completed for dependency in stage.depends_on
        )
        paused = stream.paused or bool(stage.paused_reason)
        effective_completed = stage.id in completed
        ready = not effective_completed and dependencies_complete and not paused
        if ready:
            ready_stage_ids.append(stage.id)
        elif not effective_completed:
            blocked_stage_ids.append(stage.id)
        if paused and not effective_completed:
            paused_stage_ids.append(stage.id)

        stage_rows.append(
            {
                "id": stage.id,
                "title": stage.title,
                "objective": stage.objective,
                "workstream": stage.workstream,
                "weight": stage.weight,
                "status": "completed" if effective_completed else "pending",
                "depends_on": list(stage.depends_on),
                "dependencies_complete": dependencies_complete,
                "ready": ready,
                "paused": paused,
                "paused_reason": (
                    stage.paused_reason or stream.paused_reason
                ),
                "capabilities": list(stage.capabilities),
                "execution_mode": stage.execution_mode,
                "evidence_refs": [
                    *stage.evidence_refs,
                    *dynamic_refs.get(stage.id, []),
                ],
                "completion_source": (
                    "runtime_verified"
                    if stage.id in dynamically_verified
                    and stage.status != "completed"
                    else "roadmap_evidence"
                    if stage.status == "completed"
                    else None
                ),
            }
        )

    stream_rows: list[dict[str, Any]] = []
    overall_weighted_basis = 0
    for stream in WORKSTREAMS:
        stream_stages = [
            stage for stage in STAGES if stage.workstream == stream.id
        ]
        completed_weight = sum(
            stage.weight
            for stage in stream_stages
            if stage.id in completed
        )
        percentage = float(completed_weight)
        overall_weighted_basis += completed_weight * stream.weight
        stream_rows.append(
            {
                "id": stream.id,
                "title": stream.title,
                "weight": stream.weight,
                "percentage": round(percentage, 1),
                "completed_percentage": round(percentage, 1),
                "remaining_percentage": round(100 - percentage, 1),
                "paused": stream.paused,
                "paused_reason": stream.paused_reason,
                "completed_stage_count": sum(
                    stage.id in completed for stage in stream_stages
                ),
                "stage_count": len(stream_stages),
            }
        )

    execution_wave = [
        row for row in stage_rows if row["id"] in ready_stage_ids
    ]
    overall = ((overall_weighted_basis + 5) // 10) / 10
    return {
        "kind": MISSION_KIND,
        "version": MISSION_VERSION,
        "title": MASTER_TASK_TITLE,
        "status": "paused_tracks_and_active_backlog",
        "percentage_basis": (
            "Weighted roadmap milestones with evidence-backed completed stages; "
            "this is not a benchmark of general intelligence."
        ),
        "overall_percentage": round(overall, 1),
        "completed_percentage": round(overall, 1),
        "remaining_percentage": round(100 - overall, 1),
        "workstreams": stream_rows,
        "stages": stage_rows,
        "parallel_ready_stage_ids": ready_stage_ids,
        "parallel_ready_stages": execution_wave,
        "blocked_stage_ids": blocked_stage_ids,
        "paused_stage_ids": paused_stage_ids,
        "execution_policy": {
            "single_go_intent": True,
            "dependency_guard": True,
            "parallel_ready_planning": True,
            "evidence_gate": True,
            "auto_queue_ready_stages": True,
            "auto_execute_external_actions": False,
            "reason": (
                "External actions require connected providers, reversible "
                "execution controls, and verifiable completion evidence."
            ),
        },
    }


def _verified_runtime_stage_evidence(
    session: Session,
    *,
    organization_id: UUID,
    master_task_id: UUID,
) -> tuple[set[str], dict[str, list[str]]]:
    verified: set[str] = set()
    evidence_refs: dict[str, list[str]] = {}
    tasks = list(
        session.scalars(
            select(Task).where(Task.organization_id == organization_id)
        )
    )
    for task in tasks:
        input_data = task.input_data or {}
        if input_data.get("master_mission_task_id") != str(master_task_id):
            continue
        stage_id = input_data.get("cognitive_mission_stage_id")
        if not stage_id:
            continue
        output = task.output_data or {}
        verification = (
            output.get("cognitive_verification")
            if isinstance(output, dict)
            else None
        )
        if not (
            isinstance(verification, dict)
            and verification.get("status") == "verified"
        ):
            continue
        evidence_valid, _reason, refs = verify_task_completion_evidence(
            session,
            task=task,
        )
        if not evidence_valid:
            continue
        stage_key = str(stage_id)
        verified.add(stage_key)
        evidence_refs[stage_key] = refs
    return verified, evidence_refs


def _contract_requires_verified_upstream_commit(
    contract: dict[str, Any],
) -> bool:
    for step in contract.get("steps") or []:
        if not isinstance(step, dict):
            continue
        bindings = step.get("bindings")
        if not isinstance(bindings, dict):
            continue
        if "upstream.verified_commit_sha" in bindings.values():
            return True
    return False


def _verified_dependency_commit_evidence(
    session: Session,
    *,
    organization_id: UUID,
    master_task_id: UUID,
    dependency_stage_ids: list[str],
) -> dict[str, Any] | None:
    dependency_ids = {
        str(stage_id)
        for stage_id in dependency_stage_ids
        if str(stage_id).strip()
    }
    if not dependency_ids:
        return None

    candidates: list[dict[str, Any]] = []
    tasks = list(
        session.scalars(
            select(Task).where(Task.organization_id == organization_id)
        )
    )
    for task in tasks:
        input_data = task.input_data or {}
        if input_data.get("master_mission_task_id") != str(master_task_id):
            continue
        stage_id = str(input_data.get("cognitive_mission_stage_id") or "")
        if stage_id not in dependency_ids:
            continue
        if TaskStatus(task.status) is not TaskStatus.SUCCEEDED:
            continue

        output = task.output_data or {}
        verification = (
            output.get("cognitive_verification")
            if isinstance(output, dict)
            else None
        )
        if not (
            isinstance(verification, dict)
            and verification.get("status") == "verified"
        ):
            continue

        evidence_valid, _reason, refs = verify_task_completion_evidence(
            session,
            task=task,
        )
        if not evidence_valid:
            continue

        chain = output.get("contract_chain")
        receipts = (
            chain.get("receipts")
            if isinstance(chain, dict)
            else None
        )
        if not isinstance(receipts, list):
            continue

        for receipt in receipts:
            if not isinstance(receipt, dict):
                continue
            if receipt.get("step_id") != "merge-verified-pull-request":
                continue
            try:
                tool_run_id = UUID(str(receipt.get("tool_run_id") or ""))
            except ValueError:
                continue
            run = session.get(ToolRun, tool_run_id)
            if run is None:
                continue
            if (
                run.organization_id != organization_id
                or run.status != ToolRunStatus.SUCCEEDED.value
            ):
                continue
            tool_output = run.output_data or {}
            if not (
                isinstance(tool_output, dict)
                and tool_output.get("merged") is True
            ):
                continue
            commit_sha = str(tool_output.get("sha") or "").strip()
            if not commit_sha:
                continue

            completed_at = (
                run.completed_at
                or task.completed_at
                or task.updated_at
                or task.created_at
            )
            candidates.append(
                {
                    "verified_commit_sha": commit_sha,
                    "source_stage_id": stage_id,
                    "source_task_id": str(task.id),
                    "source_tool_run_id": str(run.id),
                    "completed_at": (
                        completed_at.isoformat()
                        if completed_at is not None
                        else ""
                    ),
                    "evidence_refs": sorted(set(refs)),
                }
            )

    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            str(item["completed_at"]),
            str(item["source_tool_run_id"]),
        )
    )
    selected = dict(candidates[-1])
    selected["source"] = "verified_dependency_merge_receipt"
    return selected


def current_development_mission(
    session: Session,
    *,
    organization_id: UUID,
) -> tuple[dict[str, Any], Task | None]:
    candidates = list(
        session.scalars(
            select(Task)
            .where(
                Task.organization_id == organization_id,
                Task.title == MASTER_TASK_TITLE,
            )
            .order_by(Task.created_at.desc())
        )
    )
    master_task = next(
        (
            item
            for item in candidates
            if (item.input_data or {}).get("mission_kind") == MISSION_KIND
            and TaskStatus(item.status) not in TERMINAL_TASK_STATUSES
        ),
        None,
    )
    if master_task is None:
        return build_development_mission(), None

    verified, refs = _verified_runtime_stage_evidence(
        session,
        organization_id=organization_id,
        master_task_id=master_task.id,
    )
    return build_development_mission(verified, refs), master_task


def sync_development_mission_task(
    session: Session,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
) -> tuple[Task, dict[str, Any], bool]:
    candidates = list(
        session.scalars(
            select(Task)
            .where(
                Task.organization_id == organization_id,
                Task.title == MASTER_TASK_TITLE,
            )
            .order_by(Task.created_at.desc())
        )
    )
    task = next(
        (
            item
            for item in candidates
            if (item.input_data or {}).get("mission_kind") == MISSION_KIND
        ),
        None,
    )
    created = False
    if task is None or TaskStatus(task.status) in TERMINAL_TASK_STATUSES:
        task = Task(
            organization_id=organization_id,
            created_by_user_id=actor_user_id,
            title=MASTER_TASK_TITLE,
            objective=(
                "Maintain the complete Seldrune development roadmap, dependency "
                "graph, parallel-ready lanes, and evidence-backed percentages."
            ),
            priority=100,
            status=TaskStatus.QUEUED.value,
            input_data={},
        )
        session.add(task)
        session.flush()
        created = True

    verified, refs = _verified_runtime_stage_evidence(
        session,
        organization_id=organization_id,
        master_task_id=task.id,
    )
    mission = build_development_mission(verified, refs)

    task.input_data = {
        "mission_kind": MISSION_KIND,
        "mission_version": MISSION_VERSION,
        "overall_percentage": mission["overall_percentage"],
        "remaining_percentage": mission["remaining_percentage"],
        "parallel_ready_stage_ids": mission["parallel_ready_stage_ids"],
        "paused_stage_ids": mission["paused_stage_ids"],
        "snapshot": mission,
    }
    existing_output = dict(task.output_data or {})
    task.output_data = {
        **existing_output,
        "progress": {
            "completed_percentage": mission["completed_percentage"],
            "remaining_percentage": mission["remaining_percentage"],
        },
        "parallel_ready_stage_ids": mission["parallel_ready_stage_ids"],
    }
    session.add(
        TaskEvent(
            organization_id=organization_id,
            task_id=task.id,
            actor_user_id=actor_user_id,
            event_type=(
                "cognitive_mission.created"
                if created
                else "cognitive_mission.synced"
            ),
            details={
                "mission_version": MISSION_VERSION,
                "overall_percentage": mission["overall_percentage"],
                "parallel_ready_stage_ids": mission["parallel_ready_stage_ids"],
                "paused_stage_ids": mission["paused_stage_ids"],
                "runtime_verified_stage_ids": sorted(verified),
            },
        )
    )
    session.commit()
    session.refresh(task)
    compile_mission_stage_contracts(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        master_task=task,
        mission=mission,
    )
    return task, mission, created


def compile_mission_stage_contracts(
    session: Session,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    master_task: Task,
    mission: dict[str, Any] | None = None,
) -> list[Task]:
    mission_snapshot = mission
    if mission_snapshot is None:
        verified, refs = _verified_runtime_stage_evidence(
            session,
            organization_id=organization_id,
            master_task_id=master_task.id,
        )
        mission_snapshot = build_development_mission(verified, refs)

    stages = {
        str(stage["id"]): stage
        for stage in mission_snapshot["stages"]
    }
    tasks = list(
        session.scalars(
            select(Task).where(Task.organization_id == organization_id)
        )
    )
    updated: list[Task] = []
    for task in tasks:
        input_data = dict(task.input_data or {})
        if input_data.get("master_mission_task_id") != str(master_task.id):
            continue
        stage_id = input_data.get("cognitive_mission_stage_id")
        stage = stages.get(str(stage_id)) if stage_id else None
        if stage is None:
            continue
        if (
            input_data.get("compiled_execution_contract") is not None
            and TaskStatus(task.status) is not TaskStatus.QUEUED
        ):
            continue

        contract = compile_stage_execution_contract(
            session,
            organization_id=organization_id,
            stage=stage,
        )
        next_input_data = {
            **input_data,
            "compiled_execution_contract": contract,
        }
        if _contract_requires_verified_upstream_commit(contract):
            upstream_evidence = _verified_dependency_commit_evidence(
                session,
                organization_id=organization_id,
                master_task_id=master_task.id,
                dependency_stage_ids=[
                    str(item) for item in stage.get("depends_on") or []
                ],
            )
            if upstream_evidence is None:
                next_input_data.pop("upstream_evidence", None)
            else:
                next_input_data["upstream_evidence"] = upstream_evidence

        if input_data == next_input_data:
            continue

        task.input_data = next_input_data
        session.add(
            TaskEvent(
                organization_id=organization_id,
                task_id=task.id,
                actor_user_id=actor_user_id,
                event_type="cognitive_mission.stage_compiled",
                details={
                    "stage_id": stage["id"],
                    "contract_version": contract["version"],
                    "profile": contract["profile"],
                    "executable_now": contract["executable_now"],
                    "blocking_reasons": contract["blocking_reasons"],
                },
            )
        )
        updated.append(task)

    if updated:
        session.commit()
        for task in updated:
            session.refresh(task)
    return updated


def queue_parallel_ready_stages(
    session: Session,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    master_task: Task,
) -> list[Task]:
    verified, refs = _verified_runtime_stage_evidence(
        session,
        organization_id=organization_id,
        master_task_id=master_task.id,
    )
    mission = build_development_mission(verified, refs)
    existing = list(
        session.scalars(
            select(Task).where(Task.organization_id == organization_id)
        )
    )
    existing_stage_ids = {
        (task.input_data or {}).get("cognitive_mission_stage_id")
        for task in existing
        if (task.input_data or {}).get("master_mission_task_id")
        == str(master_task.id)
    }

    queued: list[Task] = []
    for stage in mission["parallel_ready_stages"]:
        if stage["id"] in existing_stage_ids:
            continue
        contract = compile_stage_execution_contract(
            session,
            organization_id=organization_id,
            stage=stage,
        )
        input_data: dict[str, Any] = {
            "master_mission_task_id": str(master_task.id),
            "cognitive_mission_stage_id": stage["id"],
            "workstream": stage["workstream"],
            "depends_on": stage["depends_on"],
            "required_capabilities": stage["capabilities"],
            "execution_mode": stage["execution_mode"],
            "evidence_gate_required": True,
            "compiled_execution_contract": contract,
        }
        if _contract_requires_verified_upstream_commit(contract):
            upstream_evidence = _verified_dependency_commit_evidence(
                session,
                organization_id=organization_id,
                master_task_id=master_task.id,
                dependency_stage_ids=[
                    str(item) for item in stage.get("depends_on") or []
                ],
            )
            if upstream_evidence is not None:
                input_data["upstream_evidence"] = upstream_evidence

        task = Task(
            organization_id=organization_id,
            created_by_user_id=actor_user_id,
            title=stage["title"],
            objective=stage["objective"],
            priority=90,
            status=TaskStatus.QUEUED.value,
            input_data=input_data,
        )
        session.add(task)
        session.flush()
        session.add(
            TaskEvent(
                organization_id=organization_id,
                task_id=task.id,
                actor_user_id=actor_user_id,
                event_type="cognitive_mission.stage_queued",
                details={
                    "master_mission_task_id": str(master_task.id),
                    "stage_id": stage["id"],
                    "depends_on": stage["depends_on"],
                },
            )
        )
        queued.append(task)

    session.commit()
    for task in queued:
        session.refresh(task)
    return queued
