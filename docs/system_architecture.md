# System Architecture

## Overview

The autograder follows a **Hexagonal Architecture** (also known as Ports and Adapters pattern), which ensures the core grading logic remains **isolated, reusable, and environment-agnostic**. This architecture allows the system to be deployed in multiple contexts (GitHub Actions, web APIs, CLI, etc.) without modifying the core logic.

---

## Architectural Principles

### 1. **Core Isolation**
The autograder core is completely isolated from external systems. It doesn't know or care about:
- Where the code is running (GitHub, API server, local machine)
- How requests arrive (HTTP, GitHub Actions, CLI)
- Where results are sent (files, HTTP response, database)

### 2. **Standardized Communication**
All communication with the core happens through two standardized objects:
- **Input**: `AutograderRequest` (what to grade)
- **Output**: `AutograderResponse` (grading results)

### 3. **Adapter Pattern**
Environment-specific logic is handled by **connectors** (adapters) that:
- Translate environment-specific inputs into `AutograderRequest`
- Process `AutograderResponse` and deliver results appropriately
- Handle environment-specific concerns (file I/O, HTTP, logging)

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL ENVIRONMENTS                         │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   GitHub     │  │   Web API    │  │     CLI      │             │
│  │   Actions    │  │   Server     │  │   Interface  │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                  │                  │                      │
└─────────┼──────────────────┼──────────────────┼──────────────────────┘
          │                  │                  │
          │                  │                  │
┌─────────┼──────────────────┼──────────────────┼──────────────────────┐
│         │    CONNECTOR LAYER (Inbound Ports)  │                      │
│         ▼                  ▼                  ▼                      │
│  ┌─────────────┐    ┌─────────────┐   ┌─────────────┐             │
│  │   GitHub    │    │     API     │   │     CLI     │             │
│  │  Connector  │    │  Connector  │   │  Connector  │             │
│  └──────┬──────┘    └──────┬──────┘   └──────┬──────┘             │
│         │                   │                  │                     │
│         └───────────────────┴──────────────────┘                     │
│                             │                                        │
│                             ▼                                        │
│                  ┌─────────────────────┐                            │
│                  │ AutograderRequest   │                            │
│                  │  - submission_files │                            │
│                  │  - assignment_config│                            │
│                  │  - student_name     │                            │
│                  │  - feedback_mode    │                            │
│                  │  - credentials      │                            │
│                  └──────────┬──────────┘                            │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AUTOGRADER CORE (Isolated)                      │
│                                                                      │
│                    ┌─────────────────────┐                          │
│                    │  Autograder Facade  │                          │
│                    │   (Orchestrator)    │                          │
│                    └──────────┬──────────┘                          │
│                               │                                      │
│              ┌────────────────┴────────────────┐                    │
│              ▼                                  ▼                    │
│    ┌──────────────────┐              ┌──────────────────┐          │
│    │  BUILDER LAYER   │              │   CORE LAYER     │          │
│    │                  │              │                  │          │
│    │ • PreFlight      │──────────────▶│ • Grader        │          │
│    │ • CriteriaTree   │              │ • Reporter      │          │
│    │ • Template       │              │ • Result        │          │
│    │   Library        │              │   Processor     │          │
│    │ • Execution      │              │                  │          │
│    │   Helpers        │              │                  │          │
│    └──────────────────┘              └──────────────────┘          │
│                                                                      │
│                    ┌─────────────────────┐                          │
│                    │ AutograderResponse  │                          │
│                    │  - status           │                          │
│                    │  - final_score      │                          │
│                    │  - feedback         │                          │
│                    │  - test_report      │                          │
│                    └──────────┬──────────┘                          │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────────┐
│         │    CONNECTOR LAYER (Result Processing) │                  │
│         ▼                   ▼                  ▼                     │
│  ┌─────────────┐    ┌─────────────┐   ┌─────────────┐             │
│  │   GitHub    │    │     API     │   │     CLI     │             │
│  │  (Export)   │    │  (Export)   │   │  (Export)   │             │
│  └──────┬──────┘    └──────┬──────┘   └──────┬──────┘             │
│         │                   │                  │                     │
└─────────┼───────────────────┼──────────────────┼─────────────────────┘
          │                   │                  │
          ▼                   ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        RESULT DELIVERY                               │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ .md file in  │  │ HTTP JSON    │  │  Console     │             │
│  │ student repo │  │  Response    │  │  Output      │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Layer Breakdown

### 1. Connector Layer (Ports)

**Purpose**: Adapts external environments to communicate with the isolated core.

**Responsibilities**:
- Parse environment-specific inputs
- Assemble standardized `AutograderRequest`
- Process `AutograderResponse` and deliver results appropriately

#### Available Connectors

##### GitHub Action Connector

**Environment**: GitHub Actions workflow  
**Location**: `connectors/adapters/github_action_adapter/`

**Inbound Flow**:
1. GitHub Action triggered on push/PR
2. Connector reads configuration from `.github/` folder:
   - `criteria.json`
   - `feedback.json`
   - `setup.json`
3. Collects student submission files from repository
4. Extracts student name from GitHub context
5. Assembles `AutograderRequest`

**Outbound Flow**:
1. Receives `AutograderResponse`
2. Formats feedback as Markdown
3. Commits `FEEDBACK.md` to student's repository
4. Optionally posts comment on PR

**Use Case**: Automatic grading on student repository submissions

---

##### API Connector

**Environment**: Web server (Flask/FastAPI)  
**Location**: `connectors/adapters/api/`

**Inbound Flow**:
1. HTTP POST request received with JSON payload
2. Validates request structure
3. Parses JSON into `AutograderRequest` components
4. Handles file uploads or base64-encoded files

**Outbound Flow**:
1. Receives `AutograderResponse`
2. Serializes to JSON
3. Returns HTTP response with:
   - Status code
   - Final score
   - Feedback text
   - Test report array

**Use Case**: Web-based grading systems, LMS integration, remote grading services

---

##### CLI Connector

**Environment**: Command-line interface  
**Location**: `connectors/adapters/cli/`

**Inbound Flow**:
1. User runs command: `autograder grade --config config.json --files ./submission/`
2. Reads config files from filesystem
3. Loads submission files from directory
4. Assembles `AutograderRequest`

**Outbound Flow**:
1. Receives `AutograderResponse`
2. Pretty-prints results to console
3. Optionally writes to output file

**Use Case**: Local testing, batch grading, development workflow

---

### 2. Autograder Core

**Purpose**: Contains all grading logic, completely isolated from external systems.

**Characteristics**:
- ✅ Environment-agnostic (doesn't know about GitHub, HTTP, files)
- ✅ Testable in isolation
- ✅ Reusable across different deployment contexts
- ✅ Standardized input/output contracts

**Entry Point**: `AutograderFacade.grade(autograder_request)`

---

#### Autograder Facade (Orchestrator)

**Location**: `autograder/autograder_facade.py`

**Purpose**: Coordinates the entire grading process, acting as the single entry point for the core system.

**Responsibilities**:
1. Receive and validate `AutograderRequest`
2. Set global context for request access
3. Coordinate Builder Layer operations
4. Coordinate Core Layer operations
5. Handle errors and edge cases
6. Return `AutograderResponse`

**Process Flow**:
```python
def grade(autograder_request: AutograderRequest) -> AutograderResponse:
    # 1. Set global context
    request_context.set_request(autograder_request)
    
    # 2. Run pre-flight checks (Builder Layer)
    if autograder_request.assignment_config.setup:
        impediments = PreFlight.run()
        if impediments:
            return AutograderResponse("fail", 0.0, error_messages)
    
    # 3. Load template (Builder Layer)
    template = TemplateLibrary.get_template(template_name)
    
    # 4. Build criteria tree (Builder Layer)
    if template.requires_pre_executed_tree:
        criteria_tree = CriteriaTree.build_pre_executed_tree(template)
    else:
        criteria_tree = CriteriaTree.build_non_executed_tree()
    
    # 5. Initialize grader (Core Layer)
    grader = Grader(criteria_tree, template)
    
    # 6. Run grading (Core Layer)
    result = grader.run()
    
    # 7. Generate feedback (Core Layer)
    if autograder_request.include_feedback:
        feedback_prefs = FeedbackPreferences.from_dict()
        reporter = Reporter.create(feedback_mode, result, feedback_prefs)
        feedback_text = reporter.generate_feedback()
    
    # 8. Return response
    return AutograderResponse(
        status="Success",
        final_score=result.final_score,
        feedback=feedback_text,
        test_report=result.all_test_results
    )
```

---

#### Builder Layer

**Purpose**: Prepares everything needed for the grading process to execute.

**Location**: `autograder/builder/`

**Components**:

##### 1. **PreFlight** (`pre_flight.py`)

**Responsibility**: Validates submission before grading begins

**Operations**:
- Checks for required files (from `setup.json`)
- Validates project structure
- Executes setup commands if needed
- Returns fatal errors if checks fail

**Example**:
```python
impediments = PreFlight.run()
# impediments = [
#   {"type": "file_check", "message": "File 'index.html' not found"}
# ]
```

##### 2. **CriteriaTree** (`tree_builder.py`)

**Responsibility**: Builds the grading criteria tree structure

**Operations**:
- Parses `criteria.json` configuration
- Creates tree structure (categories → subjects → tests)
- Balances subject weights
- Maps test names to template functions
- Optionally pre-executes tests (for AI batching)

**Output**: `Criteria` object with hierarchical test structure

##### 3. **TemplateLibrary** (`template_library/library.py`)

**Responsibility**: Loads and manages test templates

**Operations**:
- Retrieves pre-built templates (`web dev`, `api`, `essay`, `I/O`)
- Dynamically loads custom templates from code strings
- Initializes execution helpers (sandbox, AI executor)

**Output**: `Template` object with test functions

##### 4. **Execution Helpers** (`execution_helpers/`)

**Responsibility**: Provides complex infrastructure for test execution

**Available Helpers**:

- **SandboxExecutor**: Docker container management
  - Creates isolated environment
  - Copies student files
  - Executes commands
  - Manages cleanup

- **AiExecutor**: Batch AI test processing
  - Collects AI-powered tests
  - Sends batch request to OpenAI
  - Maps results back to tests
  - Optimizes API usage

---

#### Core Layer

**Purpose**: Executes the actual grading and generates feedback.

**Location**: `autograder/core/`

**Components**:

##### 1. **Grader** (`grading/grader.py`)

**Responsibility**: Traverses criteria tree and executes tests

**Process**:
```
1. Start with root categories (base, bonus, penalty)
2. Recursively traverse subjects
3. At each leaf (test), execute:
   - Get test function from template
   - Pass file content + parameters
   - Receive TestResult
4. Calculate weighted scores per subject
5. Apply scoring algorithm (base + bonus - penalty)
6. Return Result object
```

**Scoring Algorithm**:
```python
final_score = base_score

if final_score < 100:
    bonus_to_add = min(bonus_score, 100 - final_score)
    final_score += bonus_to_add

penalty_to_subtract = (penalty_score / 100) * penalty_weight
final_score -= penalty_to_subtract

final_score = max(0, min(100, final_score))
```

**Output**: `Result` object with:
- `final_score`: Calculated grade
- `base_results`: List of base test results
- `bonus_results`: List of bonus test results
- `penalty_results`: List of penalty test results
- `submission_files`: Original files
- `author`: Student name

##### 2. **Reporter** (`report/`)

**Responsibility**: Generates human-readable feedback from test results

**Available Reporters**:

- **DefaultReporter** (`default_reporter.py`)
  - Structured, template-based feedback
  - Shows passed/failed tests
  - Categorized by base/bonus/penalty
  - Includes linked learning resources
  - Fast and deterministic

- **AIReporter** (`ai_reporter.py`)
  - Context-aware AI-generated feedback
  - Analyzes submission files
  - Explains causes and consequences
  - Personalized tone and persona
  - Provides hints or solutions based on configuration

**Reporter Factory** (`reporter_factory.py`):
```python
if feedback_mode == "default":
    reporter = Reporter.create_default_reporter(result, feedback_prefs)
elif feedback_mode == "AI":
    reporter = Reporter.create_ai_reporter(result, feedback_prefs)

feedback_text = reporter.generate_feedback()
```

##### 3. **Result Processor** (`utils/result_processor.py`)

**Responsibility**: Processes and aggregates test results

**Operations**:
- Filters results by category
- Calculates statistics (pass rate, average score)
- Groups results by subject
- Prepares data for reporting

---

## Data Flow: Complete Grading Session

Let's trace a complete request through the system:

### Example: GitHub Action Grading

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. TRIGGER: Student pushes code to GitHub repository           │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. GITHUB CONNECTOR (Inbound)                                  │
│    • Reads .github/criteria.json                               │
│    • Reads .github/feedback.json                               │
│    • Reads .github/setup.json                                  │
│    • Collects submission files from repo                       │
│    • Extracts student name from GitHub context                 │
│    • Creates AssignmentConfig                                  │
│    • Assembles AutograderRequest:                              │
│      - submission_files: {"index.html": "...", "app.js": "..."}│
│      - assignment_config: AssignmentConfig(...)                │
│      - student_name: "alice123"                                │
│      - feedback_mode: "AI"                                     │
│      - openai_key: <from secrets>                              │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. AUTOGRADER FACADE                                            │
│    • Receives AutograderRequest                                │
│    • Sets global context                                       │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. BUILDER LAYER                                                │
│                                                                 │
│ 4a. PreFlight                                                   │
│     • Checks for index.html ✓                                  │
│     • Checks for app.js ✓                                      │
│     • No impediments found                                     │
│                                                                 │
│ 4b. TemplateLibrary                                             │
│     • Loads "web dev" template                                 │
│     • Initializes test functions                               │
│     • No execution helpers needed                              │
│                                                                 │
│ 4c. CriteriaTree                                                │
│     • Parses criteria.json                                     │
│     • Builds tree structure:                                   │
│       Root                                                      │
│       ├── Base (100 pts)                                       │
│       │   ├── HTML (60 pts)                                    │
│       │   │   ├── Structure (24 pts)                           │
│       │   │   │   ├── has_tag tests                            │
│       │   │   │   └── has_attribute tests                      │
│       │   │   └── Links (12 pts)                               │
│       │   └── CSS (40 pts)                                     │
│       ├── Bonus (40 pts)                                       │
│       └── Penalty (50 pts)                                     │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. CORE LAYER - GRADER                                          │
│                                                                 │
│ 5a. Initialize Grader                                           │
│     • grader = Grader(criteria_tree, template)                 │
│                                                                 │
│ 5b. Execute Base Tests                                          │
│     • HTML Structure tests:                                    │
│       - has_tag("body", 1) → 100/100 ✓                        │
│       - has_tag("header", 1) → 100/100 ✓                      │
│       - has_tag("article", 4) → 50/100 (only 2 found) ✗       │
│     • CSS tests:                                                │
│       - uses_relative_units() → 100/100 ✓                     │
│       - check_media_queries() → 80/100 ⚠                      │
│     • Base Score: 82/100                                       │
│                                                                 │
│ 5c. Execute Bonus Tests                                         │
│     • check_all_images_have_alt() → 100/100 ✓                 │
│     • Bonus Score: 40/40                                       │
│                                                                 │
│ 5d. Execute Penalty Tests                                       │
│     • check_bootstrap_usage() → 0/100 (not found) ✓           │
│     • has_forbidden_tag("script") → 100/100 (found!) ✗        │
│     • Penalty Score: 25/50                                     │
│                                                                 │
│ 5e. Calculate Final Score                                       │
│     • final = 82 (base)                                        │
│     • final += 18 (bonus, capped at 100)                       │
│     • final = 100                                              │
│     • final -= 12.5 (penalty: 25/50 * 50 weight)              │
│     • FINAL SCORE: 87.5/100                                    │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. CORE LAYER - REPORTER (AI Mode)                             │
│                                                                 │
│    • AIReporter analyzes:                                       │
│      - Test results (passed/failed)                            │
│      - Submission files (index.html, app.js)                   │
│      - Assignment context from feedback.json                   │
│                                                                 │
│    • Sends to OpenAI with:                                      │
│      - Feedback tone: "friendly and encouraging"               │
│      - Feedback persona: "Code Buddy"                          │
│      - Provide solutions: "hint"                               │
│                                                                 │
│    • Generates feedback:                                        │
│      "Great work, alice123! Your HTML structure is solid...    │
│       However, I noticed you're only using 2 <article> tags... │
│       Hint: Consider breaking down your content into 4...      │
│       Also, I see a <script> tag in your HTML. For this...     │
│       Final Score: 87.5/100"                                   │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. AUTOGRADER FACADE                                            │
│    • Creates AutograderResponse:                               │
│      - status: "Success"                                       │
│      - final_score: 87.5                                       │
│      - feedback: <AI-generated text>                           │
│      - test_report: [TestResult, TestResult, ...]              │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. GITHUB CONNECTOR (Outbound)                                 │
│    • Formats feedback as Markdown                              │
│    • Creates FEEDBACK.md file                                  │
│    • Commits to student repository                             │
│    • Posts comment on PR: "Grading complete! Score: 87.5/100"  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Benefits of Hexagonal Architecture

### 1. **Environment Independence**
The core grading logic can run in any environment without modification:
- GitHub Actions
- AWS Lambda
- Local CLI
- Kubernetes cluster
- Jupyter Notebook

### 2. **Testability**
Core can be tested in complete isolation:
```python
# Unit test without any external dependencies
def test_grading_logic():
    request = AutograderRequest(
        submission_files={"test.py": "print('hello')"},
        assignment_config=mock_config,
        student_name="test_user"
    )
    response = Autograder.grade(request)
    assert response.final_score == 85.0
```

### 3. **Reusability**
Same core logic serves multiple use cases:
- Instructor web dashboard
- Student self-assessment tool
- Automated CI/CD pipeline
- LMS integration

### 4. **Maintainability**
Changes to connectors don't affect core:
- Add new connector for Gradescope → No core changes
- Update GitHub API → Only GitHub connector affected
- Change feedback format → Only reporter affected

### 5. **Extensibility**
Easy to add new capabilities:
- New test templates → Add to `template_library/`
- New feedback mode → Add new reporter
- New deployment → Create new connector

---

## Component Isolation Benefits

### Builder Layer ↔ Core Layer Separation

**Why separate?**

The Builder Layer prepares data structures, while the Core Layer processes them. This separation allows:

1. **Independent evolution**: Change tree building logic without affecting grading
2. **Different modes**: Pre-executed trees for AI batching vs. lazy execution for simple tests
3. **Clear responsibilities**: Builder assembles, Core executes

**Communication**:
```
Builder Layer produces: Criteria tree, Template
Core Layer consumes: Criteria tree, Template
Core Layer produces: Result
Builder Layer (cleanup): Stops execution helpers
```

---

## Security Considerations

### 1. **Code Isolation**
Student code runs in Docker containers (via SandboxExecutor):
- No access to host filesystem
- Limited network access
- Resource constraints (CPU, memory)
- Automatic cleanup

### 2. **API Key Management**
- Keys passed through `AutograderRequest`
- Never stored in core or connectors
- Set as environment variables only during grading
- Cleared after session

### 3. **Submission Validation**
- PreFlight checks validate file structure
- File size limits enforced by connectors
- Malformed JSON caught before core processing

---

## Scalability Patterns

### 1. **Horizontal Scaling**
Each grading request is independent:
- Deploy multiple API connector instances
- Load balance across instances
- Stateless design enables easy scaling

### 2. **Batch Processing**
AI Executor demonstrates efficient batching:
- Collect multiple operations
- Execute in single API call
- Distribute results

### 3. **Caching**
Upstash driver provides Redis integration:
- Cache test results
- Store template configurations
- Share data across instances

---

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Error occurs at any layer                                   │
└────────────────┬────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Try to handle gracefully:                                   │
│ • PreFlight errors → Return AutograderResponse("fail")      │
│ • Template errors → Log and return error response           │
│ • Grading errors → Capture, log, return partial results     │
│ • Reporter errors → Fall back to basic feedback             │
└────────────────┬────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ AutograderFacade catches exception                          │
│ • Logs full error details                                   │
│ • Returns AutograderResponse:                               │
│   - status: "fail"                                          │
│   - final_score: 0.0                                        │
│   - feedback: Error message                                 │
│   - test_report: []                                         │
└────────────────┬────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Connector handles error response                            │
│ • GitHub: Commits error message to FEEDBACK.md              │
│ • API: Returns 500 with error details                       │
│ • CLI: Prints error to stderr                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Directory Structure Mapping

```
autograder/
├── connectors/                    # CONNECTOR LAYER
│   ├── port.py                    # Abstract Port interface
│   ├── models/                    # Shared models
│   │   ├── autograder_request.py  # Input contract
│   │   └── assignment_config.py   # Configuration
│   └── adapters/                  # Concrete implementations
│       ├── github_action_adapter/ # GitHub connector
│       ├── api/                   # API connector
│       └── cli/                   # CLI connector
│
├── autograder/                    # CORE SYSTEM
│   ├── autograder_facade.py       # Orchestrator (entry point)
│   ├── context.py                 # Global request context
│   │
│   ├── builder/                   # BUILDER LAYER
│   │   ├── pre_flight.py          # Setup validation
│   │   ├── tree_builder.py        # Criteria tree construction
│   │   ├── template_library/      # Test templates
│   │   │   ├── library.py         # Template loader
│   │   │   └── templates/         # Pre-built templates
│   │   │       ├── web_dev.py
│   │   │       ├── api_testing.py
│   │   │       ├── essay_grader.py
│   │   │       └── input_output.py
│   │   ├── execution_helpers/     # Complex infrastructure
│   │   │   ├── sandbox_executor.py # Docker containers
│   │   │   └── AI_Executor.py      # AI batching
│   │   └── models/                # Builder data structures
│   │       ├── criteria_tree.py   # Tree nodes
│   │       ├── template.py        # Template base
│   │       └── test_function.py   # Test base
│   │
│   └── core/                      # CORE LAYER
│       ├── grading/
│       │   └── grader.py          # Test execution & scoring
│       ├── report/
│       │   ├── reporter_factory.py
│       │   ├── default_reporter.py
│       │   └── ai_reporter.py
│       ├── models/
│       │   ├── autograder_response.py # Output contract
│       │   ├── result.py
│       │   └── test_result.py
│       └── utils/
│           ├── result_processor.py
│           └── upstash_driver.py  # Redis integration
```

---

## Summary

The autograder's hexagonal architecture provides:

✅ **Complete isolation** of core grading logic  
✅ **Standardized contracts** (AutograderRequest/Response)  
✅ **Environment flexibility** (GitHub, API, CLI, etc.)  
✅ **Easy testing** without external dependencies  
✅ **Clear separation of concerns** (Builder vs. Core)  
✅ **Extensibility** through adapters and templates  
✅ **Security** through containerization and isolation  
✅ **Scalability** through stateless design  

This architecture enables the autograder to be deployed anywhere, grading anything, while maintaining a clean, testable, and maintainable codebase! 🏗️

---

## Related Documentation

- **[Getting Started](./getting_started.md)** - Understand the complete workflow
- **[Criteria Configuration](./configuration/criteria_config.md)** - Define grading criteria
- **[Templates Guide](./templates/grading_templates.md)** - Use test templates
- **[Core Concepts](./core_concepts.md)** - Deep dive into key concepts
