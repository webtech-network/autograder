# Autograder Documentation

This documentation is organized to be both practical for first-time users and deep enough for maintainers working on the grading engine internals.

## Start Here

1. [Responsibilities and Dependencies](architecture/overview.md): the current map of who owns what
2. [Pipeline Architecture](core/pipeline-architecture.md)
3. [Criteria Tree](core/criteria-tree.md)
4. [Sandbox Management](core/sandbox-management.md)
5. [Template Library](core/template-library.md)
6. [Feedback Generation](core/feedback-generation.md)

## Learning Paths

### Educator or instructional designer

- [Educational Criteria Design Guide](guides/criteria-tree-educational-standards.md)
- [Criteria Configuration Examples](guides/criteria_configuration_examples.md)
- [Feedback Generation](core/feedback-generation.md)

### Backend maintainer

- [Responsibilities and Dependencies](architecture/overview.md)
- [Pipeline Architecture](core/pipeline-architecture.md)
- [Grading Operations](pipeline/README.md)
- [Core Values](architecture/core_structures.md)
- [Sandbox Manager Internals](architecture/sandbox_manager.md)

### Template author

- [Adding an Evaluator](architecture/extending.md)
- [Template Library](core/template-library.md)
- [Input/Output Template](template-library/input_output.md)
- [API Testing Template](template-library/api_testing.md)
- [Web Development Template](template-library/web_dev.md)
- [Static Analysis Template](template-library/static_analysis.md)

### GitHub Actions / CI integrator

- [GitHub Action module overview](github_action/README.md)
- [GitHub Action configuration reference](github_action/configuration.md)
- [Demo repository walkthrough](github_action/quick-start.md)

## Quick Access

| Area | Entry Point |
|------|-------------|
| API reference | [API.md](API.md) |
| GitHub Action | [github_action/README.md](github_action/README.md) |
| Grading operations | [pipeline/README.md](pipeline/README.md) |
| Integration contracts | [contracts/DECISIONS.md](contracts/DECISIONS.md) |
| Features | [features/grading_engine.md](features/grading_engine.md) |
| Development setup | [guides/development.md](guides/development.md) |
