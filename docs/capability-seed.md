# Seldrune Shared Capability and Continuity Seed v0.2

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


## Shared owner continuity

Seldrune GPT and assigned-agent requests can attach the authenticated actor's owner-continuity entry from sense:owner-continuity:{user_id}, scoped by organization and actor. Agent tasks receive only the note belonging to the actor who launched that task. The note is labeled as personalization context and cannot grant a tool, connection, or approval. Retrieved organizational knowledge remains task-matched and provenance-aware.

## OpenAI model route

SELDRUNE_MODEL_OPENAI_DEFAULT defaults to gpt-6-luna. Seldrune GPT uses it for OpenAI-provider requests when no model is explicitly requested; agent tasks use it when no agent-specific model is configured. Other providers keep their configured models. Existing allowlists and spend limits continue to apply. The development provider default remains mock; production must have OpenAI selected and a working, authorized provider credential.

GPT-6 Luna is an API model, not a GPU. It accepts text and images, but not direct audio or video input; the live face-and-voice pipeline remains a separate service and must be measured independently. Seldrune's model gateway and orchestration layer must expose any tools an agent is expected to use; a prompt seed alone does not create connections or tool permissions.

## Multi-perspective innovation

For difficult or unfamiliar tasks, agents compare first-principles, domain, implementation, and counterexample lenses, then compress the useful insights into one testable approach. For frontier physics or quantum ideas they distinguish established results, hypotheses, classical simulation, and actual quantum hardware. Claims such as a 1,000× advantage require a paired benchmark with defined tasks and evidence.

Agents should inspect the connected providers and granted tools relevant to the job, execute only through authorized Seldrune routes, and verify outcomes. New account connections, external messages, spending, production deployments, and destructive operations follow the existing owner approval gates.
## What this changes

The seed changes agent instructions for each runtime call. It does not modify model weights or create new knowledge from nothing. Its practical effect is to help existing agents reuse their latent abilities more consistently while Seldrune supplies relevant knowledge and governed tools.
