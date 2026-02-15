# Autograder System - Complete Technical Documentation

**Version:** 2.0  
**Last Updated:** February 15, 2026  
**Architecture:** Pipeline-based, Stateless Design

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Architecture](#core-architecture)
3. [Grading Configuration](#grading-configuration)
4. [Submission Processing](#submission-processing)
5. [The Autograder Pipeline](#the-autograder-pipeline)
6. [Criteria Tree - Deep Dive](#criteria-tree---deep-dive)
7. [Result Tree - Deep Dive](#result-tree---deep-dive)
8. [Grading Templates](#grading-templates)
9. [Sandbox Manager](#sandbox-manager)
10. [Algorithms & Scoring](#algorithms--scoring)
11. [Feedback Generation](#feedback-generation)
12. [Web API Integration](#web-api-integration)
13. [Implementation Examples](#implementation-examples)

---

## System Overview

### What is the Autograder?

The **Autograder** is a highly configurable, automated grading system designed to evaluate student submissions against predefined grading criteria. It operates in the context of grading submissions, working with two main entities:

1. **Grading Configuration** - Defines HOW to grade an assignment
2. **Submission** - The student's work to be evaluated

### Key Design Principles

- **Stateless Pipeline Architecture**: A grading configuration creates a reusable pipeline that can grade unlimited submissions without state pollution
- **Tree-Based Scoring**: Hierarchical criteria trees enable complex, weighted scoring with categories, subjects, and individual tests
- **Sandboxed Execution**: Untrusted student code runs in isolated Docker containers for security
- **Template-Based Testing**: Reusable test libraries for common assignment types (web dev, I/O, APIs, essays)
- **Configurable Feedback**: Support for both structured default feedback and AI-powered personalized feedback

---

## Core Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     WEB API LAYER                           │
│  • REST API for submissions                                 │
│  • Database storage (configurations & results)              │
│  • Background grading tasks                                 │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                  AUTOGRADER CORE                            │
│  ┌──────────────────────────────────────────────────────┐  ���
│  │           AutograderPipeline                         │  │
│  │  (Stateless, Reusable Grading Workflow)              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Pipeline Steps (Executed in Order):                        │
│  1. TemplateLoaderStep    → Load grading template           │
│  2. BuildTreeStep         → Build criteria tree             │
│  3. PreFlightStep         → Validate & sandbox (optional)   │
│  4. GradeStep             → Execute tests & score           │
│  5. FocusStep             → Identify key failures           │
│  6. FeedbackStep          → Generate feedback               │
│  7. ExporterStep          → Export results (optional)       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                  SANDBOX MANAGER                            │
│  • Docker-based isolation                                   │
│  • Language-specific pools (Python, Java, Node.js, C++)     │
│  • Container lifecycle management                           │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Grading Configuration
         │
         ├─→ Template Name ──────────────┐
         │                                │
         ├─→ Criteria Config ─────────┐  │
         │                             │  │
         ├─→ Feedback Config          │  │
         │                             │  │
         └─→ Setup Config              │  │
                                       │  │
                                       ▼  ▼
                            ┌──────────────────────┐
                            │ build_pipeline()     │
                            │ (Factory Function)   │
                            └──────────┬───────────┘
                                       │
                                       ▼
                            ┌──────────────────────┐
                            │ AutograderPipeline   │
                            │ (Stateless Instance) │
                            └──────────┬───────────┘
                                       │
         Submission ───────────────────┤
                                       │
                                       ▼
                            ┌──────────────────────┐
                            │  pipeline.run()      │
                            └──────────┬───────────┘
                                       │
                                       ▼
                            ┌──────────────────────┐
                            │ PipelineExecution    │
                            │ (Result Object)      │
                            │                      │
                            │ • status             │
                            │ • result             │
                            │ • step_results       │
                            └──────────────────────┘
```

---

## Grading Configuration

A **Grading Configuration** is the complete blueprint for grading a specific assignment. It consists of four main components:

### 1. Grading Criteria (CriteriaConfig)

The **criteria configuration** defines the test structure and scoring weights.

**Structure:**
```python
{
    "base": {                     # Required category
        "weight": 100,
        "subjects": [...],        # Nested organization
        "tests": [...]            # Direct tests
    },
    "bonus": {                    # Optional category
        "weight": 20,             # Adds up to 20 points
        "subjects": [...]
    },
    "penalty": {                  # Optional category
        "weight": 10,             # Subtracts up to 10 points
        "subjects": [...]
    }
}
```

**Key Features:**
- **Three Categories**: Base (required), Bonus (optional), Penalty (optional)
- **Hierarchical Structure**: Categories → Subjects → Tests
- **Recursive Subjects**: Subjects can contain sub-subjects for deep organization
- **Weighted Scoring**: Each level has configurable weights
- **Heterogeneous Trees**: Mix subjects and tests at the same level with `subjects_weight`

**Example:**
```python
{
    "base": {
        "weight": 100,
        "subjects": [
            {
                "subject_name": "HTML Structure",
                "weight": 50,
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
            },
            {
                "subject_name": "CSS Styling",
                "weight": 50,
                "tests": [
                    {
                        "name": "has_style",
                        "file": "style.css",
                        "parameters": [
                            {"name": "property_name", "value": "display"},
                            {"name": "property_value", "value": "flex"}
                        ]
                    }
                ]
            }
        ]
    }
}
```

#### Configuration Models (Pydantic Validation)

The system uses **Pydantic** models for robust validation:

```python
# autograder/models/config/criteria.py
class CriteriaConfig(BaseModel):
    test_library: Optional[str]
    base: CategoryConfig
    bonus: Optional[CategoryConfig]
    penalty: Optional[CategoryConfig]

# autograder/models/config/category.py
class CategoryConfig(BaseModel):
    weight: float  # 0-100
    tests: Optional[List[TestConfig]]
    subjects: Optional[List[SubjectConfig]]
    subjects_weight: Optional[int]  # Required if both tests and subjects exist

# autograder/models/config/subject.py
class SubjectConfig(BaseModel):
    subject_name: str
    weight: float  # 0-100
    tests: Optional[List[TestConfig]]
    subjects: Optional[List['SubjectConfig']]  # Recursive
    subjects_weight: Optional[int]

# autograder/models/config/test.py
class TestConfig(BaseModel):
    name: str  # Test function name from template
    file: Optional[str]  # Target file(s)
    parameters: Optional[List[ParameterConfig]]
```

### 2. Grading Template

The **grading template** provides the executable test functions used to evaluate submissions.

**Template Structure:**
```python
class Template(ABC):
    @property
    def template_name(self) -> str:
        """Name identifier (e.g., 'webdev', 'IO', 'api')"""
        
    @property
    def requires_sandbox(self) -> bool:
        """Whether this template needs sandboxed execution"""
        
    def get_test(self, name: str) -> TestFunction:
        """Retrieve a test function by name"""
```

**Available Templates:**
- `webdev` - HTML/CSS/JavaScript validation (no sandbox)
- `IO` - Command-line I/O programs (requires sandbox)
- `api` - REST API testing (requires sandbox)
- `essay` - AI-powered essay grading (no sandbox)
- Custom templates (user-defined)

**Template Example (Web Development):**
```python
class WebDevTemplate(Template):
    def __init__(self):
        self.tests = {
            "has_tag": HasTag(),
            "has_class": HasClass(),
            "check_bootstrap_linked": CheckBootstrapLinked(),
            # ... 30+ more test functions
        }
    
    @property
    def template_name(self):
        return "Web Development"
    
    @property
    def requires_sandbox(self) -> bool:
        return False  # Static HTML/CSS analysis
    
    def get_test(self, name: str) -> TestFunction:
        if name not in self.tests:
            raise AttributeError(f"Test '{name}' not found")
        return self.tests[name]
```

**Test Function Anatomy:**
```python
class HasTag(TestFunction):
    @property
    def name(self) -> str:
        return "has_tag"
    
    @property
    def description(self) -> str:
        return "Checks for presence of HTML tags"
    
    @property
    def parameter_description(self) -> List[ParamDescription]:
        return [
            ParamDescription("tag", "Tag name to search", "string"),
            ParamDescription("required_count", "Minimum occurrences", "integer")
        ]
    
    def execute(
        self, 
        files: Optional[List[SubmissionFile]], 
        sandbox: Optional[SandboxContainer],
        tag: str = "",
        required_count: int = 0,
        **kwargs
    ) -> TestResult:
        # Parse HTML and count tags
        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(tag))
        
        # Calculate score
        score = min(100, (found_count / required_count) * 100)
        report = f"Found {found_count} of {required_count} required <{tag}> tags"
        
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"tag": tag, "required_count": required_count}
        )
```

### 3. Feedback Preferences

Configures how feedback is presented to students.

```python
{
    "general": {
        "report_title": "Assignment Report",
        "show_score": true,
        "show_passed_tests": false,
        "add_report_summary": true
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
        "assignment_context": "Web portfolio with Bootstrap"
    }
}
```

### 4. Preflight Checks (Setup Config)

Optional validation and sandbox setup before grading.

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

**When setup_config is provided:**
1. **Required Files Check**: Validates file existence
2. **Sandbox Creation**: If template requires it
3. **Setup Commands**: Executes in sandbox (e.g., install dependencies)

---

## Submission Processing

### Submission Object

A **Submission** represents a student's work to be graded.

```python
@dataclass
class Submission:
    username: str                              # Student identifier
    user_id: int                               # External student ID
    assignment_id: int                         # Assignment identifier
    submission_files: Dict[str, SubmissionFile]  # All submitted files
    language: Optional[Language] = None        # For I/O/API templates

@dataclass
class SubmissionFile:
    filename: str
    content: str  # Full file content as string
```

**Example:**
```python
submission = Submission(
    username="john.doe",
    user_id="student123",
    assignment_id=42,
    submission_files={
        "index.html": SubmissionFile(
            filename="index.html",
            content="<!DOCTYPE html>..."
        ),
        "style.css": SubmissionFile(
            filename="style.css",
            content="body { margin: 0; }"
        )
    },
    language=None  # Only needed for I/O and API templates
)
```

### From Configuration to Execution

**Step 1: Build the Pipeline (Once per Assignment)**
```python
pipeline = build_pipeline(
    template_name="webdev",
    include_feedback=True,
    grading_criteria=criteria_dict,
    feedback_config=feedback_dict,
    setup_config=setup_dict,  # Optional
    custom_template=None,
    feedback_mode="default",  # or "ai"
    export_results=False
)
```

**Step 2: Grade Submissions (Reusable Pipeline)**
```python
# Same pipeline can grade many submissions
submission1 = create_submission("student1")
submission2 = create_submission("student2")

result1 = pipeline.run(submission1)
result2 = pipeline.run(submission2)
```

---

## The Autograder Pipeline

### Pipeline Architecture

The **AutograderPipeline** is a stateless orchestrator that executes a series of steps to grade a submission.

```python
class AutograderPipeline:
    """
    Orchestrates the execution of grading steps for a submission.
    
    Key Characteristics:
    - Stateless: Can be reused for multiple submissions
    - Step-based: Each step produces output for the next
    - Error-resilient: Stops on first failure, cleans up resources
    - Traceable: Maintains full execution history
    """
    
    def __init__(self):
        self._steps = {}  # Ordered dict of steps
    
    def add_step(self, step_name: StepName, step: Step):
        """Add a step to the pipeline"""
        self._steps[step_name] = step
    
    def run(self, submission: Submission) -> PipelineExecution:
        """Execute all steps on a submission"""
        # 1. Initialize execution tracking
        pipeline_execution = PipelineExecution.start_execution(submission)
        
        # 2. Execute steps in order
        for step in self._steps:
            try:
                pipeline_execution = self._steps[step].execute(pipeline_execution)
                
                # Check if step failed
                current_step_result = pipeline_execution.get_previous_step()
                if current_step_result and not current_step_result.is_successful:
                    pipeline_execution.set_failure()
                    break
                    
            except Exception as e:
                pipeline_execution.status = PipelineStatus.INTERRUPTED
                break
        
        # 3. Finalize and cleanup
        pipeline_execution.finish_execution()
        self._cleanup_sandbox(pipeline_execution)
        
        return pipeline_execution
```

### Pipeline Steps Explained

#### 1. **TemplateLoaderStep** (`LOAD_TEMPLATE`)

**Purpose:** Load the grading template containing test functions.

**Input:** None (uses template_name from config)  
**Output:** Template object

**Process:**
```python
class TemplateLoaderStep(Step):
    def execute(self, input: PipelineExecution) -> PipelineExecution:
        # Load from template library or custom template
        if self._custom_template:
            template = load_custom_template(self._custom_template)
        else:
            template = TemplateLibraryService.load_builtin_template(
                self._template_name
            )
        
        return input.add_step_result(
            StepResult(
                step=StepName.LOAD_TEMPLATE,
                data=template,
                status=StepStatus.SUCCESS
            )
        )
```

**What Happens:**
- Loads pre-built template from library (`webdev`, `IO`, `api`, `essay`)
- Or loads custom template (future: sandboxed execution for security)
- Template contains all test functions that will be used in grading

---

#### 2. **BuildTreeStep** (`BUILD_TREE`)

**Purpose:** Build the Criteria Tree from configuration and template.

**Input:** Template (from previous step)  
**Output:** CriteriaTree

**Process:**
```python
class BuildTreeStep(Step):
    def execute(self, input: PipelineExecution) -> PipelineExecution:
        # 1. Validate criteria configuration
        criteria_config = CriteriaConfig.from_dict(self._criteria_json)
        
        # 2. Get template from previous step
        template = input.get_step_result(StepName.LOAD_TEMPLATE).data
        
        # 3. Build criteria tree
        criteria_tree = CriteriaTreeService().build_tree(
            criteria_config,
            template
        )
        
        return input.add_step_result(
            StepResult(
                step=StepName.BUILD_TREE,
                data=criteria_tree,
                status=StepStatus.SUCCESS
            )
        )
```

**What Happens:**
1. **Validation**: Pydantic validates the criteria structure
2. **Tree Construction**: Creates hierarchical tree of Categories → Subjects → Tests
3. **Test Function Embedding**: Matches test names to template functions and embeds them in TestNodes
4. **Weight Balancing**: Normalizes sibling weights to sum to 100

**Algorithm (CriteriaTreeService):**
```python
def build_tree(criteria_config, template):
    # Parse base category (required)
    base = parse_category("base", criteria_config.base, template)
    
    # Parse bonus category (optional)
    bonus = parse_category("bonus", criteria_config.bonus, template) if criteria_config.bonus else None
    
    # Parse penalty category (optional)
    penalty = parse_category("penalty", criteria_config.penalty, template) if criteria_config.penalty else None
    
    return CriteriaTree(base=base, bonus=bonus, penalty=penalty)

def parse_category(name, config, template):
    category = CategoryNode(name, config.weight)
    
    # Parse subjects recursively
    if config.subjects:
        category.subjects = [parse_subject(s, template) for s in config.subjects]
        balance_weights(category.subjects)
    
    # Parse direct tests
    if config.tests:
        category.tests = [parse_test(t, template) for t in config.tests]
    
    return category

def parse_test(config, template):
    # Find test function in template
    test_function = template.get_test(config.name)
    if not test_function:
        raise ValueError(f"Test '{config.name}' not found in template")
    
    # Create test node with embedded function
    return TestNode(
        name=config.name,
        test_function=test_function,  # Embedded reference
        parameters=config.get_kwargs_dict(),
        file_target=config.file
    )
```

---

#### 3. **PreFlightStep** (`PRE_FLIGHT`) - Optional

**Purpose:** Validate submission and create sandbox if needed.

**Input:** Submission, Template  
**Output:** SandboxContainer (or None)

**Process:**
```python
class PreFlightStep(Step):
    def execute(self, input: PipelineExecution) -> PipelineExecution:
        sandbox = None
        
        # 1. Check required files
        if self._setup_config.get('required_files'):
            if not check_required_files(input.submission.submission_files):
                return fail_with_error("Missing required files")
        
        # 2. Create sandbox if template requires it
        template = input.get_step_result(StepName.LOAD_TEMPLATE).data
        if template.requires_sandbox:
            sandbox = create_sandbox(input.submission)
        
        # 3. Run setup commands in sandbox
        if self._setup_config.get('setup_commands'):
            if not execute_setup_commands(sandbox):
                return fail_with_error("Setup commands failed")
        
        return input.add_step_result(
            StepResult(
                step=StepName.PRE_FLIGHT,
                data=sandbox,  # May be None
                status=StepStatus.SUCCESS
            )
        )
```

**What Happens:**
1. **File Validation**: Checks if required files exist in submission
2. **Sandbox Creation**: If template.requires_sandbox is True:
   - Gets sandbox from language pool (managed by SandboxManager)
   - Copies submission files into container
3. **Setup Commands**: Executes commands like `pip install`, `npm install`

**When Does PreFlight Run?**
- Only if `setup_config` is provided to `build_pipeline()`
- Even with empty `setup_config={}`, it will create sandbox if template requires it

---

#### 4. **GradeStep** (`GRADE`) - Core Step

**Purpose:** Execute all tests and build the Result Tree.

**Input:** CriteriaTree, Sandbox (optional), Submission  
**Output:** GradeStepResult (contains final_score and result_tree)

**Process:**
```python
class GradeStep(Step):
    def execute(self, input: PipelineExecution) -> PipelineExecution:
        # 1. Get criteria tree from BUILD_TREE step
        criteria_tree = input.get_step_result(StepName.BUILD_TREE).data
        
        # 2. Get sandbox from PRE_FLIGHT step (if it ran)
        sandbox = None
        if input.has_step_result(StepName.PRE_FLIGHT):
            sandbox = input.get_step_result(StepName.PRE_FLIGHT).data
        
        # 3. Set sandbox in grader service
        if sandbox:
            self._grader_service.set_sandbox(sandbox)
        
        # 4. Grade from tree
        result_tree = self._grader_service.grade_from_tree(
            criteria_tree=criteria_tree,
            submission_files=input.submission.submission_files
        )
        
        # 5. Calculate final score
        final_score = result_tree.calculate_final_score()
        
        return input.add_step_result(
            StepResult(
                step=StepName.GRADE,
                data=GradeStepResult(
                    final_score=final_score,
                    result_tree=result_tree
                ),
                status=StepStatus.SUCCESS
            )
        )
```

**What Happens (GraderService Algorithm):**

```python
def grade_from_tree(criteria_tree, submission_files):
    # 1. Process base category
    base_result = process_category(criteria_tree.base)
    
    # 2. Process bonus category (optional)
    bonus_result = process_category(criteria_tree.bonus) if criteria_tree.bonus else None
    
    # 3. Process penalty category (optional)
    penalty_result = process_category(criteria_tree.penalty) if criteria_tree.penalty else None
    
    # 4. Create root node
    root = RootResultNode(
        base=base_result,
        bonus=bonus_result,
        penalty=penalty_result
    )
    
    return ResultTree(root)

def process_category(category: CategoryNode) -> CategoryResultNode:
    # Recursively process subjects
    subject_results = [process_subject(s) for s in category.subjects]
    
    # Process direct tests
    test_results = [process_test(t) for t in category.tests]
    
    # Balance weights
    balance_weights(subject_results, test_results, category.subjects_weight)
    
    return CategoryResultNode(
        name=category.name,
        weight=category.weight,
        subjects=subject_results,
        tests=test_results
    )

def process_test(test: TestNode) -> TestResultNode:
    # 1. Get target files
    files = get_file_target(test.file_target, submission_files)
    
    # 2. Execute test function
    test_result = test.test_function.execute(
        files=files,
        sandbox=self._sandbox,
        **test.parameters
    )
    
    # 3. Create result node
    return TestResultNode(
        name=test.name,
        test_node=test,
        score=test_result.score,  # 0-100
        report=test_result.report,
        weight=test.weight
    )
```

**Execution Flow:**
```
CriteriaTree (Stateless Definition)
         │
         ├─→ Process Base Category
         │        │
         │        ├─→ Process Subject 1
         │        │        ├─→ Execute Test 1 → TestResultNode(score=100)
         │        │        └─→ Execute Test 2 → TestResultNode(score=75)
         │        │   Calculate Subject Score: (100 + 75) / 2 = 87.5
         │        │
         │        └─→ Process Subject 2
         │                 └─→ Execute Test 3 → TestResultNode(score=50)
         │            Calculate Subject Score: 50
         │    Calculate Category Score: (87.5 * 0.6 + 50 * 0.4) = 72.5
         │
         └─→ Process Bonus Category (similar)
                  Calculate Final Score: base + bonus - penalty
```

---

#### 5. **FocusStep** (`FOCUS`) - Optional

**Purpose:** Identify the most impactful failed tests for feedback.

**Input:** GradeStepResult (with result_tree)  
**Output:** Focus (lists of FocusedTest)

**Process:**
```python
class FocusStep(Step):
    def execute(self, input: PipelineExecution) -> PipelineExecution:
        # Get grading result
        grade_result = input.get_step_result(StepName.GRADE).data
        result_tree = grade_result.result_tree
        
        # Find most impactful tests
        focus = self._focus_service.find(result_tree)
        
        return input.add_step_result(
            StepResult(
                step=StepName.FOCUS,
                data=focus,
                status=StepStatus.SUCCESS
            )
        )
```

**What Happens (FocusService Algorithm):**

The FocusService calculates the **impact** of each failed test on the final score, considering:
- Test's own weight
- Parent subject's weight
- Category's weight
- How the test's failure propagates up the tree

```python
def calculate_impact(test, cumulative_multiplier):
    """
    Calculate how many points this test deducted from final score.
    
    Example:
    - Test scored 50/100 (missed 50 points)
    - Test weight: 25% of subject
    - Subject weight: 40% of category
    - Category weight: 100% (base)
    
    Impact = 50 * (25/100) * (40/100) * (100/100) = 5 points lost
    """
    if test.score == 100:
        return 0.0
    
    points_missed = 100 - test.score
    return points_missed * (test.weight / 100) * cumulative_multiplier

def find(result_tree):
    # Process each category
    base_focused = process_category(result_tree.root.base)
    bonus_focused = process_category(result_tree.root.bonus) if result_tree.root.bonus else None
    penalty_focused = process_category(result_tree.root.penalty) if result_tree.root.penalty else None
    
    # Sort by impact (highest first)
    base_focused.sort(key=lambda f: f.diff_score, reverse=True)
    
    return Focus(base=base_focused, bonus=bonus_focused, penalty=penalty_focused)
```

**Output:**
```python
@dataclass
class FocusedTest:
    test_result: TestResultNode
    diff_score: float  # Impact on final score

@dataclass
class Focus:
    base: List[FocusedTest]     # Sorted by impact (highest first)
    bonus: Optional[List[FocusedTest]]
    penalty: Optional[List[FocusedTest]]
```

---

#### 6. **FeedbackStep** (`FEEDBACK`) - Optional

**Purpose:** Generate human-readable feedback for students.

**Input:** Focus (from FOCUS step)  
**Output:** Feedback text (string)

**Process:**
```python
class FeedbackStep(Step):
    def execute(self, input: PipelineExecution) -> PipelineExecution:
        # Get focused tests
        focus = input.get_step_result(StepName.FOCUS).data
        
        # Generate feedback
        feedback = self._reporter_service.generate_feedback(
            grading_result=focus,
            feedback_config=self._feedback_config
        )
        
        return input.add_step_result(
            StepResult(
                step=StepName.FEEDBACK,
                data=feedback,
                status=StepStatus.SUCCESS
            )
        )
```

**Reporter Types:**

1. **DefaultReporter** (Structured)
   - Template-based feedback
   - Shows test results by category
   - Includes test reports
   - Fast and deterministic

2. **AIReporter** (Personalized)
   - Uses OpenAI API
   - Analyzes submission context
   - Explains root causes
   - Provides hints or solutions
   - Customizable tone and persona

**Feedback Configuration:**
```python
{
    "general": {
        "report_title": "Assignment Report",
        "show_score": true,
        "show_passed_tests": false
    },
    "default": {
        "category_headers": {
            "base": "✅ Requirements",
            "bonus": "⭐ Bonus"
        }
    },
    "ai": {
        "provide_solutions": "hint",
        "feedback_tone": "encouraging",
        "feedback_persona": "Code Mentor"
    }
}
```

---

#### 7. **ExporterStep** (`EXPORTER`) - Optional

**Purpose:** Export results to external systems (e.g., Upstash Redis).

**Input:** Complete PipelineExecution  
**Output:** Export confirmation

---

### PipelineExecution Object

The **PipelineExecution** is the stateful execution context that flows through all steps.

```python
@dataclass
class PipelineExecution:
    """
    Tracks the entire grading execution and results from each step.
    
    Attributes:
        step_results: List of results from each executed step
        assignment_id: The assignment being graded
        submission: The student submission
        status: Current pipeline status
        result: Final grading result (set at end)
    """
    step_results: List[StepResult]
    assignment_id: int
    submission: Submission
    status: PipelineStatus = PipelineStatus.EMPTY
    result: Optional[GradingResult] = None
    
    def add_step_result(self, step_result: StepResult):
        """Add a step result and return self for chaining"""
        self.step_results.append(step_result)
        return self
    
    def get_step_result(self, step_name: StepName) -> StepResult:
        """Retrieve result from a specific step"""
        for result in self.step_results:
            if result.step == step_name:
                return result
        raise ValueError(f"Step {step_name} was not executed")
    
    def has_step_result(self, step_name: StepName) -> bool:
        """Check if a step was executed"""
        return any(r.step == step_name for r in self.step_results)
    
    def get_previous_step(self) -> Optional[StepResult]:
        """Get the most recent step result"""
        return self.step_results[-1] if self.step_results else None
    
    def finish_execution(self):
        """
        Finalize execution and create GradingResult.
        Called after all steps complete or on failure.
        """
        if self.status != PipelineStatus.FAILED:
            self.status = PipelineStatus.SUCCESS
            
            grade_result = self.get_step_result(StepName.GRADE).data
            feedback = None
            if self.has_step_result(StepName.FEEDBACK):
                feedback = self.get_step_result(StepName.FEEDBACK).data
            
            self.result = GradingResult(
                final_score=grade_result.final_score,
                feedback=feedback,
                result_tree=grade_result.result_tree
            )
    
    @classmethod
    def start_execution(cls, submission: Submission):
        """Initialize a new pipeline execution"""
        return cls(
            step_results=[],
            assignment_id=submission.assignment_id,
            submission=submission,
            status=PipelineStatus.RUNNING
        )
```

**Pipeline Status:**
```python
class PipelineStatus(Enum):
    EMPTY = "empty"           # Not started
    RUNNING = "running"       # In progress
    SUCCESS = "success"       # Completed successfully
    FAILED = "failed"         # Step failed gracefully
    INTERRUPTED = "interrupted"  # Exception occurred
```

**Step Result:**
```python
@dataclass
class StepResult:
    step: StepName           # Which step produced this
    data: Any                # Step output (Template, CriteriaTree, etc.)
    status: StepStatus       # SUCCESS or FAIL
    error: Optional[str]     # Error message if failed
    
    @property
    def is_successful(self) -> bool:
        return self.status == StepStatus.SUCCESS and self.error is None
```

---

## Criteria Tree - Deep Dive

### What is a Criteria Tree?

The **Criteria Tree** is the stateless, hierarchical definition of grading criteria. It's built once from configuration and reused for all submissions.

### Tree Structure

```
CriteriaTree (Root)
│
├─ base: CategoryNode (weight=100, required)
│   │
│   ├─ subjects: List[SubjectNode]
│   │   │
│   │   ├─ SubjectNode("HTML Structure", weight=50)
│   │   │   │
│   │   │   ├─ subjects: List[SubjectNode]  (recursive!)
│   │   │   │   └─ SubjectNode("Navigation", weight=30)
│   │   │   │       └─ tests: [TestNode("has_tag", params={tag:"nav"})]
│   │   │   │
│   │   │   └─ tests: List[TestNode]
│   │   │       └─ TestNode("has_tag", test_function=<HasTag>, params={tag:"header"})
│   │   │
│   │   └─ SubjectNode("CSS Styling", weight=50)
│   │       └─ tests: [TestNode("has_style", ...)]
│   │
│   └─ tests: List[TestNode]  (optional, direct tests under category)
│
├─ bonus: CategoryNode (weight=20, optional)
│   └─ subjects: [...]
│
└─ penalty: CategoryNode (weight=10, optional)
    └─ subjects: [...]
```

### Node Types

#### 1. CriteriaTree (Root)
```python
@dataclass
class CriteriaTree:
    base: CategoryNode                    # Required
    bonus: Optional[CategoryNode] = None
    penalty: Optional[CategoryNode] = None
```

#### 2. CategoryNode (Top Level)
```python
@dataclass
class CategoryNode:
    name: str                             # "base", "bonus", "penalty"
    weight: float                         # Scoring weight
    subjects: List[SubjectNode] = []      # Nested subjects
    tests: List[TestNode] = []            # Direct tests
    subjects_weight: Optional[float] = None  # For heterogeneous trees
    
    def get_all_tests(self) -> List[TestNode]:
        """Recursively collect all tests under this category"""
        tests = list(self.tests)
        for subject in self.subjects:
            tests.extend(subject.get_all_tests())
        return tests
```

#### 3. SubjectNode (Mid Level)
```python
@dataclass
class SubjectNode:
    name: str                             # Subject name
    weight: float                         # Weight in parent
    subjects: List['SubjectNode'] = []    # Nested subjects (recursive!)
    tests: List[TestNode] = []            # Tests in this subject
    subjects_weight: Optional[float] = None
    
    def get_all_tests(self) -> List[TestNode]:
        """Recursively collect all tests"""
        tests = list(self.tests)
        for subject in self.subjects:
            tests.extend(subject.get_all_tests())
        return tests
```

#### 4. TestNode (Leaf Level)
```python
@dataclass
class TestNode:
    name: str                             # Test identifier
    test_function: TestFunction           # EMBEDDED function reference
    parameters: Dict[str, Any] = {}       # Test parameters
    file_target: Optional[List[str]] = None  # Target files
    weight: float = 100.0                 # Weight in parent
```

**Key Innovation: Embedded Test Functions**

Unlike older architectures, test functions are **embedded directly** in TestNodes during tree building. This eliminates lazy loading and improves performance.

```python
# During tree building
test_function = template.get_test("has_tag")  # Get from template
test_node = TestNode(
    name="has_tag",
    test_function=test_function,  # EMBEDDED reference
    parameters={"tag": "nav", "required_count": 1}
)

# During grading
result = test_node.test_function.execute(
    files=submission_files,
    sandbox=sandbox,
    **test_node.parameters  # {"tag": "nav", "required_count": 1}
)
```

### Heterogeneous Trees

A **heterogeneous tree** has both subjects and tests at the same level.

**Example:**
```python
{
    "subject_name": "HTML",
    "weight": 100,
    "subjects_weight": 70,  # 70% for sub-subjects, 30% for tests
    "subjects": [
        {"subject_name": "Structure", "weight": 50, "tests": [...]},
        {"subject_name": "Content", "weight": 50, "tests": [...]}
    ],
    "tests": [
        {"name": "has_doctype", ...}
    ]
}
```

**Weight Distribution:**
- Sub-subjects group: 70% of parent weight
  - Structure: 50% of 70% = 35%
  - Content: 50% of 70% = 35%
- Tests group: 30% of parent weight
  - has_doctype: 100% of 30% = 30%

**Implementation:**
```python
def process_holder(holder: CategoryNode | SubjectNode):
    # Determine weight factors
    if holder.subjects and holder.tests:
        subjects_factor = holder.subjects_weight / 100
        tests_factor = 1 - subjects_factor
    else:
        subjects_factor = 1.0
        tests_factor = 1.0
    
    # Process subjects
    subject_results = [process_subject(s) for s in holder.subjects]
    balance_weights(subject_results, subjects_factor)
    
    # Process tests
    test_results = [process_test(t) for t in holder.tests]
    balance_weights(test_results, tests_factor)
    
    return ResultNode(subjects=subject_results, tests=test_results)
```

### Weight Balancing Algorithm

Sibling nodes are automatically balanced to sum to 100.

```python
def balance_subject_weights(subjects: List[SubjectNode]):
    total_weight = sum(s.weight for s in subjects)
    
    if total_weight > 0 and total_weight != 100:
        scaling_factor = 100 / total_weight
        for subject in subjects:
            subject.weight = subject.weight * scaling_factor

# Example:
# Input:  [Subject(weight=60), Subject(weight=80)]
# Total: 140
# Scaling: 100 / 140 = 0.714
# Output: [Subject(weight=42.86), Subject(weight=57.14)]
```

---

## Result Tree - Deep Dive

### What is a Result Tree?

The **Result Tree** is the stateful product of executing a Criteria Tree on a submission. It mirrors the Criteria Tree structure but contains **actual execution results** instead of definitions.

### Key Differences: Criteria Tree vs Result Tree

| Aspect | Criteria Tree | Result Tree |
|--------|---------------|-------------|
| **Nature** | Stateless definition | Stateful execution result |
| **Purpose** | Define what to test | Store what happened |
| **Nodes** | TestNode, SubjectNode, CategoryNode | TestResultNode, SubjectResultNode, CategoryResultNode |
| **Content** | Test functions, parameters | Scores, reports, metadata |
| **Lifecycle** | Build once, reuse forever | Created per submission |
| **Calculation** | No scores | Bottom-up score calculation |

### Result Tree Structure

```
ResultTree
│
└─ root: RootResultNode
    │
    ├─ base: CategoryResultNode (score: 85.5)
    │   │
    │   ├─ subjects: List[SubjectResultNode]
    │   │   │
    │   │   ├─ SubjectResultNode("HTML", score: 90)
    │   │   │   │
    │   │   │   └─ tests: List[TestResultNode]
    │   │   │       ├─ TestResultNode("has_tag", score: 100, report: "Found 1/1 <nav> tags")
    │   │   │       └─ TestResultNode("has_tag", score: 80, report: "Found 4/5 <section> tags")
    │   │   │
    │   │   └─ SubjectResultNode("CSS", score: 75)
    │   │       └─ tests: [...]
    │   │
    │   └─ tests: []
    │
    ├─ bonus: CategoryResultNode (score: 50)
    │   └─ ...
    │
    └─ penalty: CategoryResultNode (score: 20)
        └─ ...
```

### Node Types

#### 1. ResultTree (Container)
```python
@dataclass
class ResultTree:
    root: RootResultNode
    template_name: Optional[str] = None
    metadata: Dict[str, Any] = {}
    
    def calculate_final_score(self) -> float:
        """Calculate and return final score"""
        return self.root.calculate_score()
    
    def get_all_test_results(self) -> List[TestResultNode]:
        """Get all test results from entire tree"""
        return self.root.get_all_test_results()
    
    def get_failed_tests(self) -> List[TestResultNode]:
        """Get tests with score < 100"""
        return [t for t in self.get_all_test_results() if t.score < 100]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "final_score": self.root.score,
            "tree": self.root.to_dict(),
            "summary": {
                "total_tests": len(self.get_all_test_results()),
                "passed_tests": len(self.get_passed_tests()),
                "failed_tests": len(self.get_failed_tests())
            }
        }
```

#### 2. RootResultNode (Special Scoring)
```python
@dataclass
class RootResultNode:
    name: str = "root"
    score: float = 0.0
    base: CategoryResultNode         # Required
    bonus: Optional[CategoryResultNode] = None
    penalty: Optional[CategoryResultNode] = None
    
    def calculate_score(self) -> float:
        """
        Calculate final score using BASE + BONUS - PENALTY logic.
        
        Formula:
        - base_score: Standard 0-100 from base category
        - bonus_points: (bonus_score / 100) * bonus_weight
        - penalty_points: (penalty_score / 100) * penalty_weight
        - final = base + bonus - penalty (clamped to 0-100)
        """
        # Calculate base
        base_score = self.base.calculate_score()
        
        # Calculate bonus addition
        bonus_points = 0.0
        if self.bonus:
            bonus_score = self.bonus.calculate_score()
            bonus_points = (bonus_score / 100) * self.bonus.weight
        
        # Calculate penalty subtraction
        penalty_points = 0.0
        if self.penalty:
            penalty_score = self.penalty.calculate_score()
            penalty_points = (penalty_score / 100) * self.penalty.weight
        
        # Final score (clamped)
        self.score = max(0.0, min(100.0, base_score + bonus_points - penalty_points))
        return self.score
```

**Scoring Example:**
```
Base Category: 75/100 (weight=100)
Bonus Category: 80/100 (weight=20) → adds (80/100)*20 = 16 points
Penalty Category: 50/100 (weight=10) → subtracts (50/100)*10 = 5 points

Final Score = 75 + 16 - 5 = 86/100
```

#### 3. CategoryResultNode
```python
@dataclass
class CategoryResultNode:
    name: str                        # "base", "bonus", "penalty"
    weight: float
    score: float = 0.0
    subjects: List[SubjectResultNode] = []
    tests: List[TestResultNode] = []
    subjects_weight: Optional[float] = None
    
    def calculate_score(self) -> float:
        """
        Calculate weighted average score from children.
        
        Process:
        1. Calculate scores for all children (recursive)
        2. Combine subjects and tests
        3. Calculate weighted average
        """
        # Calculate children scores first
        for subject in self.subjects:
            subject.calculate_score()
        for test in self.tests:
            test.calculate_score()
        
        # Combine all children
        all_children = list(self.subjects) + list(self.tests)
        
        if not all_children:
            return 0.0
        
        # Weighted average
        total_weight = sum(child.weight for child in all_children)
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(child.score * child.weight for child in all_children)
        self.score = weighted_sum / total_weight
        
        return self.score
```

#### 4. SubjectResultNode
```python
@dataclass
class SubjectResultNode:
    name: str
    weight: float
    score: float = 0.0
    subjects: List['SubjectResultNode'] = []  # Recursive
    tests: List[TestResultNode] = []
    subjects_weight: Optional[float] = None
    
    def calculate_score(self) -> float:
        """Same weighted average algorithm as CategoryResultNode"""
        # Recursively calculate children
        for subject in self.subjects:
            subject.calculate_score()
        for test in self.tests:
            test.calculate_score()
        
        # Weighted average
        all_children = list(self.subjects) + list(self.tests)
        total_weight = sum(c.weight for c in all_children)
        
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(c.score * c.weight for c in all_children)
        self.score = weighted_sum / total_weight
        
        return self.score
```

#### 5. TestResultNode (Leaf)
```python
@dataclass
class TestResultNode:
    name: str
    test_node: TestNode              # Reference to original criteria
    score: float                     # 0-100
    report: str                      # Human-readable feedback
    weight: float = 100.0
    parameters: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    
    def calculate_score(self) -> float:
        """Leaf nodes return their own score"""
        return self.score
```

### Score Calculation Algorithm

The score flows **bottom-up** through the tree:

```
1. Execute Tests (Leaf Level)
   ├─ TestResult("has_tag"): score=100
   ├─ TestResult("has_class"): score=75
   └─ TestResult("has_style"): score=50

2. Calculate Subject Scores
   Subject("HTML", weight=60)
   ├─ Test1(score=100, weight=50)
   ├─ Test2(score=75, weight=50)
   └─ Score = (100*50 + 75*50) / (50+50) = 87.5

   Subject("CSS", weight=40)
   └─ Test3(score=50, weight=100)
   └─ Score = 50

3. Calculate Category Score
   Category("base", weight=100)
   ├─ Subject1(score=87.5, weight=60)
   ├─ Subject2(score=50, weight=40)
   └─ Score = (87.5*60 + 50*40) / (60+40) = 72.5

4. Calculate Root Score
   Root
   ├─ base(score=72.5, weight=100)
   ├─ bonus(score=80, weight=20) → +16 points
   └─ penalty(score=30, weight=10) → -3 points
   Final = 72.5 + 16 - 3 = 85.5
```

**Implementation:**
```python
# Start from root
final_score = result_tree.calculate_final_score()

# This triggers:
def calculate_final_score():
    return self.root.calculate_score()  # RootResultNode

def root.calculate_score():
    base_score = self.base.calculate_score()  # CategoryResultNode
    # ... bonus and penalty
    return base_score + bonus - penalty

def category.calculate_score():
    for subject in self.subjects:
        subject.calculate_score()  # SubjectResultNode (recursive!)
    for test in self.tests:
        test.calculate_score()  # TestResultNode (leaf, returns self.score)
    
    # Weighted average of all children
    return weighted_average(subjects + tests)
```

---

## Grading Templates

### Template Architecture

A **Grading Template** is a collection of test functions for a specific assignment type.

```python
class Template(ABC):
    @property
    @abstractmethod
    def template_name(self) -> str:
        """Unique identifier"""
    
    @property
    @abstractmethod
    def template_description(self) -> str:
        """Human-readable description"""
    
    @property
    @abstractmethod
    def requires_sandbox(self) -> bool:
        """Whether template needs sandboxed execution"""
    
    @abstractmethod
    def get_test(self, name: str) -> TestFunction:
        """Retrieve a test function by name"""
```

### Test Function Interface

```python
class TestFunction(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Test identifier"""
    
    @property
    @abstractmethod
    def description(self) -> str:
        """What this test checks"""
    
    @property
    @abstractmethod
    def parameter_description(self) -> List[ParamDescription]:
        """Parameters this test accepts"""
    
    @abstractmethod
    def execute(
        self,
        files: Optional[List[SubmissionFile]],
        sandbox: Optional[SandboxContainer],
        **kwargs
    ) -> TestResult:
        """Execute the test and return result"""
```

### Built-in Templates

#### 1. Web Development Template (`webdev`)

**Purpose:** Validate HTML, CSS, and JavaScript files  
**Requires Sandbox:** No (static analysis)

**Test Functions (30+):**
- `has_tag` - Check for HTML tags
- `has_class` - Check for CSS classes
- `has_style` - Check for CSS properties
- `check_bootstrap_linked` - Verify Bootstrap inclusion
- `check_internal_links` - Validate anchor links
- `uses_semantic_tags` - Check for semantic HTML
- `check_media_queries` - Responsive design validation
- Many more...

**Example Test:**
```python
class HasTag(TestFunction):
    @property
    def name(self):
        return "has_tag"
    
    def execute(
        self,
        files: Optional[List[SubmissionFile]],
        sandbox: Optional[SandboxContainer],
        tag: str = "",
        required_count: int = 0,
        **kwargs
    ) -> TestResult:
        html_content = files[0].content
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(tag))
        
        score = min(100, (found_count / required_count) * 100) if required_count > 0 else 100
        report = f"Found {found_count}/{required_count} <{tag}> tags"
        
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"tag": tag, "required_count": required_count}
        )
```

#### 2. Input/Output Template (`IO`)

**Purpose:** Test command-line programs  
**Requires Sandbox:** Yes

**Test Functions:**
- `expect_output` - Validate program output against expected

**Example:**
```python
class ExpectOutputTest(TestFunction):
    def execute(
        self,
        files: Optional[List[SubmissionFile]],
        sandbox: Optional[SandboxContainer],
        test_cases: List[Tuple[List[str], str]] = [],
        **kwargs
    ) -> TestResult:
        # Run program in sandbox with test inputs
        for inputs, expected_output in test_cases:
            result = sandbox.run_command(
                f"python program.py",
                stdin="\n".join(inputs)
            )
            
            if expected_output not in result.stdout:
                return TestResult(
                    test_name=self.name,
                    score=0,
                    report=f"Expected '{expected_output}', got '{result.stdout}'"
                )
        
        return TestResult(
            test_name=self.name,
            score=100,
            report="All test cases passed"
        )
```

#### 3. API Testing Template (`api`)

**Purpose:** Test REST APIs  
**Requires Sandbox:** Yes

**Test Functions:**
- `health_check` - Verify API is running
- `check_response_json` - Validate JSON response
- `check_status_code` - Verify HTTP status

#### 4. Essay Template (`essay`)

**Purpose:** AI-powered essay grading  
**Requires Sandbox:** No

**Test Functions:**
- AI-based evaluation of writing quality
- Structure analysis
- Argument strength
- Evidence quality

---

## Sandbox Manager

### Purpose

The **Sandbox Manager** provides secure, isolated execution environments for untrusted student code.

### Architecture

```
SandboxManager
│
├─ Language Pools
│   ├─ Python Pool (min=2, max=5)
│   │   ├─ Container 1 (idle)
│   │   ├─ Container 2 (in use)
│   │   └─ Container 3 (idle)
│   │
│   ├─ Java Pool (min=1, max=3)
│   ├─ Node.js Pool (min=2, max=4)
│   └─ C++ Pool (min=1, max=2)
│
└─ Lifecycle Management
    ├─ Pre-warming (create minimum containers on startup)
    ├─ Acquire/Release (pool pattern)
    ├─ Monitor (background thread replenishes pools)
    └─ Cleanup (destroy all on shutdown)
```

### Initialization

```python
# Load configuration from YAML
pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")

# Example config:
# - language: PYTHON
#   image: sandbox-py:latest
#   min_containers: 2
#   max_containers: 5
# - language: JAVA
#   image: sandbox-java:latest
#   min_containers: 1
#   max_containers: 3

# Initialize manager
manager = initialize_sandbox_manager(pool_configs)
```

**What Happens:**
1. **Orphan Cleanup**: Removes containers from previous crashed runs
2. **Pool Creation**: Creates one LanguagePool per configured language
3. **Pre-warming**: Creates minimum containers for each pool
4. **Monitor Start**: Launches background thread to maintain pool levels
5. **Signal Handlers**: Registers cleanup handlers for graceful shutdown

### Container Lifecycle

```python
# 1. Acquire from pool (PreFlightStep)
sandbox = manager.get_sandbox(Language.PYTHON)

# 2. Copy submission files into container
sandbox.copy_files(submission_files)

# 3. Run commands (setup or tests)
response = sandbox.run_command("pip install -r requirements.txt")
response = sandbox.run_command("python program.py")

# 4. Release back to pool (AutograderPipeline cleanup)
manager.release_sandbox(Language.PYTHON, sandbox)
```

### SandboxContainer Interface

```python
class SandboxContainer:
    def copy_files(self, files: Dict[str, SubmissionFile]):
        """Copy submission files into container"""
    
    def run_command(self, command: str, stdin: str = "") -> CommandResponse:
        """Execute command and return result"""
        # Returns: CommandResponse(exit_code, stdout, stderr)
    
    def get_file(self, filepath: str) -> str:
        """Read file from container"""
    
    def cleanup(self):
        """Reset container to clean state"""
```

### Security Features

1. **Isolation**: Each container is a separate Docker instance
2. **Resource Limits**: CPU, memory, and time restrictions
3. **Network Isolation**: No external network access
4. **Read-only Base**: Submission files in separate volume
5. **Automatic Cleanup**: Containers reset between uses

### Pool Management

```python
class LanguagePool:
    def acquire(self) -> SandboxContainer:
        """
        Get a container from the pool.
        
        Algorithm:
        1. Check for available containers
        2. If none and below max, create new container
        3. If at max, wait for container to be released
        4. Mark container as in-use
        5. Return container
        """
    
    def release(self, container: SandboxContainer):
        """
        Return container to pool.
        
        Process:
        1. Clean container (remove submission files)
        2. Mark as available
        3. Notify waiting threads
        """
    
    def replenish(self):
        """
        Ensure pool has minimum containers.
        Called by monitor thread every 5 seconds.
        """
```

---

## Algorithms & Scoring

### 1. Criteria Tree Building

**Input:** Criteria configuration (dict), Template  
**Output:** CriteriaTree with embedded test functions

**Algorithm:**
```python
def build_tree(criteria_config, template):
    # 1. Validate configuration (Pydantic)
    config = CriteriaConfig.from_dict(criteria_config)
    
    # 2. Build base category (required)
    base = build_category("base", config.base, template)
    
    # 3. Build bonus category (optional)
    bonus = build_category("bonus", config.bonus, template) if config.bonus else None
    
    # 4. Build penalty category (optional)
    penalty = build_category("penalty", config.penalty, template) if config.penalty else None
    
    return CriteriaTree(base=base, bonus=bonus, penalty=penalty)

def build_category(name, config, template):
    category = CategoryNode(name=name, weight=config.weight)
    
    # Build subjects
    if config.subjects:
        category.subjects = [build_subject(s, template) for s in config.subjects]
        balance_weights(category.subjects)
    
    # Build tests
    if config.tests:
        category.tests = [build_test(t, template) for t in config.tests]
    
    return category

def build_subject(config, template):
    subject = SubjectNode(name=config.subject_name, weight=config.weight)
    
    # Recursive subjects
    if config.subjects:
        subject.subjects = [build_subject(s, template) for s in config.subjects]
        balance_weights(subject.subjects)
    
    # Tests
    if config.tests:
        subject.tests = [build_test(t, template) for t in config.tests]
    
    return subject

def build_test(config, template):
    # Find test function in template
    test_func = template.get_test(config.name)
    if not test_func:
        raise ValueError(f"Test '{config.name}' not found in template")
    
    # Create test node with embedded function
    return TestNode(
        name=config.name,
        test_function=test_func,
        parameters=config.get_kwargs_dict(),
        file_target=config.file
    )

def balance_weights(nodes):
    """Normalize sibling weights to sum to 100"""
    total = sum(n.weight for n in nodes)
    if total > 0 and total != 100:
        factor = 100 / total
        for node in nodes:
            node.weight *= factor
```

**Time Complexity:** O(n) where n = number of nodes in tree  
**Space Complexity:** O(n)

### 2. Grading (Result Tree Building)

**Input:** CriteriaTree, Submission files, Sandbox (optional)  
**Output:** ResultTree with scores

**Algorithm:**
```python
def grade_from_tree(criteria_tree, submission_files, sandbox):
    # 1. Process base category
    base_result = process_category(criteria_tree.base)
    
    # 2. Process bonus category
    bonus_result = process_category(criteria_tree.bonus) if criteria_tree.bonus else None
    
    # 3. Process penalty category
    penalty_result = process_category(criteria_tree.penalty) if criteria_tree.penalty else None
    
    # 4. Create result tree
    root = RootResultNode(base=base_result, bonus=bonus_result, penalty=penalty_result)
    return ResultTree(root=root)

def process_category(category):
    # Calculate weight factors for heterogeneous trees
    if category.subjects and category.tests:
        subjects_factor = category.subjects_weight / 100
        tests_factor = 1 - subjects_factor
    else:
        subjects_factor = tests_factor = 1.0
    
    # Process subjects
    subject_results = [process_subject(s) for s in category.subjects]
    balance_result_weights(subject_results, subjects_factor)
    
    # Process tests
    test_results = [process_test(t) for t in category.tests]
    balance_result_weights(test_results, tests_factor)
    
    return CategoryResultNode(
        name=category.name,
        weight=category.weight,
        subjects=subject_results,
        tests=test_results
    )

def process_subject(subject):
    # Same structure as process_category (recursive)
    ...

def process_test(test):
    # 1. Get target files
    files = get_files_for_test(test.file_target)
    
    # 2. Execute test function
    result = test.test_function.execute(
        files=files,
        sandbox=sandbox,
        **test.parameters
    )
    
    # 3. Create result node
    return TestResultNode(
        name=test.name,
        test_node=test,
        score=result.score,  # 0-100
        report=result.report,
        weight=test.weight
    )
```

**Time Complexity:** O(n*t) where n = nodes, t = avg test execution time  
**Space Complexity:** O(n)

### 3. Score Calculation (Bottom-Up)

**Algorithm:**
```python
def calculate_final_score(result_tree):
    return result_tree.root.calculate_score()

# RootResultNode
def calculate_score(self):
    # 1. Calculate base score (0-100)
    base_score = self.base.calculate_score()
    
    # 2. Calculate bonus points
    bonus_points = 0
    if self.bonus:
        bonus_score = self.bonus.calculate_score()  # 0-100
        bonus_points = (bonus_score / 100) * self.bonus.weight
    
    # 3. Calculate penalty points
    penalty_points = 0
    if self.penalty:
        penalty_score = self.penalty.calculate_score()  # 0-100
        penalty_points = (penalty_score / 100) * self.penalty.weight
    
    # 4. Final score (clamped to 0-100)
    self.score = max(0, min(100, base_score + bonus_points - penalty_points))
    return self.score

# CategoryResultNode / SubjectResultNode
def calculate_score(self):
    # 1. Recursively calculate children
    for child in self.subjects + self.tests:
        child.calculate_score()
    
    # 2. Weighted average
    all_children = self.subjects + self.tests
    total_weight = sum(c.weight for c in all_children)
    
    if total_weight == 0:
        return 0
    
    weighted_sum = sum(c.score * c.weight for c in all_children)
    self.score = weighted_sum / total_weight
    return self.score

# TestResultNode
def calculate_score(self):
    return self.score  # Already calculated by test execution
```

**Time Complexity:** O(n) - single traversal  
**Space Complexity:** O(1) - modifies tree in place

### 4. Focus Calculation (Impact Analysis)

**Purpose:** Identify which failed tests had the most impact on final score.

**Algorithm:**
```python
def calculate_impact(test, cumulative_multiplier):
    """
    Calculate absolute point loss from this test.
    
    Args:
        test: TestResultNode
        cumulative_multiplier: Product of all parent weights (as decimals)
    
    Returns:
        Points lost (0-100 scale)
    """
    if test.score == 100:
        return 0.0
    
    points_missed = 100 - test.score
    return points_missed * (test.weight / 100) * cumulative_multiplier

def find_focused_tests(result_tree):
    focused = []
    
    # Process each category
    for category in [result_tree.root.base, result_tree.root.bonus, result_tree.root.penalty]:
        if not category:
            continue
        
        # Initial multiplier for category is 1.0 (100%)
        focused.extend(process_category_for_focus(category, multiplier=1.0))
    
    # Sort by impact (highest first)
    focused.sort(key=lambda f: f.diff_score, reverse=True)
    return focused

def process_subject_for_focus(subject, parent_multiplier):
    focused = []
    
    # Handle heterogeneous trees
    if subject.subjects_weight:
        subject_multiplier = parent_multiplier * (subject.subjects_weight / 100)
        test_multiplier = parent_multiplier * ((100 - subject.subjects_weight) / 100)
    else:
        subject_multiplier = test_multiplier = parent_multiplier
    
    # Process nested subjects
    for child_subject in subject.subjects:
        child_weight_factor = child_subject.weight / 100
        focused.extend(
            process_subject_for_focus(
                child_subject,
                subject_multiplier * child_weight_factor
            )
        )
    
    # Process tests
    for test in subject.tests:
        test_weight_factor = test.weight / 100
        impact = calculate_impact(test, test_multiplier * test_weight_factor)
        focused.append(FocusedTest(test_result=test, diff_score=impact))
    
    return focused
```

**Example:**
```
Tree Structure:
- Base (100%)
  - Subject A (60%)
    - Test 1 (50%, score=50) → missed 50 points
    - Test 2 (50%, score=100) → missed 0 points
  - Subject B (40%)
    - Test 3 (100%, score=80) → missed 20 points

Impact Calculation:
- Test 1: 50 * 0.50 * 0.60 * 1.0 = 15 points lost
- Test 2: 0 * 0.50 * 0.60 * 1.0 = 0 points lost
- Test 3: 20 * 1.00 * 0.40 * 1.0 = 8 points lost

Focused Order: [Test1(15), Test3(8), Test2(0)]
```

**Time Complexity:** O(n log n) - traversal + sort  
**Space Complexity:** O(n)

---

## Feedback Generation

### Two Feedback Modes

#### 1. Default Reporter (Structured)

**Characteristics:**
- Template-based
- Fast and deterministic
- Shows test results by category
- Includes test reports

**Configuration:**
```python
{
    "general": {
        "report_title": "Assignment Report",
        "show_score": true,
        "show_passed_tests": false
    },
    "default": {
        "category_headers": {
            "base": "✅ Required",
            "bonus": "⭐ Bonus",
            "penalty": "❌ Issues"
        }
    }
}
```

**Output Structure:**
```
==========================================
Assignment Report
==========================================
Final Score: 85/100

✅ Required (75/100)
-------------------------------------------
[PASS] HTML Structure: has_tag
  → Found 1/1 <nav> tags

[FAIL] CSS Styling: has_style
  → Expected 'display: flex' but found 'display: block'

⭐ Bonus (16/20)
-------------------------------------------
[PASS] Responsive Design: check_media_queries
  → Found 2/2 media queries
```

#### 2. AI Reporter (Personalized)

**Characteristics:**
- Uses OpenAI API
- Context-aware analysis
- Explains root causes
- Provides hints or solutions
- Customizable tone and persona

**Configuration:**
```python
{
    "ai": {
        "provide_solutions": "hint",  # "none" | "hint" | "detailed"
        "feedback_tone": "encouraging",
        "feedback_persona": "Code Mentor",
        "assignment_context": "Bootstrap portfolio page",
        "extra_orientations": "Focus on accessibility",
        "submission_files_to_read": ["index.html", "style.css"]
    }
}
```

**Output Example:**
```
Hey there! 👋

I reviewed your Bootstrap portfolio and you're off to a great start! 
You scored 85/100. Let's talk about what went well and what could be better.

✨ What You Nailed:
- Your navigation bar looks professional with proper Bootstrap classes
- You included all required sections (About, Projects, Contact)
- Great use of semantic HTML tags!

🔧 Areas to Improve:
1. Flexbox Layout (Lost 15 points)
   I noticed you're using 'display: block' for your project cards. Bootstrap's 
   grid system uses flexbox by default, so try using 'display: flex' on the 
   container for better alignment.
   
   💡 Hint: Check out Bootstrap's .d-flex utility class!

2. Media Queries (Lost 5 points)
   You're missing responsive breakpoints for mobile devices. Your page looks 
   great on desktop but needs work on smaller screens.
   
   💡 Hint: Bootstrap provides responsive grid classes like col-md-6 and 
   col-sm-12 that handle this automatically.

Keep coding! You're making great progress. 🚀
```

### Feedback Generation Process

```python
def generate_feedback(focused_tests, feedback_config):
    if feedback_mode == "default":
        return generate_default_feedback(focused_tests, feedback_config)
    else:
        return generate_ai_feedback(focused_tests, feedback_config)

def generate_ai_feedback(focused_tests, config):
    # 1. Read submission files (if configured)
    submission_context = read_submission_files(config.submission_files_to_read)
    
    # 2. Build prompt
    prompt = f"""
    You are a {config.feedback_persona} providing feedback to a student.
    
    Assignment Context: {config.assignment_context}
    Tone: {config.feedback_tone}
    Solutions: {config.provide_solutions}
    
    Student's Results:
    {format_focused_tests(focused_tests)}
    
    Student's Code:
    {submission_context}
    
    Provide constructive feedback that:
    1. Highlights what they did well
    2. Explains what needs improvement
    3. Provides {config.provide_solutions} for issues
    4. Encourages continued learning
    """
    
    # 3. Call OpenAI API
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content
```

---

## Web API Integration

### Architecture

The Web API provides a RESTful interface for creating grading configurations and submitting student work.

```
┌─────────────────────────────────────────┐
│          FastAPI Application            │
│                                         │
│  Endpoints:                             │
│  POST /grading-configs                  │
│  POST /submissions                      │
│  GET  /submissions/{id}                 │
│  GET  /submissions/{id}/results         │
└────────────┬────────────────────────────┘
             │
             ├─→ Database (PostgreSQL)
             │   ├─ grading_configurations
             │   ├─ submissions
             │   └─ results
             │
             └─→ Background Tasks
                 └─ grade_submission()
```

### Grading Configuration Storage

**Database Schema:**
```sql
CREATE TABLE grading_configurations (
    id SERIAL PRIMARY KEY,
    external_assignment_id VARCHAR(255) UNIQUE,
    template_name VARCHAR(100) NOT NULL,
    criteria_config JSON NOT NULL,
    language VARCHAR(50),
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
```

**API Endpoint:**
```python
@app.post("/grading-configs")
async def create_grading_config(
    external_assignment_id: str,
    template_name: str,
    criteria_config: dict,
    language: str
):
    # 1. Validate criteria config
    CriteriaConfig.from_dict(criteria_config)  # Raises if invalid
    
    # 2. Store in database
    config = await grading_config_repo.create(
        external_assignment_id=external_assignment_id,
        template_name=template_name,
        criteria_config=criteria_config,
        language=language
    )
    
    return {"id": config.id, "version": config.version}
```

### Submission Processing

**Database Schema:**
```sql
CREATE TABLE submissions (
    id SERIAL PRIMARY KEY,
    grading_config_id INTEGER REFERENCES grading_configurations(id),
    username VARCHAR(255) NOT NULL,
    external_user_id VARCHAR(255) NOT NULL,
    submission_files JSON NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE results (
    id SERIAL PRIMARY KEY,
    submission_id INTEGER REFERENCES submissions(id),
    final_score DECIMAL(5,2),
    feedback TEXT,
    result_tree JSON,
    execution_time_ms INTEGER,
    pipeline_status VARCHAR(50),
    error_message TEXT,
    graded_at TIMESTAMP
);
```

**API Endpoint:**
```python
@app.post("/submissions")
async def submit_for_grading(
    external_assignment_id: str,
    username: str,
    external_user_id: str,
    submission_files: dict
):
    # 1. Get grading configuration
    config = await grading_config_repo.get_by_external_id(external_assignment_id)
    
    # 2. Create submission record
    submission = await submission_repo.create(
        grading_config_id=config.id,
        username=username,
        external_user_id=external_user_id,
        submission_files=submission_files,
        status=SubmissionStatus.PENDING
    )
    
    # 3. Start background grading task
    BackgroundTasks.add_task(
        grade_submission,
        submission_id=submission.id,
        grading_config_id=config.id,
        template_name=config.template_name,
        criteria_config=config.criteria_config,
        language=config.language,
        username=username,
        external_user_id=external_user_id,
        submission_files=submission_files
    )
    
    return {
        "submission_id": submission.id,
        "status": "PENDING",
        "message": "Submission received and queued for grading"
    }
```

**Background Grading Task:**
```python
async def grade_submission(
    submission_id: int,
    grading_config_id: int,
    template_name: str,
    criteria_config: dict,
    language: str,
    username: str,
    external_user_id: str,
    submission_files: dict
):
    start_time = time.time()
    
    try:
        # 1. Update status to PROCESSING
        await submission_repo.update_status(submission_id, SubmissionStatus.PROCESSING)
        
        # 2. Build autograder pipeline
        pipeline = build_pipeline(
            template_name=template_name,
            include_feedback=True,
            grading_criteria=criteria_config,
            feedback_config=None,
            setup_config={},  # Triggers sandbox creation if needed
            custom_template=None,
            feedback_mode="default",
            export_results=False
        )
        
        # 3. Convert to Autograder Submission
        autograder_submission = Submission(
            username=username,
            user_id=external_user_id,
            assignment_id=grading_config_id,
            submission_files={
                filename: SubmissionFile(filename, content)
                for filename, content in submission_files.items()
            },
            language=Language[language.upper()] if language else None
        )
        
        # 4. Run pipeline
        pipeline_execution = pipeline.run(autograder_submission)
        
        # 5. Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # 6. Store results
        if pipeline_execution.result:
            await result_repo.create(
                submission_id=submission_id,
                final_score=pipeline_execution.result.final_score,
                feedback=pipeline_execution.result.feedback,
                result_tree=pipeline_execution.result.result_tree.to_dict(),
                execution_time_ms=execution_time_ms,
                pipeline_status=PipelineStatus.SUCCESS,
                graded_at=datetime.now(timezone.utc)
            )
            await submission_repo.update_status(submission_id, SubmissionStatus.COMPLETED)
        else:
            # Handle failure
            error_msg = "Pipeline failed"
            if pipeline_execution.step_results:
                last_step = pipeline_execution.get_previous_step()
                if last_step and last_step.error:
                    error_msg = last_step.error
            
            await result_repo.create(
                submission_id=submission_id,
                final_score=0.0,
                execution_time_ms=execution_time_ms,
                pipeline_status=PipelineStatus.FAILED,
                error_message=error_msg,
                graded_at=datetime.now(timezone.utc)
            )
            await submission_repo.update_status(submission_id, SubmissionStatus.FAILED)
    
    except Exception as e:
        # Handle exceptions
        await result_repo.create(
            submission_id=submission_id,
            final_score=0.0,
            pipeline_status=PipelineStatus.INTERRUPTED,
            error_message=str(e),
            graded_at=datetime.now(timezone.utc)
        )
        await submission_repo.update_status(submission_id, SubmissionStatus.FAILED)
```

---

## Implementation Examples

### Example 1: Complete Web Development Assignment

**Grading Configuration:**
```python
criteria_config = {
    "base": {
        "weight": 100,
        "subjects": [
            {
                "subject_name": "HTML Structure",
                "weight": 40,
                "tests": [
                    {
                        "name": "has_tag",
                        "file": "index.html",
                        "parameters": [
                            {"name": "tag", "value": "nav"},
                            {"name": "required_count", "value": 1}
                        ]
                    },
                    {
                        "name": "has_tag",
                        "file": "index.html",
                        "parameters": [
                            {"name": "tag", "value": "section"},
                            {"name": "required_count", "value": 3}
                        ]
                    }
                ]
            },
            {
                "subject_name": "CSS Styling",
                "weight": 40,
                "tests": [
                    {
                        "name": "has_class",
                        "file": "index.html",
                        "parameters": [
                            {"name": "class_names", "value": ["container", "row", "col-*"]},
                            {"name": "required_count", "value": 5}
                        ]
                    }
                ]
            },
            {
                "subject_name": "Bootstrap",
                "weight": 20,
                "tests": [
                    {
                        "name": "check_bootstrap_linked",
                        "file": "index.html"
                    }
                ]
            }
        ]
    },
    "bonus": {
        "weight": 20,
        "tests": [
            {
                "name": "check_media_queries",
                "file": "style.css",
                "parameters": [
                    {"name": "required_count", "value": 2}
                ]
            }
        ]
    }
}

feedback_config = {
    "general": {
        "report_title": "Portfolio Assessment",
        "show_score": True,
        "show_passed_tests": False
    },
    "default": {
        "category_headers": {
            "base": "✅ Required",
            "bonus": "⭐ Bonus"
        }
    }
}
```

**Build Pipeline:**
```python
pipeline = build_pipeline(
    template_name="webdev",
    include_feedback=True,
    grading_criteria=criteria_config,
    feedback_config=feedback_config,
    setup_config=None,  # No sandbox needed for webdev
    custom_template=None,
    feedback_mode="default",
    export_results=False
)
```

**Create Submission:**
```python
submission = Submission(
    username="jane.smith",
    user_id="student456",
    assignment_id=10,
    submission_files={
        "index.html": SubmissionFile(
            filename="index.html",
            content="""
                <!DOCTYPE html>
                <html>
                <head>
                    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
                    <link rel="stylesheet" href="style.css">
                </head>
                <body>
                    <nav class="navbar navbar-expand-lg">
                        <div class="container">Navigation</div>
                    </nav>
                    <section class="container">
                        <div class="row">
                            <div class="col-md-6">Content 1</div>
                            <div class="col-md-6">Content 2</div>
                        </div>
                    </section>
                    <section class="container">Section 2</section>
                    <section class="container">Section 3</section>
                </body>
                </html>
            """
        ),
        "style.css": SubmissionFile(
            filename="style.css",
            content="""
                @media (max-width: 768px) {
                    .container { padding: 10px; }
                }
                @media (max-width: 480px) {
                    .navbar { font-size: 14px; }
                }
            """
        )
    },
    language=None
)
```

**Execute:**
```python
result = pipeline.run(submission)

print(f"Status: {result.status}")
print(f"Final Score: {result.result.final_score}")
print(f"Feedback:\n{result.result.feedback}")
```

**Expected Output:**
```
Status: success
Final Score: 116.0

==========================================
Portfolio Assessment
==========================================
Final Score: 116/100 (Base: 100/100, Bonus: 16/20)

✅ Required (100/100)
-------------------------------------------
HTML Structure (100/100)
  [PASS] has_tag
    → Found 1/1 <nav> tags
  
  [PASS] has_tag
    → Found 3/3 <section> tags

CSS Styling (100/100)
  [PASS] has_class
    → Found 5/5 required Bootstrap classes

Bootstrap (100/100)
  [PASS] check_bootstrap_linked
    → Bootstrap CSS found in HTML

⭐ Bonus (16/20)
-------------------------------------------
[PASS] check_media_queries
  → Found 2/2 media queries for responsive design
```

### Example 2: Python I/O Program

**Setup Config:**
```python
setup_config = {
    "runtime_image": "python:3.9-slim",
    "execution_timeout": 10
}
```

**Criteria Config:**
```python
criteria_config = {
    "base": {
        "weight": 100,
        "tests": [
            {
                "name": "expect_output",
                "parameters": [
                    {
                        "name": "test_cases",
                        "value": [
                            [["5", "10"], "Sum: 15"],
                            [["20", "8"], "Sum: 28"]
                        ]
                    }
                ]
            }
        ]
    }
}
```

**Submission:**
```python
submission = Submission(
    username="bob.jones",
    user_id="student789",
    assignment_id=20,
    submission_files={
        "program.py": SubmissionFile(
            filename="program.py",
            content="""
num1 = int(input())
num2 = int(input())
print(f"Sum: {num1 + num2}")
            """
        )
    },
    language=Language.PYTHON
)
```

**Initialize Sandbox Manager:**
```python
# Must be called before grading
pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
manager = initialize_sandbox_manager(pool_configs)
```

**Build and Run:**
```python
pipeline = build_pipeline(
    template_name="IO",
    include_feedback=True,
    grading_criteria=criteria_config,
    feedback_config=feedback_config,
    setup_config=setup_config,  # Creates sandbox
    custom_template=None,
    feedback_mode="default",
    export_results=False
)

result = pipeline.run(submission)

# Cleanup
manager.shutdown()
```

---

## Summary

The Autograder system is a sophisticated, production-ready automated grading platform built on several key innovations:

### Key Architectural Decisions

1. **Stateless Pipeline Pattern**
   - Grading configurations create reusable pipelines
   - No state pollution between submissions
   - Scalable and thread-safe

2. **Tree-Based Scoring**
   - Hierarchical criteria enable complex grading schemes
   - Weighted scoring with categories, subjects, and tests
   - Support for bonus/penalty points

3. **Embedded Test Functions**
   - Test functions embedded during tree building
   - Eliminates lazy loading overhead
   - Improves performance and error handling

4. **Sandboxed Execution**
   - Docker-based isolation for untrusted code
   - Pool management for performance
   - Automatic cleanup and resource limits

5. **Step-Based Execution**
   - Clear separation of concerns
   - Traceable execution history
   - Easy to debug and extend

6. **Flexible Feedback**
   - Support for structured and AI-powered feedback
   - Configurable tone, persona, and detail level
   - Focus on high-impact failures

### For Human Readers

This documentation provides a complete understanding of:
- How grading configurations are structured
- How submissions flow through the pipeline
- How scores are calculated recursively
- How sandboxes provide secure execution
- How feedback is generated

### For AI Agents

This documentation enables autonomous operation by providing:
- Complete API specifications
- Algorithm implementations
- Data structure definitions
- Error handling patterns
- Integration examples

The system is designed to be both powerful and understandable, enabling educators to create sophisticated grading schemes while maintaining clarity and reliability in execution.

