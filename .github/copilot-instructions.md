# Autograder — Agent Skill Guide

This document provides AI agents with the architectural context needed to navigate and modify the Autograder codebase effectively.

---

## Project Architecture

The Autograder is a **pipeline-based grading system**. Submissions flow through ordered steps, each receiving a `PipelineExecution` object:

```
Load Template → Build Tree → Pre-Flight → Grade → Focus → Feedback → Export
```

### Module Layout

| Module | Purpose |
|--------|---------|
| `autograder/` | Core grading engine (pipeline, steps, services, models, templates) |
| `web/` | FastAPI REST API layer (routes, schemas, database, repositories) |
| `sandbox_manager/` | Docker container pool management for code execution |
| `github_action/` | GitHub Classroom integration adapter |
| `examples/` | Demo app and example configurations |
| `tests/` | Unit, integration, web, and performance tests |

### Key Abstractions

- **`AutograderPipeline`** (`autograder/autograder.py`) — Orchestrates step execution. Built via `build_pipeline()`.
- **`PipelineExecution`** (`autograder/models/pipeline_execution.py`) — Carries submission data and step results through the pipeline.
- **`Step`** (`autograder/models/abstract/step.py`) — ABC for pipeline steps. Each step implements `execute(pipeline_exec) -> PipelineExecution`.
- **`Template`** (`autograder/models/abstract/template.py`) — ABC for grading templates. Contains test function collections.
- **`TestFunction`** (`autograder/models/abstract/test_function.py`) — ABC for individual test logic. Implements `execute(files, sandbox, **kwargs) -> TestResult`.
- **`CriteriaTree`** / **`ResultTree`** (`autograder/models/`) — Tree structures for grading rubrics and their scored results.

---

## How To: Add a New API Endpoint

1. **Define schema** in `web/schemas/` (Pydantic `BaseModel` for request/response)
2. **Create route** in `web/api/v1/` (FastAPI `APIRouter` with endpoint function)
3. **Add repository** (if DB access needed) in `web/repositories/`
4. **Register router** in `web/api/v1/__init__.py` via `api_router.include_router()`
5. **Add tests** in `tests/web/`

Route prefix chain: `app → /api/v1 → /{router_prefix}`

---

## How To: Add a New Grading Template

1. **Create template file** in `autograder/template_library/` (e.g., `my_template.py`)
2. **Implement `Template` ABC**: define `template_name`, `template_description`, `requires_sandbox`, `get_test(name)`
3. **Implement test classes** extending `TestFunction` ABC: define `name`, `description`, `parameter_description`, `execute()`
4. **Register in `__init__.py`**: add to `TEMPLATE_REGISTRY` dict
5. **Add to `TemplateLibraryService`**: it auto-loads from `TEMPLATE_REGISTRY` at startup

---

## How To: Add a New Pipeline Step

1. **Create step class** in `autograder/steps/` extending `Step` ABC
2. **Add `StepName` enum value** in `autograder/models/dataclass/step_result.py`
3. **Wire into `build_pipeline()`** in `autograder/autograder.py`
4. **Store result** via `pipeline_exec.add_step_result(StepResult(...))`

---

## How To: Add a New Sandbox Language

1. **Add enum value** to `Language` in `sandbox_manager/models/sandbox_models.py`
2. **Create Dockerfile** in `sandbox_manager/images/Dockerfile.<lang>`
3. **Add pool config** in `sandbox_config.yml`
4. **Update `CommandResolver`** defaults in `autograder/services/command_resolver.py`

---

## Testing Conventions

| Directory | Scope | Requires Docker |
|-----------|-------|-----------------|
| `tests/unit/` | Pure logic, mocked dependencies | No |
| `tests/web/` | API routes, DB operations (mocked sandbox) | No |
| `tests/integration/` | Full pipeline with real sandboxes | Yes |
| `tests/performance/` | Load testing, stress testing | Yes |

Run unit tests: `pytest tests/unit/ -v`
Run web tests: `pytest tests/web/ -v`
Run integration tests: `pytest tests/integration/ -v` (requires Docker)

---

## Data Flow Through the Pipeline

```
Submission
  → TemplateLoaderStep    → StepResult.data = Template
  → BuildTreeStep         → StepResult.data = CriteriaTree
  → PreFlightStep         → StepResult.data = SandboxContainer (or None)
  → GradeStep             → StepResult.data = GradeStepResult (final_score + ResultTree)
  → FocusStep             → StepResult.data = Focus (sorted failed tests by impact)
  → FeedbackStep          → StepResult.data = feedback string
  → ExporterStep          → StepResult.data = None (side effect: external write)
```

Steps access previous results via: `pipeline_exec.get_step_result(StepName.X).data`

---

## Common Patterns

- **Services** (`autograder/services/`) contain business logic, used by steps
- **Models** (`autograder/models/`) are data structures (dataclasses, Pydantic, tree nodes)
- **Templates** (`autograder/template_library/`) contain test function implementations
- **Web schemas** (`web/schemas/`) are Pydantic models for API validation
- **Web repositories** (`web/repositories/`) wrap SQLAlchemy queries
- **Sandbox operations** go through `SandboxManager` → `LanguagePool` → `SandboxContainer`
