# Autograder Documentation

Welcome to the complete documentation for the Autograder system.

## Documentation Files

### 📘 [Complete System Documentation](./COMPLETE_SYSTEM_DOCUMENTATION.md)
**The definitive guide to the Autograder system** - A comprehensive 1000+ line technical document covering:

- **System Overview**: Architecture, design principles, and data flow
- **Grading Configuration**: Criteria trees, templates, feedback, and preflight checks
- **Submission Processing**: How student work flows through the system
- **Autograder Pipeline**: Detailed explanation of all 7 pipeline steps
- **Criteria Tree Deep Dive**: Structure, nodes, weights, and algorithms
- **Result Tree Deep Dive**: Score calculation, tree traversal, and aggregation
- **Grading Templates**: Template architecture and built-in test libraries
- **Sandbox Manager**: Docker-based isolation and pool management
- **Algorithms & Scoring**: Complete algorithm implementations with complexity analysis
- **Feedback Generation**: Default and AI-powered feedback systems
- **Web API Integration**: REST API, database schema, and background processing
- **Implementation Examples**: Real-world usage patterns

**Target Audience**: Developers, system architects, AI agents, and technical users

### 📊 [Visual Diagrams](./VISUAL_DIAGRAMS.md)
**System visualizations and flow charts** - ASCII diagrams showing:
- System architecture overview
- Pipeline execution flow
- Criteria and Result tree structures
- Weight balancing algorithms
- Focus service impact calculation
- Sandbox pool management lifecycle
- Web API request flow
- Test function execution patterns

**Target Audience**: Visual learners, new developers, system designers

### ⚡ [Quick Reference Guide](./QUICK_REFERENCE.md)
**Fast lookups and common patterns** - Practical reference for:
- Building pipelines (with examples)
- Configuration schemas and templates
- API reference for core classes
- Common usage patterns
- Troubleshooting guide
- Performance tips
- CLI commands
- File locations

**Target Audience**: Developers actively using the system

---

## Quick Navigation

### For Developers
- Start with [System Overview](./COMPLETE_SYSTEM_DOCUMENTATION.md#system-overview)
- Understand [Core Architecture](./COMPLETE_SYSTEM_DOCUMENTATION.md#core-architecture)
- Learn [Pipeline Steps](./COMPLETE_SYSTEM_DOCUMENTATION.md#the-autograder-pipeline)

### For Educators
- Read [Grading Configuration](./COMPLETE_SYSTEM_DOCUMENTATION.md#grading-configuration)
- Explore [Grading Templates](./COMPLETE_SYSTEM_DOCUMENTATION.md#grading-templates)
- Review [Implementation Examples](./COMPLETE_SYSTEM_DOCUMENTATION.md#implementation-examples)

### For AI Agents
- Parse [Algorithms & Scoring](./COMPLETE_SYSTEM_DOCUMENTATION.md#algorithms--scoring)
- Study [Data Flow](./COMPLETE_SYSTEM_DOCUMENTATION.md#data-flow)
- Reference [Web API Integration](./COMPLETE_SYSTEM_DOCUMENTATION.md#web-api-integration)

---

## Key Concepts

### 1. Stateless Pipeline Architecture
The Autograder uses a **pipeline pattern** where:
- A grading configuration creates a reusable `AutograderPipeline`
- The same pipeline can grade unlimited submissions
- No state pollution between executions
- Thread-safe and horizontally scalable

### 2. Tree-Based Scoring
Grading criteria are organized as **hierarchical trees**:
```
CriteriaTree
├─ Base Category (required, 100 points)
│  ├─ Subject 1 (weighted)
│  │  ├─ Test 1
│  │  └─ Test 2
│  └─ Subject 2
│     └─ Test 3
├─ Bonus Category (optional, adds points)
└─ Penalty Category (optional, subtracts points)
```

Scores flow **bottom-up**: test scores → subject scores → category scores → final score

### 3. Sandboxed Execution
Untrusted student code runs in **Docker containers**:
- Pre-warmed container pools for performance
- Automatic resource limits (CPU, memory, time)
- Network isolation and file system protection
- Automatic cleanup and reuse

### 4. Step-Based Processing
Each submission flows through up to 7 steps:
1. **Load Template** - Get test functions
2. **Build Tree** - Create criteria hierarchy
3. **Pre-Flight** - Validate & sandbox (optional)
4. **Grade** - Execute tests & build result tree
5. **Focus** - Identify key failures
6. **Feedback** - Generate student feedback
7. **Export** - Send to external systems (optional)

---

## Core Components

### PipelineExecution
The **stateful execution context** that tracks:
- All step results
- Submission being graded
- Pipeline status (RUNNING, SUCCESS, FAILED, INTERRUPTED)
- Final grading result

### CriteriaTree (Stateless)
The **definition** of grading criteria:
- Built once from configuration
- Contains test function references
- Reusable across all submissions
- Weight-balanced hierarchy

### ResultTree (Stateful)
The **result** of grading execution:
- Created per submission
- Mirrors CriteriaTree structure
- Contains actual scores and reports
- Supports bottom-up score calculation

---

## System Architecture

```
┌────────────────────────────────────────────────────────┐
│                  WEB API (FastAPI)                     │
│  • REST endpoints for configs and submissions          │
│  • PostgreSQL database                                 │
│  • Background grading tasks                            │
└─────────────────────┬──────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│              AUTOGRADER CORE                           │
│  ┌──────────────────────────────────────────────────┐ │
│  │        AutograderPipeline                        │ │
│  │  (Orchestrates step-by-step grading)             │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
│  Components:                                           │
│  • CriteriaTreeService - Tree building                │
│  • GraderService - Test execution                     │
│  • FocusService - Impact analysis                     │
│  • ReporterService - Feedback generation              │
│  • TemplateLibraryService - Test libraries            │
└─────────────────────┬──────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│              SANDBOX MANAGER                           │
│  • Docker container pools (Python, Java, Node, C++)    │
│  • Acquire/release pattern                            │
│  • Automatic cleanup and monitoring                   │
└────────────────────────────────────────────────────────┘
```

---

## Data Models

### Submission
```python
@dataclass
class Submission:
    username: str
    user_id: int
    assignment_id: int
    submission_files: Dict[str, SubmissionFile]
    language: Optional[Language]
```

### GradingResult
```python
@dataclass
class GradingResult:
    final_score: float           # 0-100
    feedback: Optional[str]      # Human-readable feedback
    result_tree: ResultTree      # Complete execution tree
```

### PipelineExecution
```python
@dataclass
class PipelineExecution:
    step_results: List[StepResult]
    assignment_id: int
    submission: Submission
    status: PipelineStatus
    result: Optional[GradingResult]
```

---

## Usage Examples

### Basic Usage
```python
# 1. Build pipeline (once per assignment)
pipeline = build_pipeline(
    template_name="webdev",
    include_feedback=True,
    grading_criteria=criteria_dict,
    feedback_config=feedback_dict,
    setup_config=None,
    custom_template=None,
    feedback_mode="default",
    export_results=False
)

# 2. Create submission
submission = Submission(
    username="student123",
    user_id="ext_123",
    assignment_id=42,
    submission_files={
        "index.html": SubmissionFile("index.html", "<html>...</html>")
    }
)

# 3. Grade (reuse pipeline for many submissions)
result = pipeline.run(submission)

# 4. Access results
print(f"Score: {result.result.final_score}")
print(f"Feedback: {result.result.feedback}")
```

### With Sandboxed Execution
```python
# Initialize sandbox manager (once at startup)
pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
manager = initialize_sandbox_manager(pool_configs)

# Build pipeline with sandbox support
pipeline = build_pipeline(
    template_name="IO",
    include_feedback=True,
    grading_criteria=criteria_dict,
    feedback_config=feedback_dict,
    setup_config={},  # Triggers sandbox creation
    feedback_mode="default",
    export_results=False
)

# Create submission with language
submission = Submission(
    username="student456",
    user_id="ext_456",
    assignment_id=43,
    submission_files={
        "program.py": SubmissionFile("program.py", "print('Hello')")
    },
    language=Language.PYTHON
)

# Grade (sandbox automatically acquired and released)
result = pipeline.run(submission)

# Cleanup on shutdown
manager.shutdown()
```

---

## Performance Characteristics

### Pipeline Execution
- **Build Time**: O(n) where n = number of criteria nodes
- **Grading Time**: O(n*t) where t = average test execution time
- **Score Calculation**: O(n) single tree traversal
- **Memory**: O(n) for trees

### Sandbox Management
- **Pool Warm-up**: Pre-creates containers on startup
- **Acquisition**: O(1) if containers available, blocking if pool exhausted
- **Cleanup**: Automatic after each grading session
- **Scaling**: Configurable min/max containers per language

### Database Operations
- **Config Creation**: Single INSERT
- **Submission Processing**: 
  - INSERT submission (immediate)
  - Background grading task (async)
  - INSERT result (after completion)
- **Retrieval**: Indexed queries on submission_id

---

## Security Considerations

### Code Execution
- **Isolation**: All student code runs in Docker containers
- **Resource Limits**: CPU, memory, and time restrictions
- **Network**: No external network access from containers
- **File System**: Read-only base image, submission files in separate volume

### API Security
- **Authentication**: External user IDs tracked
- **Validation**: Pydantic models validate all inputs
- **Rate Limiting**: Background task queue prevents overload
- **Error Handling**: Graceful failures with detailed error messages

---

## Extending the System

### Adding a New Template
```python
class MyTemplate(Template):
    def __init__(self):
        self.tests = {
            "my_test": MyTestFunction()
        }
    
    @property
    def template_name(self):
        return "My Template"
    
    @property
    def requires_sandbox(self) -> bool:
        return False  # or True if needs execution
    
    def get_test(self, name: str) -> TestFunction:
        return self.tests.get(name)

class MyTestFunction(TestFunction):
    @property
    def name(self):
        return "my_test"
    
    def execute(self, files, sandbox, **kwargs) -> TestResult:
        # Implement test logic
        return TestResult(self.name, score=100, report="Success")
```

### Adding a Pipeline Step
```python
class MyCustomStep(Step):
    def execute(self, input: PipelineExecution) -> PipelineExecution:
        # Process input
        result = do_custom_processing(input)
        
        # Return updated execution
        return input.add_step_result(
            StepResult(
                step=StepName.MY_STEP,
                data=result,
                status=StepStatus.SUCCESS
            )
        )

# Add to pipeline
pipeline.add_step(StepName.MY_STEP, MyCustomStep())
```

---

## Troubleshooting

### Common Issues

**Pipeline Failure**
- Check `pipeline_execution.status` and `pipeline_execution.get_previous_step().error`
- Review step results: `pipeline_execution.step_results`

**Sandbox Errors**
- Ensure Docker is running
- Verify sandbox images are built: `docker images | grep sandbox`
- Check pool configuration in `sandbox_config.yml`

**Score Calculation Issues**
- Verify weight balancing: sibling weights should sum to 100
- Check heterogeneous tree configuration: `subjects_weight` must be set
- Review test scores: all should be 0-100

**Template Not Found**
- Verify template name is lowercase: "webdev", "io", "api", "essay"
- For custom templates, ensure they're properly loaded

---

## Contributing

When contributing to the documentation:

1. **Maintain Clarity**: Write for both humans and AI agents
2. **Provide Examples**: Include real code snippets
3. **Explain Algorithms**: Show step-by-step processes
4. **Update Diagrams**: Keep architecture diagrams current
5. **Version Changes**: Note breaking changes and migrations

---

## Version History

**v2.0** (February 2026)
- Complete architecture refactoring to pipeline pattern
- Stateless pipeline design
- Tree-based scoring with embedded test functions
- Sandbox manager with pool pattern
- Web API integration
- Complete documentation overhaul

---

## License

[Add your license information here]

---

## Contact

For questions, issues, or contributions, please contact:
- Development Team: [Add contact info]
- Documentation: [Add contact info]


