# Archive (historical)

Everything in this directory is **historical**. These files record designs,
roadmaps and verification data from earlier versions of the Autograder. They are
not current instructions and are not maintained; several describe mechanisms
that have been removed (the step pipeline and `PreFlightStep`, per-run template
loading, AI feedback mode, `CommandResolver`, result `root` wrappers and the
pipeline execution serializer).

For the current system read [AGENTS.md](../AGENTS.md), the
[responsibility map](../docs/architecture/overview.md) and the
[integration contracts](../docs/contracts/DECISIONS.md). Roadmap progress is
tracked in GitHub issues (the architecture refactor in #363), not in these files.

| File | What it was |
| --- | --- |
| `roadmaps/TECHNICAL_DEBT_ROADMAP.md` | March 2026 refactoring plan for the step pipeline |
| `roadmaps/FEATURE_ROADMAP.md` | March 2026 feature plan |
| `roadmaps/preflight-step-decomposition.md` | Spec for splitting `PreFlightStep` (superseded: steps were removed) |
| `pipeline_diagram.png` | Diagram of the former eight-step pipeline |
| `live-conversion-verification.json` | Verification data from the definition migration |
