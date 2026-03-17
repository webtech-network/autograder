# 📚 Autograder Documentation

Welcome to the Autograder documentation. This index organizes all available documentation by topic.

---

## Getting Started

| Document | Description |
|----------|-------------|
| [README](../README.md) | Project overview, features, and quick start |
| [Development Guide](guides/development.md) | Setup, project structure, and contributing |
| [Configuration Examples](guides/criteria_configuration_examples.md) | Real-world grading configuration examples |

## API Reference

| Document | Description |
|----------|-------------|
| [API Documentation](API.md) | Complete REST API reference — all endpoints, schemas, and examples |
| [Web Module Architecture](architecture/web_module.md) | Web layer architecture, deployment, database configuration, and troubleshooting |

## Grading Templates

| Document | Description |
|----------|-------------|
| [Input/Output Template](templates/input_output.md) | Test command-line programs with stdin/stdout validation |
| [Web Development Template](templates/web_dev.md) | Validate HTML, CSS, and JavaScript (36 test functions) |
| [API Testing Template](templates/api_testing.md) | Test student-built web APIs via HTTP requests |

## Features

| Document | Description |
|----------|-------------|
| [Deliberate Code Execution](features/deliberate_code_execution.md) | Execute code without grading (DCE feature) |
| [Focus Feature](features/focus_feature.md) | Focus-based feedback highlighting high-impact improvements |
| [Grading Engine](features/grading_engine.md) | Deep dive on the tree-based grading engine (traversal, weights, scoring) |
| [Setup Config](features/setup_config_feature.md) | Preflight checks, required files, and setup commands |
| [Setup Config Quick Start](guides/SETUP_CONFIG_QUICK_START.md) | Quick guide for setup configuration |
| [Command Resolver & Multi-Language Support](features/command_resolver.md) | Python, Java, Node.js, C and C++ support |
| [Pipeline Execution Tracking](architecture/pipeline_execution_tracking.md) | Step-by-step pipeline execution details |
| [GitHub Action](guides/github_module.md) | GitHub Classroom integration |

## Pipeline

| Document | Description |
|----------|-------------|
| [Pipeline Overview](pipeline/README.md) | Architecture, PipelineExecution, assembly rules, step dependency table |
| [Load Template Step](pipeline/01-load-template.md) | Loads the grading template with test functions |
| [Build Tree Step](pipeline/02-build-tree.md) | Constructs the CriteriaTree from JSON config |
| [Pre-Flight Step](pipeline/03-pre-flight.md) | Validates files, creates sandbox, runs setup commands |
| [Grade Step](pipeline/04-grade.md) | Executes tests and produces the scored ResultTree |
| [Focus Step](pipeline/05-focus.md) | Ranks tests by impact on the final score |
| [Feedback Step](pipeline/06-feedback.md) | Generates student-facing feedback reports |
| [Export Step](pipeline/07-export.md) | Sends scores to external systems |

## Architecture & Data Structures

| Document | Description |
|----------|-------------|
| [Core Data Structures](architecture/core_structures.md) | CriteriaTree, ResultTree, Submission, GradingResult, and more |
| [Sandbox Manager](architecture/sandbox_manager.md) | Container pooling, lifecycle, scaling, and security |
| [Criteria Example](criteria_example.json) | Example criteria tree configuration (JSON) |

## Project Management

| Document | Description |
|----------|-------------|
| [Technical Debt Roadmap](roadmaps/TECHNICAL_DEBT_ROADMAP.md) | Refactoring plan for architecture cohesion and code quality |
