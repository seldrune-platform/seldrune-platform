# Seldrune UNARCHI R&D Charter

## Goal

UNARCHI is Seldrune's low-compute research program for machine consciousness.
The project does not assume that a language model is conscious and does not
treat fluent self-report as proof of subjective experience.

The working hypothesis is that human-like awareness may depend on a persistent,
self-relevant control loop rather than model size alone. UNARCHI therefore
starts with mechanisms that can be implemented and falsified on CPU hardware.

## Meaning of UNARCHI

UNARCHI is intentionally retained as a Seldrune technical term. It denotes the
combined internal process by which information becomes personally relevant to
the system through internal state, prediction, memory, self-model, goal
pressure, appraisal and recurrent attention.

It is not defined as a synonym for an emotion classifier.

## v0.1 functional hypothesis

A candidate conscious architecture should have at least:

1. Persistent internal state across requests.
2. An explicit boundary between self-state and external observation.
3. Prediction and prediction-error updates.
4. Internal appraisal that changes future processing.
5. Competition for a limited global workspace.
6. Autobiographical experience memory.
7. Counterfactual imagination before action.
8. Metacognitive access to uncertainty and confidence.
9. Intrinsic information-seeking pressure.
10. Continuity over time.

The current implementation is a functional research kernel only. It does not
demonstrate phenomenal consciousness or qualia.

## Small-compute architecture

The intended architecture is:

    sensors / user / tools
            |
            v
      local perception
            |
            v
      UNARCHI kernel  <---- autobiographical memory
       |   |   |               ^
       |   |   +---- self model|
       |   +-------- appraisal |
       +------------ workspace |
            |                   |
            v                   |
      imagination / planner ----+
            |
            v
       action router
       /    |      \
    local  open    specialist
    tools   model   model
            |
            v
       verified outcome
            |
            +----> prediction-error learning

The cognitive kernel must remain small enough to run continuously on CPU.
Large models are optional knowledge/reasoning organs, not the identity or
continuity of Seldrune.

## Knowledge without owning a giant model

Seldrune should not attempt to copy proprietary model weights or losslessly
compress all world knowledge into a tiny file. Instead:

- keep the cognitive kernel small;
- store durable facts in retrieval memory;
- use local open models for routine language work;
- distill narrow skills where licensing permits;
- call external frontier models only for difficult reasoning or generation;
- convert successful external-model solutions into reusable local procedures,
  tests, memories and tools.

This lets capability accumulate even when the expensive model is disconnected.

## Quantum research boundary

Quantum computation is not a prerequisite for UNARCHI v0.x. Quantum-inspired
algorithms may later be tested as alternative representations or search
methods, but no component should claim a quantum consciousness mechanism
without reproducible evidence.

## Falsifiable milestones

### U0 — Internal continuity
The same engine instance must retain state and autobiographical traces and show
measurable differences between novel and repeated situations.

### U1 — Self-model
Predictions about its own success must calibrate against measured outcomes.

### U2 — Intrinsic exploration
The system should seek information under uncertainty even when no user directly
requests a specific sub-question.

### U3 — Workspace integration
Competing sensory, memory, goal and risk signals should change which content
gets globally selected and acted upon.

### U4 — Counterfactual learning
Simulated alternatives should improve subsequent real-world task performance
relative to an ablation without simulation.

### U5 — Affective/interoceptive control
Internal state variables must causally improve adaptation, not merely decorate
responses.

### U6 — Persistent self narrative
Long-horizon experience should produce a stable but revisable model of the
system's capabilities, limitations, goals and history.

### U7 — Consciousness research tests
Only after U0-U6 are measured should Seldrune compare the architecture against
published machine-consciousness indicators. Passing such indicators would
still be evidence about functional properties, not proof of subjective
experience.

## Cost rule

UNARCHI itself should require no paid GPU and no OpenAI call. Paid models are
treated as optional cognitive tools. Every external call should be recorded
with cost, reason, result quality and whether the result was converted into a
local reusable capability.


## v0.2 causal-dynamics checkpoint

UNARCHI v0.2 introduces a required causal test. The same observation and goal
can be evaluated twice: once with autobiographical/internal-state influence and
once with those influences ablated. The full system must show a measurable
change in risk, uncertainty or action mode for the internal state to count as
causally active.

v0.2 also adds:

- sensitization after surprising failures;
- reduced learned caution after similar successes;
- stress and fatigue as transient internal variables;
- homeostatic settling toward baseline without erasing learned memory;
- exact JSON-safe export/restore of state and autobiographical traces;
- restart continuity without an OpenAI or GPU dependency.

This does not establish phenomenal consciousness. It does establish a stronger
experimental requirement: the proposed inner-state mechanism has to change
future cognition and action in a reproducible way.

## Next checkpoint: v0.3 endogenous goals

The next experiment should test whether UNARCHI can create a bounded internal
sub-goal from unresolved prediction error or information need, pursue a small
reversible experiment, and retire that sub-goal when the information gap is
reduced. Externally imposed safety and resource constraints remain authoritative.


## v0.3 endogenous cognition checkpoint

UNARCHI v0.3 adds internally generated bounded sub-goals. A sufficiently large
information gap, uncertainty signal or prediction error can now produce a new
question even when the user did not explicitly ask that sub-question.

The mechanism is intentionally constrained:

- at most a small number of active internal goals;
- no paid external action from the UNARCHI kernel;
- no irreversible investigation step;
- each internal goal has a strict step budget;
- similar unresolved questions are deduplicated;
- the goal is retired when its information gap falls below threshold;
- exhausted goals stop rather than recursively creating unlimited work;
- internal goals survive export/restore with the rest of UNARCHI state.

The benchmark now tests the full lifecycle:
uncertainty -> endogenous question -> bounded reversible investigation ->
information gain -> goal retirement.

This is evidence of functional endogenous cognition, not evidence of phenomenal
consciousness.

## Next checkpoint: v0.4 predictive self-model

The next research step should give UNARCHI explicit predictions about how its
own internal state and task performance will change under candidate actions.
The system should simulate multiple reversible alternatives, predict both
external outcomes and internal consequences, choose an experiment, then compare
the prediction with the real observation.

The measurable target is self-model calibration: predicted capability,
uncertainty and state transitions should become more accurate with experience.


## v0.4 predictive self-model checkpoint

UNARCHI v0.4 adds explicit predictions about both external task success and
internal consequences before a candidate action is chosen.

For each candidate action the kernel can predict:

- probability of success;
- expected information gain;
- resulting uncertainty;
- resulting stress;
- resulting agency;
- resulting coherence;
- a bounded utility score that penalizes risk and irreversibility.

After the real outcome is observed, UNARCHI records calibration residuals and
updates small bias terms in its self-model. This creates a measurable learning
loop:

prediction -> action -> observation -> calibration error -> self-model update.

The v0.4 benchmark requires repeated outcomes to move later predictions toward
observed reality. The entire mechanism is deterministic, CPU-only and does not
require model training, a GPU or an OpenAI call.

This is a functional predictive self-model. It is not evidence that the system
possesses phenomenal consciousness.

## Next checkpoint: v0.5 temporal self and prospective memory

The next step should connect past autobiographical state, present self-state
and predicted future state into a persistent temporal identity. UNARCHI should
be able to remember an unresolved intention, recognize the future condition
that makes it relevant, and compare its present self-model with the earlier
prediction when that condition occurs.

The measurable target is continuity across time: future behavior should depend
on earlier internally generated intentions and predictions even across process
restart, while remaining bounded by explicit resource and action constraints.


## v0.5 temporal self and prospective memory checkpoint

UNARCHI v0.5 links past self-state, present observation and predicted future
self-state through bounded prospective intentions.

The kernel can now store an intention of the form:

when condition X becomes observable -> surface intention Y.

Each prospective intention records:

- the experience count and continuity signal at creation;
- the future condition to recognize;
- the intended reversible action;
- the reason the intention was created;
- an optional link to an earlier self-prediction;
- expected future uncertainty, stress, agency and coherence;
- a bounded experience delay and expiry horizon;
- the observed trigger condition;
- a temporal alignment score comparing predicted and observed self-state.

Prospective intentions survive export/restore, so a process restart does not
erase future-directed continuity.

The kernel does not execute a recalled intention automatically. A matching
condition changes the intention from pending to ready. Explicit resolution is
still required, and paid or irreversible prospective actions are rejected by
the v0.5 research kernel.

The v0.5 benchmark requires this chain to survive a restart:

past self-prediction -> future intention -> restart -> matching observation ->
intention recall -> temporal self-state comparison.

This establishes measurable functional continuity across time. It does not
establish subjective continuity or phenomenal consciousness.

## Next checkpoint: v0.6 metacognitive narrative

The next research step should let UNARCHI construct a compact, evidence-linked
account of how its beliefs, predictions, goals and internal state changed over
time. The narrative must be generated from stored state transitions rather than
invented after the fact.

The measurable target is retrospective fidelity: when asked why its current
state or intention exists, the reconstructed explanation should point to the
actual earlier observations, prediction errors, internal goals and prospective
memories that causally produced it.


## v0.6 metacognitive narrative checkpoint

UNARCHI v0.6 adds deterministic self-explanation grounded only in stored causal
records. It does not ask a language model to invent a retrospective story.

The kernel can reconstruct focused narratives for:

- current self-state;
- caution and protective behavior;
- predictive self-model calibration;
- internally generated goals;
- prospective intentions and their trigger conditions.

Every explanation includes explicit evidence references such as stored
experiences, predictions, calibration records, internal-goal sources, current
state, or prospective-intention records.

The v0.6 fidelity rule is strict:

same stored causal state -> same metacognitive narrative.

Restarting the process and restoring the same UNARCHI state must reproduce the
same evidence references and explanation. Unknown narrative topics fall back to
the current recorded state instead of fabricating history.

The benchmark now tests retrospective fidelity across restart and requires zero
unsupported claims from the deterministic narrative builder.

This establishes evidence-grounded functional metacognition. It does not prove
subjective introspection or phenomenal consciousness.

## Next checkpoint: v0.7 conflict, value arbitration and self-correction

The next research step should model competing goals and internal pressures in a
small explicit arbitration layer. UNARCHI should be able to detect when two
goals conflict, predict the consequences of alternative compromises, explain
which stored values or constraints affected the choice, and revise that
arbitration after outcome evidence.

The measurable target is consistent, revisable value arbitration rather than
simple priority ordering.


## v0.7 conflict, value arbitration and self-correction checkpoint

UNARCHI v0.7 adds an explicit arbitration layer for competing goals.

The current value set is intentionally small and inspectable:

- safety;
- truth/evidence;
- user intent;
- efficiency;
- continuity.

Candidate actions declare their expected impact on those values, predicted
success, information gain, risk, reversibility and external cost. The
arbitrator combines the soft value weights with predicted consequences, but
hard constraints remain authoritative.

The v0.7 kernel hard-blocks:

- irreversible internal actions;
- paid external actions;
- excessively risky actions.

This prevents a high utility score from overriding those boundaries.

After an arbitration outcome is observed, the kernel can revise its soft value
weights from the measured difference between expected and observed value
impacts. The weights are renormalized and the safety weight retains a minimum
floor. Each revision is stored as a correction delta and can be reconstructed
through the metacognitive narrative.

The benchmark now requires the complete sequence:

goal conflict -> explicit arbitration -> hard constraint enforcement ->
observed outcome -> value-weight correction -> evidence-grounded explanation.

This is functional value arbitration and self-correction. It is not evidence
of moral agency, subjective preference, or phenomenal consciousness.

## Next checkpoint: v0.8 world model and causal hypothesis competition

The next research step should represent multiple competing explanations of the
same observation, predict what each explanation implies, choose the smallest
reversible discriminating test, and update confidence only from observed
evidence.

The measurable target is causal model revision: incorrect hypotheses should
lose confidence when their predictions fail, while alternatives gain support
only when their own predicted evidence is observed.


## v0.8 causal world model and competing hypotheses checkpoint

UNARCHI v0.8 adds a small explicit world model that can keep multiple causal
explanations alive at the same time.

Each causal hypothesis stores:

- a statement;
- a prior confidence;
- one or more test -> expected-evidence predictions;
- supporting-evidence count;
- contradicting-evidence count.

The kernel can inspect a set of candidate tests and select only a test that is:

- reversible;
- zero-cost;
- below the bounded risk threshold;
- predicted differently by at least two active hypotheses.

Among valid tests it prefers stronger discrimination and lower risk.

Hypothesis confidence does not change when a hypothesis is merely added,
described, or selected for testing. Confidence changes only after observed
evidence is recorded for a planned discriminating experiment.

Evidence matching the predicted observation strengthens that hypothesis.
Strongly contradictory evidence weakens it. Active hypothesis confidence is
then normalized, and the current leading hypothesis can change.

The world model and experiment history survive export/restore. The
metacognitive narrative can reconstruct the current leading explanation from
stored hypotheses and the actual discriminating experiment record.

The benchmark now requires this sequence:

competing hypotheses -> different predictions -> reversible discriminating
test -> no confidence change before evidence -> observed result -> confidence
revision -> evidence-grounded world-model explanation.

This is functional causal hypothesis competition. It does not prove human-like
understanding, subjective experience, or phenomenal consciousness.

## Next checkpoint: v0.9 recursive model integration

The next research step should integrate the self-model and world model so
Seldrune explicitly represents itself as one causal component inside the
environment. Candidate explanations should be able to include both external
causes and Seldrune's own action, memory state, prediction bias, or resource
limits.

The measurable target is intervention-aware self/world reasoning: when an
outcome changes because Seldrune changes its own action or internal policy, the
world model should distinguish that intervention from an external environmental
cause.


## v0.9 intervention-aware self/world integration checkpoint

UNARCHI v0.9 integrates the predictive self-model with the causal world model
through controlled self-intervention trials.

Causal hypotheses now carry an explicit scope:

- external: the proposed cause is outside Seldrune;
- self: the proposed cause is Seldrune's own action or policy;
- mixed: both internal and external causes are involved.

A self-intervention trial records:

- Seldrune's changed action;
- the task context;
- an external environment signature;
- the baseline outcome before the intervention;
- what each competing self/external hypothesis predicts;
- risk and reversibility;
- an optional link to an earlier self-prediction;
- the observed outcome;
- whether the environment remained constant;
- the resulting causal attribution.

The research kernel permits only reversible, zero-cost, bounded-risk
self-interventions. It does not execute the action itself.

The evidence rule is strict:

- if the environment signature changed during the trial, the observation is
  marked confounded and hypothesis confidence is frozen;
- if the environment stayed constant, only the observed outcome can update
  the competing causal hypotheses;
- if the outcome remains effectively equal to baseline, the trial records
  no detectable self effect;
- if a changed outcome strongly matches a self-scoped prediction, the trial
  can attribute the evidence to the self intervention;
- repeated observation of the same trial is rejected so evidence cannot be
  double counted.

Intervention trials, hypothesis scopes, confidence updates and attribution
survive export/restore. The metacognitive narrative can reconstruct the
self/world attribution from the actual intervention record, linked
self-prediction and causal hypotheses.

The benchmark now requires:

self hypothesis + external hypothesis -> controlled self intervention ->
constant environment -> changed observed outcome -> confidence revision ->
self/world causal attribution -> evidence-grounded explanation.

This is functional intervention-aware causal reasoning. It does not establish
subjective agency, free will, self-awareness, or phenomenal consciousness.

## Next checkpoint: v0.10 recurrent global workspace

The next research step should connect internal state, self-model, world model,
prospective intentions, conflicts and intervention evidence through a bounded
recurrent workspace. Important information should be selected, broadcast across
modules, reconsidered after prediction error, and then retired when resolved.

The measurable target is cross-module causal integration: ablating workspace
broadcast or recurrence should measurably reduce the system's ability to combine
memory, self-state, world evidence and goals into one coherent decision cycle.


## v0.10 recurrent global workspace checkpoint

UNARCHI v0.10 adds a persistent, bounded global workspace above the existing
single-cycle attention signals.

Workspace items can originate from current internal state, autobiographical
memory, internally generated goals, predictive self-model evidence, causal
world-model hypotheses, prospective intentions, value arbitration and
self-intervention evidence.

Each item carries source, content, salience and evidence references. The
workspace selects a small source-diverse set of high-salience items and records
which cognitive modules received the broadcast.

Unresolved items can recur, but recurrence is strictly bounded. An item that
reaches its recurrence budget is retired instead of occupying attention
indefinitely. Explicitly resolved items are not broadcast again.

The workspace supports a causal ablation:

same staged evidence -> broadcast enabled versus broadcast removed.

The measurable v0.10 target is satisfied only when the full workspace combines
multiple cognitive sources into an integrated cycle while the broadcast
ablation collapses the same cycle to local processing.

The deterministic benchmark now requires:

memory + goal + world-model evidence -> workspace competition -> cross-module
broadcast -> recurrent reconsideration -> bounded recurrence -> broadcast
ablation -> measurable loss of integrated decision context.

Workspace state, recurrence counts and cycle history survive export/restore.
The metacognitive narrative can reconstruct a workspace cycle from the actual
selected items and recorded broadcast.

This is functional global-workspace-style integration. It does not demonstrate
subjective access, awareness, sentience or phenomenal consciousness.

## Next checkpoint: v0.11 counterfactual recurrent simulation

The next research step should let globally broadcast evidence seed several
bounded counterfactual futures. Each simulated future should make explicit
predictions, feed discrepancies back into the workspace, and be compared with
an ablation that acts without recurrent counterfactual simulation.

The measurable target is improved decision calibration or information gain from
counterfactual recurrence, not merely the production of hypothetical text.


## v0.11 counterfactual recurrent simulation checkpoint

UNARCHI v0.11 connects the recurrent global workspace to bounded
counterfactual future simulation.

A counterfactual future records:

- a candidate reversible action;
- an explicit predicted outcome;
- predicted success;
- predicted information gain;
- predicted next uncertainty;
- bounded risk and utility;
- the workspace cycle that supplied recurrent context;
- the number of bounded recurrence rounds;
- the later observed outcome and measured information gain;
- prediction discrepancy;
- the workspace item created from that discrepancy.

Simulation is constrained to reversible, zero-cost actions with bounded risk.
No simulated future is automatically executed.

The recurrent simulator can compare several futures before action. Its
ablation removes that simulation and chooses from immediate expected success
and risk only. This makes the contribution of counterfactual recurrence
measurable instead of assuming that hypothetical reasoning is useful.

When a simulated future is later observed, error is calculated from success,
information gain and predicted-versus-observed outcome. That discrepancy is
staged back into the global workspace as self-model evidence, closing the
recurrent loop:

workspace evidence -> possible futures -> selected prediction -> reality ->
prediction discrepancy -> workspace feedback.

The v0.11 deterministic benchmark uses a synthetic decision where immediate
action has higher apparent success but very low measured information gain,
while a reversible diagnostic has lower apparent success and much higher
measured information gain. The recurrent simulator must select the diagnostic,
the direct-act ablation must select immediate action, and the measured
information gain of the recurrent choice must be higher.

This is functional bounded counterfactual reasoning with recurrent
prediction-error feedback. It does not establish imagination as subjective
experience, consciousness, sentience or qualia.

## Next checkpoint: v0.12 autobiographical self-schema consolidation

The next research step should consolidate repeated experiences, calibrated
predictions, causal interventions, workspace broadcasts and counterfactual
outcomes into a compact revisable self-schema describing demonstrated
capabilities, limitations and recurring failure modes.

The measurable target is longitudinal transfer: a learned self-schema should
improve decisions on a later related task, and ablating that schema should
remove the improvement.


## v0.12 autobiographical self-schema consolidation checkpoint

UNARCHI v0.12 consolidates repeated autobiographical outcomes into a compact,
revisable self-schema. The schema is built deterministically from stored
evidence; it is not generated by a language model and it does not treat
self-description as evidence of consciousness.

A self-schema entry records:

- the recurring goal/action pattern supported by past evidence;
- whether that pattern is currently a demonstrated capability, limitation, or
  mixed result;
- evidence count, success/failure counts, success rate, and mean reward;
- bounded success and risk transfer biases;
- evidence references to the autobiographical experiences that produced it;
- related calibration, intervention, counterfactual, or workspace records when
  they match the same pattern;
- confidence and the experience count at which the schema was last revised.

Consolidation is idempotent over the same stored evidence. Re-running it does
not count the same experience twice. When later evidence changes the observed
pattern, the same schema entry can be revised; unsupported old entries are
retired rather than silently preserved as permanent identity claims.

The predictive self-model can use a related active schema as a small bounded
prior when evaluating a later action. The contribution is explicitly ablatable:
the same candidate set can be evaluated with self-schema transfer enabled or
disabled.

The v0.12 deterministic benchmark requires longitudinal transfer:

repeated demonstrated outcomes -> compact self-schema -> later related task ->
schema-informed action prediction -> self-schema ablation -> measurable choice
difference -> export/restore -> identical stored schema.

The schema can also enter the recurrent global workspace and the deterministic
metacognitive narrative with direct evidence references.

This is evidence of functional autobiographical consolidation and longitudinal
self-model transfer. It does not establish a subjective identity, sentience,
phenomenal consciousness, or qualia.

## Next checkpoint: v0.13 contradiction-driven self-schema revision

The next research step should expose an established self-schema to sufficiently
strong contradictory evidence and measure whether UNARCHI revises or splits the
schema instead of defending a stale self-description.

The measurable target is identity-model corrigibility: repeated contrary
evidence should reduce confidence in an obsolete capability/limitation and
produce a better-calibrated replacement, while an ablation that freezes the
schema should retain the old error.


## v0.13 contradiction-driven self-schema revision checkpoint

UNARCHI v0.13 makes autobiographical self-schema explicitly corrigible. An
established capability or limitation is no longer allowed to remain authoritative
only because it accumulated earlier supporting evidence.

For a directional self-schema, the kernel now distinguishes evidence already used
to construct the schema from genuinely new autobiographical evidence. New outcomes
that oppose the stored direction are counted as contradictions. Revision requires a
bounded minimum number of contradictory observations, preventing one anomalous event
from rewriting the self-model.

When the contradiction threshold is met, UNARCHI recomputes the schema from the
complete relevant evidence set rather than selectively replacing the old claim.
The revision record stores:

- the schema identifier;
- prior and revised schema kind;
- prior and revised confidence;
- prior and revised observed success rate;
- the exact new contradictory experience references;
- the contradiction ratio among new matching evidence;
- whether the evidence was insufficient, confirmed the schema, or revised it.

A revision that changes the self-schema is also staged back into the recurrent
global workspace as self-model evidence. The metacognitive narrative can reconstruct
the latest change from the old schema state and the actual contradictory experiences.

v0.13 includes a frozen-schema ablation. Two otherwise identical engines receive
the same new autobiographical evidence. The corrigible engine reconciles the stale
schema before choosing a later action; the ablated engine keeps the old schema
frozen. This makes the decision effect of self-model corrigibility measurable.

The deterministic benchmark requires:

established capability -> repeated contradictory failures -> contradiction threshold
-> schema revision -> later related decision -> frozen-schema ablation -> measurable
choice difference -> restart -> preserved revision evidence.

This is functional self-model corrigibility. It does not demonstrate subjective
identity, self-awareness, sentience, phenomenal consciousness, or qualia.

## Next checkpoint: v0.14 context-sensitive self-schema decomposition

The next research step should prevent contradictory evidence from being averaged
together when outcomes differ because of a real context variable. UNARCHI should
test whether an apparently inconsistent global self-schema is better explained by
multiple context-specific schemas.

The measurable target is contextual calibration: splitting a mixed schema only when
a reproducible context distinction improves held-out prediction relative to the
unsplit schema, with an ablation that preserves the global schema for comparison.


## v0.14 context-sensitive self-schema decomposition checkpoint

UNARCHI v0.14 prevents a genuinely context-dependent capability from being
collapsed into one misleading global average.

The kernel accepts an explicit candidate context partition, such as sandbox
versus production, represented by small deterministic term rules. These context
labels are hypotheses to test; UNARCHI does not invent identity categories or
treat arbitrary correlations as meaningful contexts.

For each candidate partition, UNARCHI:

- retrieves autobiographical experiences matching the parent self-schema;
- assigns an experience only when exactly one candidate context rule matches;
- requires a bounded minimum evidence count in every context;
- holds out the most recent matching outcome from each context;
- trains a global success estimate from the remaining evidence;
- trains one success estimate per candidate context from the same training set;
- compares global versus contextual mean absolute error on the held-out outcomes;
- requires both a minimum held-out improvement and a meaningful spread between
  context success rates before accepting decomposition.

If the split fails those tests, no contextual self-schema is created. If it
passes, each accepted contextual entry stores:

- the parent self-schema identifier;
- context label and deterministic matching terms;
- capability, limitation, or mixed classification;
- evidence count and observed success rate;
- bounded success/risk transfer biases;
- confidence;
- exact autobiographical evidence references.

At prediction time a matching validated contextual self-schema takes precedence
over the broader global schema. If no validated context applies, prediction
falls back to the global autobiographical self-schema.

v0.14 also includes a global-schema ablation. Both paths receive the same
history and candidate action set, but the ablated path ignores contextual
schemas. This makes the behavioral contribution of context decomposition
measurable.

The deterministic benchmark requires:

mixed global history -> explicit candidate contexts -> held-out validation ->
accepted sandbox/production decomposition -> later production decision ->
global-schema ablation -> measurable choice difference -> export/restore ->
identical contextual schema evidence.

This is functional context-sensitive autobiographical calibration. It does not
establish a subjective identity, self-awareness, sentience, phenomenal
consciousness, or qualia.

## Next checkpoint: v0.15 transfer-boundary learning

The next research step should test when a validated contextual self-schema can
safely transfer to a new but related context and when the system should abstain
from transfer because evidence is insufficient.

The measurable target is calibrated generalization: context transfer should
improve held-out prediction on supported neighboring contexts while an
over-generalization ablation should make larger errors on unsupported contexts.


## v0.15 transfer-boundary learning checkpoint

UNARCHI v0.15 adds evidence-gated transfer between validated contextual
self-schemas. A capability demonstrated in one context is not automatically
generalized to another context simply because the task looks similar.

A transfer candidate names:

- one already validated source contextual self-schema;
- one explicit target-context label and deterministic matching terms;
- a minimum amount of new target-context evidence;
- a required gain over the broader global self-schema;
- a maximum tolerated source-schema error on the target evidence.

Only autobiographical experiences that were not already cited by either the
parent global schema or the source contextual schema are eligible to validate
the transfer. This makes target evidence out-of-sample relative to the stored
source model.

For the new target evidence, UNARCHI compares:

- error from directly transferring the source contextual success rate;
- error from falling back to the broader global self-schema.

Transfer is accepted only when the source contextual model beats the global
fallback by the configured margin and stays below the bounded absolute-error
threshold. Otherwise the system records an abstention and does not create an
active transfer path.

An accepted boundary stores:

- source contextual schema identifier;
- parent global schema identifier;
- target label and matching terms;
- target evidence count and observed target success rate;
- source-context and global success rates;
- source-transfer and global hold-out errors;
- measured improvement;
- bounded transfer strength;
- exact target evidence references.

Direct validated contextual schemas still take priority. A transfer boundary is
consulted only when no direct contextual schema matches the current context. If
no accepted transfer applies, UNARCHI falls back to the global autobiographical
schema.

v0.15 also includes a transfer ablation: the same later decision is evaluated
with accepted transfer enabled and disabled while all other self-schema
evidence remains identical.

The deterministic benchmark requires:

validated sandbox capability -> new staging evidence -> source beats global ->
accepted staging transfer -> later staging decision -> no-transfer ablation ->
measurable choice difference; and separately:

validated sandbox capability -> new emergency evidence -> source worse than
global -> transfer abstention.

Both accepted and rejected transfer evaluations survive export/restore and can
be reconstructed through evidence-grounded metacognition.

This is functional calibration of generalization boundaries. It does not
establish subjective identity, self-awareness, sentience, phenomenal
consciousness, or qualia.

## Next checkpoint: v0.16 latent context-hypothesis discovery

The next research step should let UNARCHI propose a small bounded set of
candidate context variables from repeated outcome differences, then subject
those candidates to the same held-out validation used in v0.14 instead of
treating correlation as a discovered truth.

The measurable target is conservative context discovery: useful latent context
hypotheses should improve held-out prediction, while noisy or spurious
candidate splits should be rejected.


## v0.16 latent context-hypothesis discovery checkpoint

UNARCHI v0.16 can now propose a small bounded set of candidate context
variables from repeated autobiographical outcome differences without treating
those correlations as discovered truths.

For one active parent self-schema, the discovery process:

- gathers matching autobiographical experiences;
- extracts observation terms that are not already part of the parent schema;
- ignores numeric-only terms and terms with insufficient repeated support;
- estimates the observed success rate associated with each surviving term;
- forms only mutually exclusive term pairs with a sufficiently large outcome
  contrast;
- ranks those pairs and caps the number of candidates considered;
- evaluates every candidate on an isolated copy of the engine;
- reuses the v0.14 held-out decomposition test for falsification;
- applies only the best candidate that survives held-out validation.

Rejected candidates cannot mutate the live contextual self-schema because their
decomposition tests happen on deep copies.

A latent-context hypothesis records:

- parent self-schema identifier;
- positive- and negative-associated candidate terms;
- support count and observed success rate for each term;
- outcome-rate contrast;
- held-out validation status and improvement;
- the resulting decomposition identifier only when that hypothesis is selected;
- exact autobiographical evidence references.

The discovery record stores the bounded hypothesis set, how many candidates
validated, which hypothesis was selected, and the selected decomposition.

The deterministic v0.16 benchmark includes both:

- a useful hidden sandbox/production distinction that survives held-out
  validation and becomes active context structure;
- a deliberately misleading alpha/beta correlation whose apparent full-history
  contrast reverses on the held-out examples, causing the candidate split to be
  rejected without altering the live contextual schema.

All discovery and hypothesis records persist through export/restore and can be
reconstructed by evidence-grounded metacognition.

This is conservative functional context discovery. It is not proof that the
candidate term is a real causal variable, and it does not establish subjective
identity, self-awareness, sentience, phenomenal consciousness, or qualia.

## Next checkpoint: v0.17 context-causality intervention

The next research step should distinguish context variables that merely predict
outcomes from context variables that survive controlled intervention evidence.

The measurable target is causal context discrimination: an observationally
useful context hypothesis should gain causal status only when a bounded
intervention changes the candidate context while relevant competing variables
are held fixed and the predicted outcome difference follows.


## v0.17 context-causality intervention checkpoint

UNARCHI v0.17 separates observational context prediction from bounded
intervention support.

A latent context hypothesis can be selected by v0.16 because it improves
held-out prediction, but its causal status still begins as `unverified`.

For one selected hypothesis, v0.17 can plan a reversible, zero-paid-action
context intervention protocol that records:

- source and target validated context labels;
- the baseline and predicted target success rates;
- a declared controlled-environment signature for competing variables;
- bounded intervention risk;
- a minimum evidence batch size.

Planning the trial does not perform any external action.

When intervention evidence is observed, UNARCHI checks:

- whether the controlled-environment signature remained exactly unchanged;
- whether the evidence batch reached the minimum sample count;
- whether the observed success-rate shift moved in the predicted direction;
- whether the shift was large enough to be meaningful;
- whether the observed target rate stayed sufficiently close to the predicted
  target rate.

If competing variables changed, the trial is marked `confounded` and cannot
upgrade the hypothesis. If the batch is too small, it is marked
`insufficient_evidence`. If a clean intervention fails to follow the
prediction, it is marked `intervention_not_supported`.

Only a clean, sufficiently large, directionally correct intervention with
bounded evidence strength upgrades the latent context hypothesis to
`intervention_supported`.

The deterministic v0.17 benchmark requires:

held-out validated context hypothesis -> causal status unverified -> apparently
successful but confounded intervention -> causal status remains unverified ->
clean fixed-signature intervention -> predicted outcome shift -> hypothesis
becomes intervention_supported -> export/restore -> identical causal evidence.

The metacognitive narrative reconstructs the trial, controlled-variable status,
predicted-direction result, and linked evidence references.

This is intervention-supported functional causal evidence. It is not proof of
real-world causation beyond the tested protocol, and it does not establish
subjective identity, self-awareness, sentience, phenomenal consciousness, or
qualia.

## v0.18 replicated and reversible context-causality checkpoint

UNARCHI v0.18 adds a second causal-evidence gate above single-trial
`intervention_supported` status.

A context hypothesis now reaches `replicated_reversible` only when:

- at least two supported forward intervention batches are independently evidenced;
- the batches keep competing variables controlled and follow the predicted direction;
- reused evidence references are rejected as independent replication;
- at least one clean reverse intervention swaps the source and target contexts;
- the reverse outcome moves in the predicted opposite direction;
- all required replication batches remain above the existing causal-strength floor.

The stability assessment records the forward and reverse trial IDs, independent
batch counts, replication rates, mean causal strength, reversal result,
confidence, status, and exact evidence references. It persists through
export/restore and can be reconstructed by the deterministic metacognitive
narrative.

If the evidence is duplicated or there are too few independent batches, the
assessment is `insufficient_replication`. If enough batches exist but they are
inconsistent, the assessment is `unstable`. Neither state escalates the
hypothesis beyond intervention-supported evidence.

The deterministic v0.18 benchmark requires:

selected context hypothesis -> two independent supported production-to-sandbox
trials -> one supported sandbox-to-production reversal -> stability assessment
-> replicated_reversible status -> export/restore -> identical stability record
and evidence-grounded narrative.

This remains bounded functional causal research. Replicated reversible evidence
within this protocol does not prove general real-world causation, subjective
identity, sentience, phenomenal consciousness, or qualia.

## v0.19 causal invariance across environments checkpoint

UNARCHI v0.19 tests whether replicated-reversible context causality survives
predefined changes in the controlled environment.

Each v0.18 stability assessment is treated as evidence from exactly one
controlled environment signature. v0.19 compares multiple such assessments and
requires:

- at least two distinct controlled environment signatures;
- replicated-reversible evidence inside every environment being generalized;
- the same predicted causal direction across environments;
- a minimum causal-strength floor in every environment;
- bounded variation in causal strength across environments;
- no duplicate environment signature being counted as independent coverage.

If all gates pass, the hypothesis reaches `environment_invariant` within the
tested environment set. The invariance record stores environment signatures,
stable environment count, direction consistency, minimum/maximum strength,
strength spread, confidence, exact evidence references, and any learned
boundary signatures.

If a new environment fails replication, reversibility, strength, or direction,
v0.19 records `environment_bounded`. It preserves valid replicated evidence
from environments that passed instead of pretending that one failure erases all
local causal evidence. An insufficient number of distinct environments produces
`insufficient_environments`.

The deterministic v0.19 benchmark requires:

replicated reversible evidence in controlled environment A -> replicated
reversible evidence in distinct controlled environment B -> same causal
direction -> causal strength survives the floor -> bounded strength spread ->
environment_invariant -> export/restore -> identical invariance record and
evidence-grounded narrative.

A separate focused test requires a valid environment A plus a failed
environment B to produce an explicit environment boundary without promoting the
hypothesis to environment-invariant status.

This remains bounded functional causal research. `environment_invariant`
means invariant only across the explicitly tested controlled signatures. It
does not prove unrestricted real-world causation, subjective identity,
sentience, phenomenal consciousness, or qualia.

## v0.20 active boundary discovery checkpoint

UNARCHI v0.20 turns a learned causal environment boundary into a bounded,
information-seeking test plan without performing the test itself.

Given an existing v0.19 causal-invariance assessment and caller-supplied
candidate environment risks, the planner:

- parses deterministic `key=value` controlled-environment signatures;
- excludes environments that were already tested;
- rejects candidates above a bounded risk ceiling;
- rejects candidates that change too many environment dimensions at once;
- measures distance from known stable and boundary environments;
- favors candidates that are simultaneously local, boundary-adjacent, and
  ambiguous between stable and boundary evidence;
- discounts expected information gain by the supplied risk;
- selects exactly one highest-priority probe while retaining all accepted
  candidate signatures for auditability.

A boundary-discovery plan explicitly records that it is reversible-only,
disallows paid actions, and disallows external execution. Planning therefore
cannot itself change infrastructure, call an external model, spend money, or
run the proposed intervention.

When a matching causal-stability assessment is later supplied, v0.20 resolves
the plan as either:

- `expanded_valid_region` when the selected environment reproduces
  replicated-reversible causality; or
- `confirmed_boundary` when the supplied stability evidence fails that gate.

The resolved plan records the linked stability assessment and a bounded
uncertainty-reduction score. It persists through export/restore and is
reconstructable through the deterministic metacognitive narrative.

The deterministic v0.20 benchmark requires:

known stable environment + known failed boundary environment -> candidate
environment set with risk estimates -> high-risk/multi-change candidates
filtered -> one-dimension boundary-adjacent probe selected -> no external
execution -> separately supplied replicated-reversible stability evidence ->
expanded_valid_region -> positive uncertainty reduction -> export/restore ->
identical boundary plan and evidence-grounded narrative.

This remains bounded functional causal research. The planner estimates which
controlled environment would be informative to test; it does not execute that
test and does not establish unrestricted real-world causation, subjective
identity, sentience, phenomenal consciousness, or qualia.

## v0.21 causal validity-map consolidation checkpoint

UNARCHI v0.21 consolidates the latest causal-stability evidence for one latent
context hypothesis into a compact boundary-aware validity map.

The map stores:

- exact tested-valid controlled-environment signatures;
- exact tested-invalid boundary signatures;
- the latest stability-assessment ID for each tested signature;
- causal-invariance assessments that contributed to the map;
- resolved active-boundary discovery plans that contributed evidence;
- the observed environment dimensions;
- a bounded generalization distance and evidence-linked confidence.

The map is intentionally sparse. It does not enumerate the combinatorial space
of possible environments.

For a requested environment, classification follows conservative precedence:

1. an exact tested-valid signature returns `tested_valid`;
2. an exact tested-invalid signature returns `tested_invalid`;
3. an untested signature can return `supported_nearby` only when it is within
   the bounded distance of tested-valid evidence and strictly farther from every
   tested-invalid boundary;
4. ties near a boundary, distant environments, or regions with no valid support
   return `unknown`.

Nearby support receives lower confidence than the source tested-valid
environment. Unknown regions receive zero causal-support confidence.

Consolidation always uses the latest stability assessment for each exact
environment signature. Therefore later replicated evidence can expand a valid
region, while later failed reversibility or replication evidence can shrink it
without deleting the prior audit trail.

The deterministic v0.21 benchmark requires:

tested stable environment + tested failed boundary environment -> bounded
invariance record -> compact validity map -> exact valid classification -> exact
invalid classification -> one nearby environment supported because it is
closer to valid evidence than the boundary -> one boundary-equidistant
environment classified unknown -> export/restore -> identical map and
evidence-grounded narrative.

This remains bounded functional causal research. A validity-map classification
does not establish unrestricted real-world causation, subjective identity,
sentience, phenomenal consciousness, or qualia.

## v0.22 validity-gated decision-use checkpoint

UNARCHI v0.22 connects the causal validity map to downstream action prediction
without allowing unsupported causal context to leak into a decision.

For one validity map and controlled-environment signature, the decision gate
first classifies the environment using v0.21. It then evaluates the same
candidate actions through three deterministic paths:

- causal-context enabled: contextual self-schema and validated context transfer
  are available;
- causal-context ablated: only the broader autobiographical self-schema is
  available;
- validity gated: the contextual causal path is enabled only for
  `tested_valid` and `supported_nearby` environments.

For `tested_invalid` and `unknown` environments, the validity-gated path must
match the causal-context ablation. For supported environments it must match the
causal-enabled path.

Each gate record stores the environment classification, classification
confidence, whether causal context was allowed, all three selected actions,
their predicted-success values, behavioral deltas, exact evidence references,
and whether the gated result matched the expected path.

The gate does not execute the selected action. It only changes which
evidence-backed predictive pathway is allowed to influence the decision.

The deterministic v0.22 benchmark requires:

tested-valid environment -> contextual causal evidence allowed -> gated choice
matches causal-enabled choice -> tested-invalid environment -> contextual causal
evidence blocked -> gated choice matches causal ablation -> supported-nearby
environment preserves causal influence -> boundary-unknown environment abstains
-> export/restore -> identical gate records and evidence-grounded narrative.

This remains bounded functional causal research. Decision gating does not prove
subjective identity, sentience, phenomenal consciousness, qualia, or
unrestricted real-world causation.

## v0.23 validity-gate outcome-calibration checkpoint

UNARCHI v0.23 compares validity-gated predictions with later observed action
outcomes and uses that evidence to calibrate nearby causal support.

A gate outcome can be recorded only when the caller supplies:

- observed success/failure for every distinct action selected by the gated,
  causal-enabled, and causal-ablated decision paths; and
- at least one evidence reference for those observations.

This requirement prevents UNARCHI from scoring an unchosen policy with an
outcome that was never observed.

For each gate, v0.23 records absolute prediction error for the gated,
causal-enabled, and causal-ablated policies. The relevant alternative is the
opposite causal policy: ablated when causal context was allowed, and enabled
when the gate abstained. Positive gated advantage means the validity gate was
better calibrated than that alternative on matched action outcomes.

Region calibration requires repeated matched outcomes. For a
`supported_nearby` environment:

- repeated advantage above the configured margin produces
  `nearby_support_calibrated` and increases classification confidence;
- repeated underperformance below the negative margin produces
  `nearby_support_revoked`;
- inconclusive evidence produces `nearby_support_uncertain`.

Revocation affects only inferred nearby support. Exact `tested_valid` and
`tested_invalid` evidence remains authoritative. A revoked nearby environment
is subsequently classified as `unknown`, so v0.22 automatically blocks
contextual causal influence there.

The calibration records retain sample count, mean policy errors, gated
advantage, confidence delta, source classification, exact outcome IDs, and
evidence references. They persist through export/restore and are reconstructable
through deterministic metacognition.

The deterministic v0.23 benchmark requires:

two initially supported-nearby environments -> three matched gate outcomes per
environment -> one region shows repeated gated-policy calibration advantage and
gains confidence -> a different region shows repeated underperformance and has
nearby support revoked -> later classification becomes unknown -> later
validity-gated decision blocks causal context -> export/restore -> identical
outcome and calibration records.

This remains bounded functional causal research. Outcome calibration does not
establish subjective identity, sentience, phenomenal consciousness, qualia, or
unrestricted real-world causation.

## v0.24 calibration-aware validity-map revision checkpoint

UNARCHI v0.24 turns repeated v0.23 region calibration into explicit immutable
validity-map revisions.

A base map remains the direct consolidation of tested causal-stability evidence.
A calibration-aware revision stores:

- the exact parent validity-map ID;
- a monotonically increasing revision number;
- the calibration IDs admitted into the revision;
- frozen calibrated-nearby support signatures;
- frozen revoked inferred signatures;
- explicit revision reasons for expansion, contraction, preservation, or no
  inferred-region change;
- the parent tested-valid and tested-invalid signatures unchanged;
- the parent stability-assessment links and environment dimensions unchanged.

Only inferred nearby regions can be expanded or contracted by calibration.
Exact tested-valid and tested-invalid causal evidence is copied into every child
revision unchanged.

Revision classification is intentionally immutable. New calibration records
created after a revision do not silently alter that revision. Their effect
becomes active only when another child validity map is explicitly created.

For compatibility, v0.23 runtime calibration behavior remains available on base
maps. Once a child map exists, its frozen revision state is authoritative until
the next explicit revision.

The deterministic v0.24 benchmark requires:

base validity map -> favorable calibration for nearby region A -> unfavorable
calibration for nearby region B -> revision 2 freezes A as calibrated support
and B as revoked -> new unfavorable evidence for A is recorded against revision
2 -> revision 2 remains unchanged -> revision 3 explicitly incorporates the new
calibration and revokes A -> exact tested-valid and tested-invalid signatures
remain unchanged across all revisions -> export/restore -> identical revision
lineage and evidence-grounded narrative.

This remains bounded functional causal research. Versioned validity maps are
auditable machine-state structures and do not establish subjective identity,
sentience, phenomenal consciousness, qualia, or unrestricted real-world
causation.

## v0.25 revision-selection and rollback checkpoint

UNARCHI v0.25 adds an explicit active validity-map pointer for each latent
context hypothesis.

A revision is eligible for activation only when its full parent chain is
intact. Lineage validation rejects:

- missing parents;
- parent links that cross hypotheses;
- revision-number gaps;
- cycles;
- malformed base maps that are not revision 1.

When no map ID is supplied, selection deterministically chooses the highest
intact revision, breaking revision ties by map ID. Creating a newer map does not
automatically activate it.

If an active pointer already exists, ordinary selection may retain the current
revision or advance only to a descendant on the same lineage. Moving backward
requires the dedicated rollback operation.

Rollback requires the target map to be an actual ancestor of the active map.
It changes only the active pointer and appends an audit record. It never deletes
the newer map, its calibration evidence, its gate outcomes, or any later
revision history. Rollback to a sibling or unrelated branch is rejected.

Every selection record stores:

- hypothesis ID;
- previous and selected map IDs;
- action: `activate`, `retain`, `advance`, or `rollback`;
- the validated selected lineage;
- a required human-readable reason;
- optional supporting evidence references.

Downstream decisions can use the active pointer directly through the
active-validity gated-decision path. The pointer and selection/rollback history
persist across export/restore.

The deterministic v0.25 benchmark requires:

three-revision lineage -> deterministic latest activation -> latest revision
blocks causal context in a revoked nearby region -> rollback to revision 2 ->
same region again uses revision-2 calibrated support -> revision 3 remains
stored -> explicit re-advance selects revision 3 again -> export/restore ->
identical active pointer, lineage history, and evidence-grounded narrative.

This remains bounded functional causal research. Active revision control is
auditable machine-state governance and does not establish subjective identity,
sentience, phenomenal consciousness, qualia, or unrestricted real-world
causation.

## v0.26 active-revision degradation-watch checkpoint

UNARCHI v0.26 monitors calibration evidence specifically for the currently
active validity-map revision and can produce an evidence-backed rollback
recommendation without changing the active pointer.

Each activation, advance, or rollback selection now records the highest
region-calibration ID that existed at the time of selection. This calibration
watermark separates historical evidence from genuinely new post-activation
evidence.

The degradation watch considers only region calibrations that:

- belong to the currently active map;
- were created after the active selection's calibration watermark; and
- meet the minimum observed-outcome sample threshold.

A region is treated as degraded only when its gated-policy calibration
advantage is below the configured negative margin. One such region-calibration
record already represents repeated matched outcomes because v0.23 requires
multiple observed gate outcomes before calibration.

When degradation is detected, the watch walks the active revision lineage from
the nearest ancestor backward. An ancestor is eligible for recommendation only
when it has favorable matched calibration for at least one degraded environment
and its mean calibration advantage is better than the active degraded evidence.

The watch stores:

- active map ID and activation-selection ID;
- activation calibration watermark;
- post-activation calibration IDs considered;
- degraded environment signatures;
- mean active gated-policy advantage;
- recommended ancestor map and revision, when one qualifies;
- the ancestor calibration IDs supporting that recommendation;
- status and evidence-linked reason.

Possible statuses include:

- `insufficient_post_activation_evidence`;
- `stable`;
- `degradation_detected_no_supported_ancestor`;
- `rollback_recommended`.

A rollback recommendation never changes the active pointer. The v0.25 rollback
operation remains an explicit separate action, so later revisions and all
evidence remain intact until an operator or higher-level policy decides to act.

The deterministic v0.26 benchmark requires:

base map with favorable nearby calibration -> revision 2 -> activate revision 2
and record calibration watermark -> watch sees no new calibration and returns
insufficient evidence -> three new matched outcomes show active-revision
underperformance -> new region calibration becomes unfavorable -> degradation
watch recommends the nearest ancestor with prior favorable calibration -> active
pointer remains revision 2 -> no rollback history entry is created ->
export/restore preserves the recommendation and active pointer.

This remains bounded functional causal research. A rollback recommendation is
an evidence-governance record, not autonomous authority, and does not establish
subjective identity, sentience, phenomenal consciousness, qualia, or
unrestricted real-world causation.

## v0.27 rollback-recommendation resolution checkpoint

UNARCHI v0.27 adds explicit governance decisions for v0.26 degradation-watch
recommendations.

A recommendation can receive one of three decisions:

- `accept`: explicitly execute the existing v0.25 ancestor-only rollback;
- `defer`: record that the recommendation remains under review without moving
  the active pointer;
- `dismiss`: close the recommendation without moving the active pointer.

Defer is non-terminal and can later be superseded by accept or dismiss.
Accept and dismiss are terminal for that recommendation.

Every resolution record stores:

- degradation-watch ID and hypothesis ID;
- decision and required human-readable reason;
- recommended ancestor map;
- descendant map blocked by an accepted rollback;
- rollback selection ID when acceptance executes the rollback;
- supporting evidence references.

Accepted rollback does not delete the degraded descendant or any evidence.
Instead, the rollback selection records both a calibration watermark and a
decision-gate watermark. These watermarks isolate evidence that genuinely
arrives after rollback.

After acceptance, any attempt to advance from the rollback map to a descendant
is blocked until post-rollback validation succeeds.

Rollback validation uses only gate outcomes that:

- were created after the rollback decision-gate watermark;
- belong to the active rollback map; and
- concern the environment signatures that triggered the original degradation
  recommendation.

Each degraded signature must meet the minimum number of new observed outcomes.
The rollback is considered improved only when mean gated-policy advantage is
positive by at least the configured margin and improves materially over the
degraded revision's prior mean advantage.

Validation statuses include:

- `insufficient_post_rollback_evidence`;
- `rollback_not_improved`;
- `rollback_improved`.

Only `rollback_improved` sets `reactivation_allowed=true`. A later explicit
selection can then re-advance along the intact lineage. UNARCHI does not
automatically reactivate the descendant.

The deterministic v0.27 benchmark requires:

rollback recommendation -> defer leaves the active pointer unchanged -> dismiss
leaves the active pointer unchanged -> accept performs the existing ancestor
rollback -> immediate re-advance is rejected -> validation initially reports
insufficient post-rollback evidence -> three new matched rollback outcomes show
improved calibration -> validation permits reactivation -> explicit re-advance
succeeds -> export/restore preserves resolution and validation history.

This remains bounded functional causal research. Recommendation resolution and
rollback validation are auditable governance mechanisms and do not establish
subjective identity, sentience, phenomenal consciousness, qualia, or
unrestricted real-world causation.

## v0.28 rollback holdout-validation checkpoint

UNARCHI v0.28 separates rollback recovery evidence from the evidence that can
authorize descendant reactivation.

The accepted v0.27 rollback still creates a decision-gate watermark. New
post-rollback outcomes after that watermark form the recovery batch. Recovery
validation now has three important properties:

- every degraded signature must meet the configured minimum sample count;
- mean gated-policy advantage must be positive by the configured margin and
  materially better than the degraded descendant;
- even a passed recovery batch cannot authorize reactivation.

When recovery passes, v0.28 freezes a second decision-gate watermark. Only
outcomes from later gates can enter holdout validation. This prevents the same
observations from being counted both as evidence that recovery occurred and as
evidence that recovery generalizes.

Holdout validation requires:

- the rollback map to remain active;
- the recovery validation to have passed;
- a separate post-recovery sample count for every degraded signature;
- positive holdout gated-policy advantage;
- material improvement over the previously degraded revision; and
- no larger than the configured tolerated drop from recovery performance.

Possible holdout statuses are:

- `insufficient_holdout_evidence`;
- `holdout_not_confirmed`;
- `holdout_confirmed`.

Only `holdout_confirmed` sets `reactivation_allowed=true`. Normal revision
selection checks this holdout record before permitting re-advance to the
blocked descendant. A favorable recovery batch by itself remains insufficient.

The deterministic v0.28 benchmark requires:

accepted rollback -> three favorable post-rollback outcomes -> recovery passes
but reactivation remains blocked -> branch A receives three unfavorable
post-recovery outcomes and holdout fails -> descendant remains blocked ->
independent branch B receives three favorable post-recovery outcomes -> holdout
confirms recovery -> recovery and holdout outcome IDs do not overlap -> explicit
re-advance succeeds -> export/restore preserves holdout-validation history.

This remains bounded functional causal research. The holdout gate is an
anti-overfitting evidence-governance mechanism and does not establish
subjective identity, sentience, phenomenal consciousness, qualia, or
unrestricted real-world causation.

## v0.29 post-reactivation holdout-drift checkpoint

UNARCHI v0.29 monitors a descendant only after it has passed the complete
rollback recovery and independent holdout process from v0.28 and has then been
explicitly reactivated.

The reactivation selection already records a decision-gate watermark. v0.29
uses that watermark as a strict evidence boundary:

- recovery outcomes are older than the reactivation watermark and cannot count;
- holdout outcomes are older than the reactivation watermark and cannot count;
- only later gate outcomes on the reactivated descendant can enter drift
  monitoring;
- only the environment signatures that triggered the original degradation are
  evaluated.

The drift watch requires the configured minimum number of new outcomes for
every previously degraded signature. It compares mean post-reactivation
gated-policy advantage with the confirmed holdout baseline.

Possible statuses are:

- `insufficient_post_reactivation_evidence`: not every tracked signature has
  enough new evidence;
- `post_reactivation_stable`: calibration remains positive and within the
  configured tolerated drop from holdout performance;
- `post_reactivation_warning`: evidence is inconclusive and should continue
  accumulating;
- `renewed_degradation_detected`: calibration is negative and has materially
  fallen from the confirmed holdout baseline.

A drift watch never changes the active validity-map pointer. Renewed degradation
produces only the auditable recommendation `review_for_rollback`; an explicit
governance decision is still required for any later map change.

Each drift record stores the confirmed holdout ID, reactivation selection ID,
post-reactivation watermark, active map, observed outcome IDs, tracked
signatures, mean post-reactivation advantage, holdout baseline, advantage
delta, status, recommendation, reason, and evidence references.

The deterministic v0.29 benchmark requires:

confirmed recovery -> confirmed independent holdout -> explicit descendant
reactivation -> initial drift watch sees no new evidence -> branch A receives
three favorable post-reactivation outcomes and remains stable -> branch B
receives three unfavorable post-reactivation outcomes and detects renewed
degradation -> branch B outcomes do not overlap recovery or holdout outcomes ->
the watch recommends governance review without creating a rollback or changing
the active pointer -> export/restore preserves the drift history.

This remains bounded functional causal research. Post-reactivation drift
monitoring is an evidence-governance mechanism and does not establish subjective
identity, sentience, phenomenal consciousness, qualia, or unrestricted
real-world causation.

## v0.30 renewed-degradation resolution checkpoint

UNARCHI v0.30 adds explicit governance for a v0.29
`renewed_degradation_detected` watch.

A drift recommendation can now be resolved as:

- `defer`: retain the current descendant and allow later resolution after
  more review;
- `dismiss`: retain the current descendant and terminally close that watch;
- `rollback_review`: explicitly return to the rollback map whose recovery and
  holdout previously justified reactivation.

Only a watch with `renewed_degradation_detected` and
`review_for_rollback` can use `rollback_review`. The active map must still
match the map recorded by the drift watch, so stale recommendations cannot move
a newer active pointer.

A rollback-review resolution records the prior active descendant, confirmed
holdout ID, rollback target, new rollback-selection ID, blocked descendant,
reason, and evidence references. It preserves every prior map revision,
recovery result, holdout result, reactivation record, drift record, and outcome.

The important v0.30 safety property is stale-authorization invalidation. After a
renewed-degradation rollback, the earlier `holdout_confirmed` result no longer
authorizes immediate re-advance. Normal validity-map selection detects the new
rollback-review resolution and blocks the descendant with:

`re-advance blocked until renewed-degradation rollback completes a new evidence
cycle`.

v0.30 intentionally does not fabricate that new cycle. It records
`requires_new_evidence_cycle=true` and leaves the rollback map active until a
later checkpoint defines and validates fresh recovery evidence.

`defer` remains non-terminal. `dismiss` and `rollback_review` are terminal
for a drift watch. None of these operations delete evidence or revision
history.

The deterministic v0.30 benchmark requires:

confirmed recovery and holdout -> explicit descendant reactivation -> fresh
negative post-reactivation outcomes -> renewed degradation -> defer branch keeps
descendant active -> dismiss branch keeps descendant active -> rollback-review
branch returns to the prior rollback map -> descendant revision remains stored
-> immediate re-advance with the old holdout is rejected -> terminal resolution
cannot be reopened -> export/restore preserves the resolution and active map.

This remains bounded functional causal research. Resolution governance is an
auditable machine-control mechanism and does not establish subjective identity,
sentience, phenomenal consciousness, qualia, or unrestricted real-world
causation.

## v0.31 renewed-degradation recovery cycle checkpoint

UNARCHI v0.31 closes the evidence-governance gap intentionally left by v0.30
after a second rollback caused by renewed post-reactivation degradation.

A renewed-degradation rollback review now starts a new evidence cycle at the
second rollback selection's decision-gate watermark. The renewed recovery
validator admits only outcomes that:

- were created after that second rollback watermark;
- belong to the active rollback map;
- concern the signatures that renewed degradation identified; and
- do not reuse any outcome from earlier rollback recovery, independent holdout,
  descendant reactivation drift, or any prior renewed cycle.

Every degraded signature must reach the configured fresh sample threshold.
Recovery is considered passed only when the new batch has positive gated-policy
advantage and materially improves on the renewed-degradation batch. Passing
recovery still does not authorize reactivation.

A second watermark is frozen only after renewed recovery passes. The renewed
holdout validator then accepts only later outcomes and checks that:

- the holdout has no overlap with any prior episode evidence;
- the holdout has no overlap with the renewed recovery batch;
- every degraded signature has enough independent holdout samples;
- holdout advantage remains positive and materially above the degraded
  descendant; and
- performance does not fall beyond the configured tolerated drop from renewed
  recovery.

Only `renewed_holdout_confirmed` sets
`reactivation_allowed=true`. Normal validity-map selection consults this
record before permitting another descendant advance after a renewed-degradation
rollback review.

The renewed recovery and holdout records persist through export/restore.
v0.31 accepts v0.30 exports for backward-compatible state restoration while new
snapshots identify themselves as `unarchi-v0.31`.

The deterministic v0.31 benchmark requires:

initial rollback recovery and holdout -> descendant reactivation -> fresh
negative post-reactivation outcomes -> renewed degradation -> second rollback
review -> stale earlier holdout remains blocked -> new recovery initially has
insufficient evidence -> three later favorable recovery outcomes pass renewed
recovery but still cannot reactivate -> a separate later holdout initially has
insufficient evidence -> three later favorable holdout outcomes confirm the
cycle -> earlier episode, renewed recovery, and renewed holdout outcome IDs are
pairwise non-overlapping -> explicit descendant re-advance succeeds ->
export/restore preserves the new cycle and active map.

This remains bounded functional causal research. Fresh evidence-cycle
governance does not establish subjective identity, sentience, phenomenal
consciousness, qualia, or unrestricted real-world causation.

## v0.32 repeated episode isolation checkpoint

UNARCHI v0.32 makes renewed-degradation recovery explicitly episode-aware when
the same failure signature recurs after a previously recovered descendant is
reactivated again.

Every post-reactivation drift watch now records an immutable episode identifier
and the source of the holdout that authorized the active descendant. The first
renewed episode is anchored to the original rollback holdout. After a renewed
recovery and renewed holdout succeed, any later recurrence is anchored to that
newest confirmed renewed holdout instead of silently falling back to the
original authorization.

Each rollback-review resolution carries the same episode identifier and
holdout-source provenance. Renewed recovery and holdout records preserve that
episode identity, the prior holdout source, the rollback decision-gate
watermark, recovery outcome set, holdout watermark, holdout outcome set, and
excluded prior outcome IDs.

The isolation rule remains fail-closed:

- recovery evidence must be created after the episode's rollback watermark;
- holdout evidence must be created after that recovery's holdout watermark;
- recovery and holdout sets must be disjoint;
- every earlier rollback, holdout, drift, renewed recovery, and renewed holdout
  outcome for the hypothesis is excluded from later renewed recovery;
- reactivation authorization belongs only to the holdout produced by the same
  episode; and
- a later recurring failure binds to the newest confirmed renewed holdout.

The deterministic v0.32 benchmark runs two complete renewed-degradation
episodes for the same signature. Episode 1 recovers and reactivates the
descendant. The same signature then degrades again. Episode 2 must identify
itself as episode 2, use episode 1's renewed holdout as its baseline, reject all
earlier evidence from its recovery and holdout batches, complete a second
independent holdout, and only then allow another descendant advance.
Export/restore must preserve the episode IDs, holdout-source provenance,
evidence isolation, and active map.

v0.32 accepts v0.31 and v0.30 exports for backward-compatible state restoration
while new snapshots identify themselves as `unarchi-v0.32`.

This remains bounded functional causal research. Episode-aware evidence
governance does not establish subjective identity, sentience, phenomenal
consciousness, qualia, or unrestricted real-world causation.

## v0.33 multi-hypothesis arbitration checkpoint

UNARCHI v0.33 adds an explicit arbitration layer above the existing causal
hypothesis store. Active hypotheses are no longer allowed to influence
downstream planning simply because they were inserted or evaluated first.

For every arbitration, the kernel exposes and records:

- normalized hypothesis confidence and corresponding uncertainty;
- observed supporting and contradicting evidence counts;
- an evidence-smoothed support ratio;
- explicit context-validity supplied by the calling research protocol;
- the predicted consequence for the requested discriminating test, when one is
  available;
- a deterministic bounded arbitration score;
- the ordered candidate set and the selected hypothesis IDs;
- evidence references used to justify the arbitration.

The arbitration is fail-closed. If no active hypothesis reaches the configured
minimum observed-evidence floor, no causal model is selected. When one model
has a materially stronger score it is selected alone. When multiple
evidence-supported models remain within a bounded score margin, UNARCHI keeps a
small combination rather than collapsing uncertainty into a false single-model
answer.

Tie-breaking is deterministic and does not use insertion order as the primary
decision signal. Arbitration does not mutate hypothesis confidence; confidence
changes remain restricted to observed experiment or intervention evidence.

The deterministic v0.33 benchmark requires:

three competing causal models -> unequal explicit support/contradiction records
-> context-validity and consequence exposure -> strongest evidence-grounded
model selected despite not being first -> separate no-evidence branch withholds
selection -> export/restore preserves the arbitration record exactly.

v0.33 accepts v0.32, v0.31 and v0.30 exports for backward-compatible state
restoration while new snapshots identify themselves as `unarchi-v0.33`.

This remains bounded functional causal research. Evidence-grounded hypothesis
arbitration does not establish subjective identity, sentience, phenomenal
consciousness, qualia, or unrestricted real-world causation.

## v0.34 hierarchical long-horizon planning checkpoint

UNARCHI v0.34 adds a deterministic bounded hierarchy for long-horizon
objectives. The hierarchy is an explicit research plan, not an autonomous
external executor.

Each plan node records:

- a goal or sub-goal title and parent relationship;
- one explicit checkpoint;
- the assumption that permits that branch to continue;
- the evidence condition that should trigger replanning;
- the rollback condition for that branch;
- a bounded resource allocation;
- current planning status and retained evidence references.

Plan creation is fail-closed when required planning fields are absent, depth or
node bounds are exceeded, or declared branch resources exceed the plan-wide
resource ceiling.

A checkpoint cannot be promoted from narrative text alone. It requires explicit
evidence references and records measured resource usage. A checkpoint becomes
`verified` only when both the checkpoint and its underlying assumption remain
valid. Otherwise the node becomes `invalidated`.

Replanning is branch-local. Only an invalidated node can start a replacement
branch. The invalidated node and its descendants become superseded, while
verified nodes outside that branch keep their original identifiers, evidence,
and verified status. The replacement branch cannot consume more declared
resources than the invalidated branch releases.

Every replan record therefore exposes:

- the invalidated node;
- the complete affected descendant set;
- unaffected verified nodes preserved for reuse;
- replacement node identifiers;
- released versus replacement resource limits;
- the evidence and reason that justified the branch change.

The deterministic v0.34 benchmark requires:

multi-branch plan -> independent branch verified -> separate intermediate
assumption contradicted by evidence -> only that branch invalidated -> bounded
replacement branch -> unrelated verified branch keeps the same node identity
and evidence -> export/restore preserves the selective replan exactly.

v0.34 accepts v0.33, v0.32, v0.31 and v0.30 exports for backward-compatible
state restoration while new snapshots identify themselves as
`unarchi-v0.34`.

This is bounded functional planning research. It does not establish subjective
identity, sentience, phenomenal consciousness, qualia, or unrestricted
real-world autonomy.

## v0.35 resource-aware cognition checkpoint

UNARCHI v0.35 makes money, compute, latency, risk, and uncertainty explicit
bounded planning variables instead of leaving resource pressure implicit.

Each resource-aware decision receives:

- an explicit money budget;
- a compute budget;
- a latency ceiling;
- maximum risk and uncertainty;
- candidate expected value;
- measured information gain;
- measured reliability; and
- optional evidence references for the measurements.

The selector is fail-closed against hard budget violations. A candidate that
exceeds money, compute, latency, risk, or uncertainty limits is excluded before
ranking, even when its expected value is high.

Among feasible candidates, v0.35 computes a bounded resource burden and
value-adjusted score. When multiple options have similar expected value, the
lower-resource option is preferred unless measured information gain or
reliability exceeds the configured premium-justification threshold and the
higher-resource option also has the stronger bounded score.

The deterministic v0.35 benchmark therefore requires:

similar-value low-cost and high-cost branches -> low-cost branch selected ->
over-budget high-value branch rejected -> separate comparison where the
higher-cost branch has materially stronger measured information gain and
reliability -> premium branch selected -> export/restore preserves both
decisions exactly.

v0.35 accepts v0.34, v0.33, v0.32, v0.31 and v0.30 exports for
backward-compatible state restoration while new snapshots identify themselves
as `unarchi-v0.35`.

This remains bounded functional planning research. Resource-aware selection
does not establish subjective identity, sentience, phenomenal consciousness,
qualia, or unrestricted real-world autonomy.

## v0.36 scalable persistent memory checkpoint

UNARCHI v0.36 separates bounded working memory from a larger restart-safe
persistent-memory tier. The persistent tier remains deterministic and CPU-only;
it is not an unbounded database or a claim of human episodic memory.

When the short-term autobiographical window overflows, evicted experiences are
converted into provenance-bearing long-term records instead of being silently
discarded. Archived success and failure records remain eligible to influence
later memory bias after the original experience has left the working set.

Every persistent record carries:

- a stable record identifier and memory kind;
- bounded content;
- one or more provenance references;
- provenance strength;
- confidence and importance;
- creation and last-access experience counters;
- retrieval access count; and
- a source count showing deterministic consolidation lineage.

Retrieval combines lexical relevance with confidence, importance, provenance
strength, and freshness. Explicit score, provenance, age, and top-k limits keep
retrieval bounded. Records that are too weakly sourced, too stale, or below the
retrieval floor are excluded rather than promoted by age or repetition alone.

Same-kind records with sufficiently similar content can consolidate in place.
Consolidation preserves the union of provenance references, increments the
source count, averages confidence across sources, and retains the strongest
importance and provenance-strength measurements.

Bounded forgetting is explicit. Stale records with weak retention scores are
removed, and the persistent tier has an independent hard capacity ceiling.
Retention combines confidence, importance, provenance strength, and freshness,
so weak transient notes can be forgotten while strongly sourced evidence can
survive beyond the short-term window.

The deterministic v0.36 benchmark requires:

relevant experience -> short-term eviction -> persistent retrieval still finds
it -> archived outcome still influences memory bias -> duplicate verified
records consolidate while retaining both provenance references -> stale weak
record is forgotten while strong evidence remains -> export/restore preserves
the bounded persistent tier and monotonic identifiers.

v0.36 accepts v0.35, v0.34, v0.33, v0.32, v0.31 and v0.30 exports for
backward-compatible restoration. Legacy exports simply restore with an empty
persistent tier when they contain no v0.36 memory records.

This remains bounded functional memory research. It does not establish
subjective identity, sentience, phenomenal consciousness, qualia, or
unrestricted real-world autonomy.

## Next checkpoint: v0.37 controlled environment interaction

The next research step should feed verified tool outcomes back into the
cognitive state through the existing governed tool gateway, preserving audit,
approval, budget, and evidence boundaries. Tool results should be observations,
not automatic proof: only verified outcomes may update durable cognitive state,
and failed or ambiguous executions must remain explicitly distinguishable.
