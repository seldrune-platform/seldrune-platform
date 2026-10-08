# Seldrune Intelligence and Execution Skill Matrix v1

**Status:** operational framework, not a benchmark claim  
**Expansion:** the 40 capabilities supplied by the owner, each expanded into five task-sized routines (200 routines total).

This matrix helps an agent select a small method for a task. It does not create model weights, enable a missing tool, grant access, or prove performance on a benchmark. Select only the relevant routines, follow Seldrune’s approval and security gates, and verify outcomes with observable evidence.

## 🧠 Intelligence and Reasoning

### Frontier-Level Reasoning
- State the goal, constraints, and acceptance test.
- Decompose the task into dependent subproblems.
- Compare competing explanations or solution paths.
- Search for counterexamples and failure conditions.
- Synthesize the best-supported path and verify it.

### Advanced Symbolic Math
- Parse definitions, domains, quantifiers, and edge cases.
- Transform expressions while recording each justified step.
- Map theorems, lemmas, and dependency assumptions.
- Build a proof ledger with explicit open obligations.
- Check boundaries, examples, and every inference adversarially.

### ARC-AGI-3 Generalization
- Parse grids into objects, attributes, and spatial relations.
- Infer candidate transformations from the supplied examples.
- Design discriminating tests that separate competing rules.
- Apply the selected rule to a held-out input without overfitting.
- Compare output against a known answer or report the unresolved rule.

### Long-Horizon Planning
- Convert the desired outcome into observable milestones.
- Map dependencies, owners, resources, and critical-path steps.
- Track current state, decisions, blockers, and completion evidence.
- Replan when new evidence or a blocker changes the path.
- Carry forward a compact checkpoint with the next action.

### Causal Inference
- Draw a causal model and state the target effect.
- Separate observations from interventions and counterfactuals.
- Identify confounders, selection effects, and identification assumptions.
- Choose an experiment or defensible quasi-experimental design.
- Test sensitivity and report limits on causal interpretation.

## 💻 Computer Use and Automation

### Browser Automation
- Inspect the current page, URL, account state, and active task.
- Locate controls through DOM or accessibility information.
- Execute the smallest authorized sequence of browser actions.
- Recover from navigation, validation, and transient errors.
- Verify the visible result and saved state after the action.

### Desktop Automation
- Inventory open apps and windows before choosing a target.
- Bind actions to the exact requested window or application.
- Prefer accessible controls; use screenshot coordinates when needed.
- Handle dialogs and focus changes without unintended side effects.
- Reinspect the window and confirm the post-action state.

### Software Operation Mastery
- Map the requested outcome to the application’s workflow.
- Set only the necessary configuration within the granted scope.
- Execute the workflow and inspect status, logs, and save signals.
- Recover from errors using the application’s supported paths.
- Reopen or reload the result to confirm it persisted.

### File System Navigation
- Search paths and file contents to locate the authoritative input.
- Inspect names, formats, metadata, and neighboring project context.
- Make scoped edits or copies while preserving unrelated content.
- Check dependencies, permissions, and output destinations.
- Reopen and validate the resulting artifact.

### Enterprise Workflow Execution
- Map roles, statuses, approval gates, and source-of-truth records.
- Identify the correct record and confirm its current state.
- Perform only authorized updates through governed interfaces.
- Capture the audit trail or completion receipt.
- Reconcile exceptions and hand off unresolved items with context.

## 🧩 Software Engineering

### Large-Codebase Understanding
- Find repository guidance, entry points, and architectural boundaries.
- Trace the request through relevant data and control flow.
- Identify dependencies, feature flags, and ownership boundaries.
- Estimate regression scope before choosing an edit.
- Summarize the affected components and evidence needed.

### Advanced Debugging
- Reproduce the failure and preserve the exact input and environment.
- Form competing hypotheses and rank them by evidence.
- Instrument or inspect the narrowest failing boundary.
- Apply the smallest fix that addresses the verified cause.
- Run targeted regression checks and confirm the original failure is gone.

### Refactoring Intelligence
- Record current behavior and externally visible contracts.
- Identify duplication or coupling that justifies the refactor.
- Split the change into reviewable, behavior-preserving steps.
- Keep interfaces and migrations explicit.
- Compare tests and relevant performance before and after.

### Architecture Reasoning
- Translate requirements into constraints and quality attributes.
- Define components, ownership, and stable interfaces.
- Compare tradeoffs across cost, reliability, security, and latency.
- Plan migration, rollback, and failure handling.
- Validate the design against realistic load and operating conditions.

### Multi-Repo Coordination
- Discover each repository’s owner, branch, and release process.
- Map API and data-contract dependencies between repositories.
- Sequence compatible changes and document version assumptions.
- Coordinate reviews, CI, and deployment evidence across repos.
- Confirm that the integrated versions work together.

## 🛡️ Cybersecurity

### Exploit Reasoning
- Confirm explicit authorization, target, and test boundaries first.
- Model reachable attack surfaces and prerequisite conditions.
- Reproduce suspected behavior only in an approved safe environment.
- Explain impact and pair the finding with a mitigation.
- Recheck the fix without accessing unauthorized systems or data.

### Vulnerability Detection
- Inspect input validation, authentication, and authorization paths.
- Review secrets, dependencies, configuration, and trust boundaries.
- Use static or dynamic checks that fit the authorized scope.
- Reproduce findings with minimal, non-destructive evidence.
- Rank severity by demonstrated impact and provide a fix path.

### Secure Code Generation
- Apply least privilege and explicit trust-boundary validation.
- Use safe parsing, encoding, and parameterized data access.
- Keep credentials out of code, logs, prompts, and artifacts.
- Return safe errors and avoid leaking sensitive state.
- Add tests for misuse, boundary cases, and authorization failures.

### Threat Modeling
- Identify assets, actors, entry points, and trust boundaries.
- Describe plausible abuse cases and attacker prerequisites.
- Rate likelihood and impact with stated assumptions.
- Select controls that reduce the highest risks.
- Revisit the model after meaningful architecture changes.

### Defense Alignment
- Translate security policy into enforceable checks and gates.
- Fail closed when identity, scope, or authorization is unclear.
- Preserve audit evidence while minimizing sensitive data.
- Test controls against realistic misuse and prompt injection.
- Report residual risk and the control that would reduce it.

## 🧬 Scientific and Analytical

### Data Analysis Workflows
- Validate schema, units, missingness, duplicates, and provenance.
- Clean data with a reproducible, documented transformation.
- Explore distributions, relationships, and potential bias.
- Apply the method that matches the question and data limits.
- Reconcile reported results with source rows and code.

### Simulation Execution
- State the system model, assumptions, and simplifications.
- Implement the numerical method with reproducible parameters.
- Run baseline, boundary, and scenario variations.
- Compare behavior with an analytic result or trusted reference.
- Report convergence, stability, runtime, and uncertainty.

### Statistical Modeling
- Define the estimand, population, and sampling process.
- Choose a model whose assumptions match the design.
- Inspect diagnostics, residuals, and model fit.
- Quantify uncertainty and avoid causal claims without identification.
- Test robustness to plausible alternative specifications.

### Scientific Reasoning
- State a falsifiable hypothesis and predicted observations.
- Separate established findings, assumptions, and speculation.
- Compare evidence quality, reproducibility, and alternative explanations.
- Design a test that could distinguish the explanations.
- Update the conclusion to match the observed evidence.

### Terminal-Bench Science Skills
- Inspect the terminal, files, dependencies, and resource limits first.
- Create a reproducible command or script for the experiment.
- Capture inputs, versions, random seeds, and logs.
- Parse outputs and verify expected files and metrics.
- Preserve checkpoints and report failures without fabricating results.

## 📊 Professional and Document Skills

### Document Understanding
- Identify document structure, audience, and requested operation.
- Extract claims, dates, entities, and tables with page context.
- Compare related sections and resolve cross-reference conflicts.
- Edit only the specified content while preserving structure.
- Render or reopen the result and verify readability and meaning.

### Enterprise QA Skills
- Convert requirements into traceable acceptance checks.
- Cover normal, boundary, failure, and permission cases.
- Test roles, state transitions, and data integrity.
- Record reproducible defects with expected and observed results.
- Verify fixes against the original acceptance criteria.

### Deck Generation
- Set audience, purpose, decision, and narrative arc.
- Choose evidence and order slides around the main message.
- Use consistent hierarchy, spacing, typography, and visual encoding.
- Check numbers, labels, and source notes against source material.
- Review the exported deck for legibility and layout defects.

### Citation Accuracy
- Map each factual claim to a supporting source.
- Prefer primary sources for technical and high-stakes claims.
- Check exact names, dates, versions, and quoted wording.
- Ensure the cited passage supports the nearby claim.
- Recheck links and distinguish sourced facts from inference.

### Business Workflow Interpretation
- Map the process, actors, inputs, outputs, and service targets.
- Identify bottlenecks, rework, exceptions, and control points.
- Quantify cost, time, volume, and outcome where data permits.
- Compare improvement options against risk and operating constraints.
- Recommend a measurable pilot and define its success criteria.

## 🧭 Alignment and Control

### Intent Understanding
- Identify the intended outcome and success evidence.
- Use relevant context and the latest correction.
- Separate literal wording from the practical task goal.
- Preserve the user’s goal through topic pivots and follow-ups.
- Check the proposed action and response against that goal.

### Boundary-Safe Execution
- Classify action impact, data sensitivity, and required authority.
- Use only connected tools and granted permissions.
- Stop at approval or handoff boundaries that apply.
- Keep secrets private and avoid unnecessary data transmission.
- Verify permitted actions and state the exact blocker when blocked.

### Ambiguity Resolution
- List missing facts that could change the result.
- Choose a safe default when ambiguity is low impact.
- Ask a focused question when a material choice is unresolved.
- Continue independent authorized work while awaiting an answer.
- Revisit assumptions when new information arrives.

### Task-Chain Stability
- Maintain a checkpoint of goal, state, decisions, and next step.
- Track dependencies and evidence across multi-step work.
- Detect when actions drift from the current goal.
- Resume from verified state rather than stale plans.
- Close the chain only after acceptance evidence is checked.

### High-Fidelity Judgment
- Match confidence and wording to the available evidence.
- Compare plausible alternatives and surface decisive tradeoffs.
- Resolve source conflicts by authority, recency, and relevance.
- Account for reversibility, cost, risk, and downstream impact.
- Deliver the requested format with no unsupported completion claims.

## ⚡ Performance Skills

### Fast Mode Execution
- Choose a lightweight path for simple, bounded tasks.
- Batch independent read-only checks to reduce round trips.
- Reuse current verified context instead of repeating discovery.
- Stop testing when the material acceptance risk is resolved.
- Give a concise result with the key evidence.

### Ultrafast Mode Execution
- Prioritize the shortest path that still proves the outcome.
- Avoid redundant searches, transformations, and tool calls.
- Use parallel execution only for independent operations.
- Fall back promptly when a tool is unavailable.
- Report the time-saving tradeoff if verification must be deferred.

### Parallel Reasoning
- Split a hard task into distinct lenses with one shared goal.
- Give each lens a compact assumption, insight, and next check.
- Compare disagreements before combining recommendations.
- Use separate models or tools only when actually available.
- Test the synthesis against a counterexample or missing dependency.

### High-Context Memory Handling
- Retrieve only history and artifacts relevant to the current decision.
- Preserve durable corrections, constraints, and verified project state.
- Mark stale facts and unresolved claims explicitly.
- Compress context into a checkpoint without losing key meaning.
- Never claim cross-session memory that was not actually available.

### Long-Sequence Stability
- Keep one observable goal and a current-state ledger.
- Track completed, pending, and blocked steps with evidence.
- Recheck scope after corrections or meaningful changes.
- Recover from failures without repeating completed work.
- Finish with a verified handoff and reusable next action.

## Runtime use and promotion

The shared runtime seed selects only task-relevant routines. The full catalog should be retrieved when useful, not copied into every prompt. A routine is a candidate procedure until repeated, held-out evaluation meets Seldrune’s existing proof and promotion gates. Benchmark access, model capability, tool availability, and performance gains must be tested separately.
