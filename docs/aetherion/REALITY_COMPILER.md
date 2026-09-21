# Aetherion Reality Compiler v0.3

The Reality Compiler is an executable, truth-gated design-search layer inside
Seldrune STI. It turns an explicit objective, constraints, success metrics, and
candidate hypotheses into deterministic evaluations and a prototype plan. Its
causal digital twin runs bounded counterfactual scenarios over relationships
that the caller declares.

## Current executable boundary

Version 0.3 can:

- validate bounded objectives and normalized candidate data;
- reject candidates that miss declared constraints or cross risk thresholds;
- rank viable candidates with a deterministic multi-objective score;
- select reproducible prototype steps;
- propagate interventions through a bounded numeric causal model;
- enforce simulation guardrails and record every model assumption;
- define falsifiable laboratory protocols with units and safety notes;
- fit measured observations, calculate R², and enforce slope acceptance bounds;
- require content-addressed evidence for every submitted observation;
- issue SHA-256 evidence receipts for compilation, simulation, and calibration;
- expose results through the Aetherion API and Owner Console.

It does **not** autonomously discover new physics, prove that a declared causal
link exists, validate a physical prototype, prove commercial value, or verify
a real-world outcome. Every receipt remains `experimental`, with causal,
physical, and real-world verification flags set to `false`.

## API

- `GET /api/v1/aetherion/reality-compiler` returns a deterministic compiler demo.
- `POST /api/v1/aetherion/reality-compiler/compile` evaluates a candidate set.
- `GET /api/v1/aetherion/reality-compiler/digital-twin` returns a twin demo.
- `POST /api/v1/aetherion/reality-compiler/simulate` runs a bounded twin scenario.
- `GET /api/v1/aetherion/reality-compiler/reality-lab` returns a lab demo.
- `POST /api/v1/aetherion/reality-compiler/calibrate` evaluates observations.

## Digital twin limits

A simulation accepts at most 128 state variables, 1,024 declared causal links,
and 256 propagation steps. Values are clamped to their declared physical or
operating bounds. Interventions, guardrails, assumptions, every trajectory
frame, and verification flags are included in the deterministic receipt.

The simulator is a hypothesis engine. Its coefficients must later be calibrated
against measured data before anyone can claim the causal model is verified.

## Reality Lab gate

Reality Lab accepts a protocol and up to 10,000 finite observations. Each
observation must reference a SHA-256 evidence artifact. It computes a linear
fit, slope, intercept, and R², then returns one of three decisions:
`insufficient-data`, `rejected`, or `eligible-for-independent-review`.

Eligibility is not verification. The receipt always keeps independent
replication, causal-model verification, and physical-system verification false.
A later authorized process must validate evidence provenance and replication.

## Evidence progression

1. **Hypothesis** — a candidate and causal assumptions are explicitly stated.
2. **Experimental** — software validates, simulates, scores, and receipts them.
3. **Model calibration** — future measured data must validate causal parameters.
4. **Physical verification** — future external prototype evidence is required.
5. **Real-world verification** — future measured outcome evidence is required.

The software must never infer stages 3–5 from a simulation score.
