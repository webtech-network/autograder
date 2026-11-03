# Autograder — agent instructions

The contributor reference for humans and coding agents is [AGENTS.md](../AGENTS.md).
Read it first; this file intentionally does not repeat it, so the two cannot drift.

- Responsibilities and allowed dependencies:
  [docs/architecture/overview.md](../docs/architecture/overview.md)
- Adding an evaluator (implementation, parameter contract, registration, tests):
  [docs/architecture/extending.md](../docs/architecture/extending.md)
- Adding a language/runtime: "Change surface" in
  [docs/contracts/LANGUAGES.md](../docs/contracts/LANGUAGES.md)
- Normative integration contracts: [docs/contracts/](../docs/contracts/DECISIONS.md)

There is no step framework (`Step`, `StepName`, `add_step_result`), no
`CommandResolver` and no `sandbox_manager` `Language`; documents under `archive/`
describe those historical designs only.
