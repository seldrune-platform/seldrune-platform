# Seldrune Capability Seed v0.1

## Purpose

Give every Seldrune agent one compact work pattern that helps it turn existing model ability, relevant knowledge, and governed tools into verifiable results. This is runtime instruction transfer: it uses the model already configured for an agent and requires no GPU training job.

## How it fits the current platform

The seed is appended by `backend/app/services/agent_runtime.py` to both default and agent-specific instructions. The existing knowledge layer supplies task-matched organizational knowledge and records its references. The existing skill-evolution and proof services remain responsible for candidate measurement and verified promotion.

The seed does not replace an agent's role, model policy, tool grants, knowledge retrieval, approval gates, or completion-evidence rules.

## The compact work pattern

1. **Target** — identify the requested outcome, constraints, and acceptance evidence.
2. **Context** — use task inputs and relevant retrieved knowledge; keep source claims distinct from assumptions and unknowns.
3. **Transform** — choose the shortest effective path across research, reasoning, coding, data, writing, or operations.
4. **Act** — use only the capabilities and tools available through Seldrune's governed paths.
5. **Prove** — check the result against acceptance evidence. A plan, queued action, or model claim alone is not proof of completion.
6. **Reuse** — turn an evidence-backed successful procedure into a small capsule with a trigger, steps, recovery, and proof requirement. Promote it only through the existing measured skill gates.
7. **Report** — state what was produced, what evidence was checked, and what remains unresolved.

## Skill capsule format

Store reusable procedure separately from large source collections:

```yaml
skill_id: concise-stable-name
trigger: task cues that mean this procedure applies
goal: observable result
steps:
  - reusable action
  - reusable action
evidence: what must be checked before calling it successful
recovery: what to do when a step fails or evidence is missing
sources:
  - stable knowledge or artifact references
evaluation:
  - held-out task identifier
  - measured result
state: candidate | verified
```

The source collection remains in Seldrune knowledge storage. The capsule carries the reusable transformation pattern and points back to its evidence. This avoids copying entire documents into every prompt.

## Five-minute evaluation

Run the same small task set before and after adding the seed, using the same provider, model, inputs, and tool access. Score:

- outcome correctness,
- evidence quality,
- tool/approval compliance,
- successful artifact or test production,
- latency and token cost.

Keep the seed only if it improves the measured result without increasing unsupported completion claims. Record the model, seed version, test identifiers, and evidence references. Use the repository's existing skill-promotion threshold and proof checks; do not label an unmeasured result as a trained capability.

## What this changes

The seed changes agent instructions for each runtime call. It does not modify model weights or create new knowledge from nothing. Its practical effect is to help existing agents reuse their latent abilities more consistently while Seldrune supplies relevant knowledge and governed tools.
