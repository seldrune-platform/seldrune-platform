# Aetherion Reality Compiler v0.1

The Reality Compiler is an executable, truth-gated design-search layer inside
Seldrune STI. It turns an explicit objective, constraints, success metrics, and
candidate hypotheses into deterministic evaluations and a prototype plan.

## Current executable boundary

Version 0.1 can:

- validate bounded objectives and normalized candidate data;
- reject candidates that miss declared constraints or cross risk thresholds;
- rank viable candidates with a deterministic multi-objective score;
- select reproducible prototype steps;
- issue a SHA-256 evidence receipt;
- expose the result through the Aetherion API and Owner Console.

It does **not** autonomously discover new physics, validate a physical
prototype, prove commercial value, or verify a real-world outcome. Every
receipt remains `experimental`, with physical and real-world verification
flags set to `false`.

## API

- `GET /api/v1/aetherion/reality-compiler` returns a deterministic demo receipt.
- `POST /api/v1/aetherion/reality-compiler/compile` accepts a bounded objective
  and candidate set, then returns the same evidence schema.

## Evidence progression

1. **Hypothesis** — a candidate exists as a stated principle.
2. **Experimental** — software validates, scores, rejects, and receipts it.
3. **Physical verification** — future external test evidence is required.
4. **Real-world verification** — future measured outcome evidence is required.

The software must never infer stages 3 or 4 from a simulation score.
