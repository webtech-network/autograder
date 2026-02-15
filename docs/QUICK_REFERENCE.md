# Autograder Quick Reference Guide

Quick lookup for common tasks, APIs, and configurations.

---

## Table of Contents
- [Building a Pipeline](#building-a-pipeline)
- [Configuration Schemas](#configuration-schemas)
- [API Reference](#api-reference)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)

---

## Building a Pipeline

### Minimal Example
```python
from autograder.autograder import build_pipeline

pipeline = build_pipeline(
    template_name="webdev",
    include_feedback=True,
    grading_criteria=criteria_dict,
    feedback_config=None,
    setup_config=None,
    custom_template=None,
    feedback_mode="default",
    export_results=False
)
```

### With Sandbox
```python
pipeline = build_pipeline(
    template_name="IO",
    include_feedback=True,
    grading_criteria=criteria_dict,
    feedback_config=feedback_dict,
    setup_config={},  # Empty dict triggers sandbox if template requires it
    feedback_mode="default",
    export_results=False
)
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `template_name` | str | Yes | Template identifier: "webdev", "IO", "api", "essay" |
| `include_feedback` | bool | Yes | Whether to generate feedback |
| `grading_criteria` | dict | Yes | Criteria configuration (see schema below) |
| `feedback_config` | dict | No | Feedback preferences |
| `setup_config` | dict | No | Preflight checks config. `None` = no preflight, `{}` = sandbox if needed |
| `custom_template` | Template | No | Custom template object |
| `feedback_mode` | str | No | "default" or "ai" |
| `export_results` | bool | No | Whether to export to external systems |

---

## Configuration Schemas

### Criteria Configuration

#### Simple Test
```python
{
    "base": {
        "weight": 100,
        "tests": [
            {
                "name": "has_tag",
                "file": "index.html",
                "parameters": [
                    {"name": "tag", "value": "nav"},
                    {"name": "required_count", "value": 1}
                ]
            }
        ]
    }
}
```

#### With Subjects
```python
{
    "base": {
        "weight": 100,
        "subjects": [
            {
                "subject_name": "HTML Structure",
                "weight": 50,
                "tests": [...]
            },
            {
                "subject_name": "CSS Styling",
                "weight": 50,
                "tests": [...]
            }
        ]
    }
}
```

#### With Bonus and Penalty
```python
{
    "base": {
        "weight": 100,
        "subjects": [...]
    },
    "bonus": {
        "weight": 20,  # Adds up to 20 points
        "tests": [...]
    },
    "penalty": {
        "weight": 10,  # Subtracts up to 10 points
        "tests": [...]
    }
}
```

#### Nested Subjects (Recursive)
```python
{
    "base": {
        "weight": 100,
        "subjects": [
            {
                "subject_name": "HTML",
                "weight": 100,
                "subjects": [  # Nested!
                    {
                        "subject_name": "Structure",
                        "weight": 50,
                        "tests": [...]
                    },
                    {
                        "subject_name": "Content",
                        "weight": 50,
                        "tests": [...]
                    }
                ]
            }
        ]
    }
}
```

#### Heterogeneous Tree (Mixed Subjects and Tests)
```python
{
    "subject_name": "HTML",
    "weight": 100,
    "subjects_weight": 70,  # 70% for subjects, 30% for tests
    "subjects": [
        {
            "subject_name": "Navigation",
            "weight": 50,
            "tests": [...]
        },
        {
            "subject_name": "Content",
            "weight": 50,
            "tests": [...]
        }
    ],
    "tests": [  # Direct tests at this level
        {
            "name": "has_doctype",
            "file": "index.html"
        }
    ]
}
```

### Feedback Configuration

```python
{
    "general": {
        "report_title": "Assignment Report",
        "show_score": True,
        "show_passed_tests": False,
        "add_report_summary": True
    },
    "default": {
        "category_headers": {
            "base": "✅ Required",
            "bonus": "⭐ Bonus",
            "penalty": "❌ Issues"
        }
    },
    "ai": {
        "provide_solutions": "hint",  # "none" | "hint" | "detailed"
        "feedback_tone": "encouraging",
        "feedback_persona": "Code Mentor",
        "assignment_context": "Bootstrap portfolio project",
        "extra_orientations": "Focus on accessibility",
        "submission_files_to_read": ["index.html", "style.css"]
    }
}
```

### Setup Configuration

```python
{
    "required_files": [
        "index.html",
        "style.css",
        "images/"
    ],
    "setup_commands": [
        "pip install -r requirements.txt",
        "npm install"
    ]
}
```

---

## API Reference

### Core Classes

#### AutograderPipeline
```python
pipeline = AutograderPipeline()
pipeline.add_step(StepName.LOAD_TEMPLATE, TemplateLoaderStep(...))
result = pipeline.run(submission)
```

**Methods:**
- `add_step(step_name: StepName, step: Step)` - Add a step to pipeline
- `run(submission: Submission) -> PipelineExecution` - Execute pipeline

#### PipelineExecution
```python
execution = PipelineExecution.start_execution(submission)
execution.add_step_result(step_result)
result = execution.get_step_result(StepName.GRADE)
```

**Properties:**
- `step_results: List[StepResult]` - All step results
- `status: PipelineStatus` - Current status
- `result: GradingResult` - Final result (after finish_execution)
- `submission: Submission` - The submission being graded

**Methods:**
- `add_step_result(result: StepResult) -> PipelineExecution`
- `get_step_result(step_name: StepName) -> StepResult`
- `has_step_result(step_name: StepName) -> bool`
- `get_previous_step() -> Optional[StepResult]`
- `finish_execution()` - Finalize and create GradingResult

#### Submission
```python
submission = Submission(
    username="john.doe",
    user_id="student123",
    assignment_id=42,
    submission_files={
        "file.html": SubmissionFile("file.html", "<html>...")
    },
    language=Language.PYTHON  # Optional, needed for I/O and API
)
```

#### GradingResult
```python
result = pipeline_execution.result

print(result.final_score)  # 0-100
print(result.feedback)     # String or None
print(result.result_tree)  # ResultTree object
```

#### ResultTree
```python
tree = grading_result.result_tree

final_score = tree.calculate_final_score()
all_tests = tree.get_all_test_results()
failed = tree.get_failed_tests()
passed = tree.get_passed_tests()
dict_repr = tree.to_dict()
```

### Enums

#### PipelineStatus
```python
class PipelineStatus(Enum):
    EMPTY = "empty"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
```

#### StepName
```python
class StepName(Enum):
    BOOTSTRAP = "BootstrapStep"
    LOAD_TEMPLATE = "LoadTemplateStep"
    BUILD_TREE = "BuildTreeStep"
    PRE_FLIGHT = "PreFlightStep"
    GRADE = "GradeStep"
    FOCUS = "FocusStep"
    FEEDBACK = "FeedbackStep"
    EXPORTER = "ExporterStep"
```

#### Language
```python
class Language(Enum):
    PYTHON = "python"
    JAVA = "java"
    NODE = "node"
    CPP = "cpp"
```

---

## Common Patterns

### Pattern 1: Simple Static Analysis
```python
# For HTML/CSS/JS validation (no code execution)

pipeline = build_pipeline(
    template_name="webdev",
    include_feedback=True,
    grading_criteria=webdev_criteria,
    feedback_config=feedback_config,
    setup_config=None,  # No sandbox needed
    feedback_mode="default"
)

submission = Submission(
    username="student",
    user_id="123",
    assignment_id=1,
    submission_files={
        "index.html": SubmissionFile("index.html", html_content),
        "style.css": SubmissionFile("style.css", css_content)
    }
)

result = pipeline.run(submission)
```

### Pattern 2: Code Execution with Sandbox
```python
# For I/O programs or APIs

# Initialize sandbox manager (once at startup)
from sandbox_manager.manager import initialize_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig

pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
manager = initialize_sandbox_manager(pool_configs)

# Build pipeline
pipeline = build_pipeline(
    template_name="IO",
    include_feedback=True,
    grading_criteria=io_criteria,
    setup_config={},  # Creates sandbox
    feedback_mode="default"
)

# Create submission with language
submission = Submission(
    username="student",
    user_id="123",
    assignment_id=2,
    submission_files={
        "program.py": SubmissionFile("program.py", python_code)
    },
    language=Language.PYTHON  # Required!
)

# Grade
result = pipeline.run(submission)

# Cleanup on shutdown
manager.shutdown()
```

### Pattern 3: Reusing Pipeline
```python
# Build once
pipeline = build_pipeline(...)

# Grade many submissions
results = []
for student_submission in submissions:
    result = pipeline.run(student_submission)
    results.append(result)
```

### Pattern 4: AI Feedback
```python
pipeline = build_pipeline(
    template_name="webdev",
    include_feedback=True,
    grading_criteria=criteria,
    feedback_config={
        "ai": {
            "provide_solutions": "hint",
            "feedback_tone": "encouraging",
            "feedback_persona": "Friendly Mentor",
            "assignment_context": "Portfolio website"
        }
    },
    feedback_mode="ai"  # Use AI reporter
)
```

### Pattern 5: Web API Integration
```python
# In FastAPI endpoint

@app.post("/submissions")
async def submit(
    assignment_id: str,
    username: str,
    files: dict
):
    # Get config from database
    config = await get_grading_config(assignment_id)
    
    # Create submission record
    submission_id = await create_submission_record(...)
    
    # Queue background task
    BackgroundTasks.add_task(
        grade_submission,
        submission_id=submission_id,
        config=config,
        files=files
    )
    
    return {"submission_id": submission_id, "status": "PENDING"}

async def grade_submission(submission_id, config, files):
    # Build pipeline
    pipeline = build_pipeline(
        template_name=config.template_name,
        grading_criteria=config.criteria,
        ...
    )
    
    # Grade
    result = pipeline.run(create_submission(files))
    
    # Store results
    await save_results(submission_id, result)
```

---

## Troubleshooting

### Issue: Pipeline Returns FAILED Status

**Check:**
```python
if result.status == PipelineStatus.FAILED:
    last_step = result.get_previous_step()
    print(f"Failed at: {last_step.step}")
    print(f"Error: {last_step.error}")
```

**Common Causes:**
- Missing required files (PreFlight step)
- Setup commands failed (PreFlight step)
- Test function not found in template (BuildTree step)
- Invalid criteria configuration (BuildTree step)

### Issue: Score is 0 Despite Passing Tests

**Check:**
```python
# Verify test scores
tree = result.result.result_tree
for test in tree.get_all_test_results():
    print(f"{test.name}: {test.score}")

# Check weight configuration
print(tree.to_dict())
```

**Common Causes:**
- Tests have weight=0
- Parent subject/category has weight=0
- Weight balancing issue

### Issue: Sandbox Creation Fails

**Check:**
1. Docker is running: `docker ps`
2. Images are built: `docker images | grep sandbox`
3. Pool configuration: `sandbox_config.yml`

**Build sandbox images:**
```bash
make sandbox-build-all
```

### Issue: Template Not Found

**Error:** `Template 'WebDev' not found`

**Solution:** Template names are lowercase
```python
# ❌ Wrong
template_name="WebDev"

# ✅ Correct
template_name="webdev"
```

**Available templates:**
- `"webdev"`
- `"IO"` or `"io"`
- `"api"`
- `"essay"`

### Issue: Test Function Not Found

**Error:** `Test 'has_tag' not found in template`

**Check:**
```python
# List available tests
from autograder.template_library.web_dev import WebDevTemplate
template = WebDevTemplate()
print(list(template.tests.keys()))
```

### Issue: Heterogeneous Tree Error

**Error:** `Subject needs 'subjects_weight' defined`

**Solution:** When mixing subjects and tests, specify `subjects_weight`
```python
{
    "subject_name": "HTML",
    "weight": 100,
    "subjects_weight": 70,  # Must be present!
    "subjects": [...],
    "tests": [...]
}
```

### Issue: Weights Don't Sum to 100

**Don't worry!** Weights are automatically balanced.

```python
# Input
subjects = [
    {"weight": 60},
    {"weight": 80}
]
# Total: 140

# Automatic balancing
# Subject 1: 60/140 * 100 = 42.86
# Subject 2: 80/140 * 100 = 57.14
# Total: 100 ✓
```

---

## Performance Tips

### 1. Reuse Pipelines
```python
# ❌ Bad: Building pipeline for each submission
for submission in submissions:
    pipeline = build_pipeline(...)  # Expensive!
    result = pipeline.run(submission)

# ✅ Good: Build once, reuse
pipeline = build_pipeline(...)
for submission in submissions:
    result = pipeline.run(submission)
```

### 2. Pre-warm Sandbox Pools
```yaml
# sandbox_config.yml
- language: PYTHON
  min_containers: 3  # Higher min = faster acquisition
  max_containers: 10
```

### 3. Use Default Feedback for Speed
```python
# AI feedback is slower (OpenAI API call)
feedback_mode="default"  # Faster

# vs
feedback_mode="ai"  # Slower but more personalized
```

### 4. Limit Submission File Reads for AI
```python
{
    "ai": {
        "submission_files_to_read": ["main.py"]  # Only essential files
    }
}
```

---

## Environment Variables

```bash
# OpenAI API (for AI feedback)
OPENAI_API_KEY=sk-...

# Database (for Web API)
DATABASE_URL=postgresql://user:pass@localhost/autograder

# Sandbox (optional overrides)
DOCKER_HOST=unix:///var/run/docker.sock
```

---

## CLI Commands

### Build Sandbox Images
```bash
make sandbox-build-all          # All languages
make sandbox-build-python       # Python only
make sandbox-build-java         # Java only
make sandbox-build-node         # Node.js only
make sandbox-build-cpp          # C++ only
```

### Clean Sandbox Images
```bash
make sandbox-clean
```

### Run API Server
```bash
make run-api
```

### Run Tests
```bash
make sandbox-test
```

---

## File Locations

```
autograder/
├── autograder.py                    # build_pipeline() function
├── models/
│   ├── criteria_tree.py             # CriteriaTree, CategoryNode, etc.
│   ├── result_tree.py               # ResultTree, result nodes
│   ├── pipeline_execution.py        # PipelineExecution
│   └── dataclass/
│       ├── submission.py            # Submission, SubmissionFile
│       ├── grading_result.py        # GradingResult
│       └── step_result.py           # StepResult, StepStatus
├── services/
│   ├── criteria_tree_service.py     # Tree building
│   ├── grader_service.py            # Test execution
│   ├── focus_service.py             # Impact analysis
│   └── report/
│       ├── reporter_service.py      # Feedback factory
│       ├── default_reporter.py      # Structured feedback
│       └── ai_reporter.py           # AI feedback
├── steps/
│   ├── load_template_step.py
│   ├── build_tree_step.py
│   ├── pre_flight_step.py
│   ├── grade_step.py
│   ├── focus_step.py
│   └── feedback_step.py
└── template_library/
    ├── web_dev.py
    ├── input_output.py
    ├── api_testing.py
    └── essay.py (if exists)

sandbox_manager/
├── manager.py                       # SandboxManager
├── language_pool.py                 # LanguagePool
├── sandbox_container.py             # SandboxContainer
└── models/
    ├── pool_config.py               # SandboxPoolConfig
    └── sandbox_models.py            # Language enum

web/
├── main.py                          # FastAPI app
├── database/
│   └── models.py                    # Database models
└── repositories/
    ├── grading_config_repository.py
    ├── submission_repository.py
    └── result_repository.py
```

---

## Support

For detailed information, see:
- [Complete System Documentation](./COMPLETE_SYSTEM_DOCUMENTATION.md)
- [Visual Diagrams](./VISUAL_DIAGRAMS.md)
- [README](./README.md)

