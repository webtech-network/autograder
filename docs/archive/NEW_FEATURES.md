# Autograder - New Features & Requirements

**Version:** 2.0.0  
**Last Updated:** February 17, 2026  
**Status:** Feature Planning & Implementation

---

## Table of Contents

1. [Overview](#overview)
2. [New Feature: Code Execution Without Grading](#new-feature-code-execution-without-grading)
3. [Future Feature: Static Code Analysis](#future-feature-static-code-analysis)
4. [Implementation Guidelines](#implementation-guidelines)
5. [Testing Requirements](#testing-requirements)

---

## Overview

This document specifies new features and endpoints required for the Autograder service to support the Prisma learning platform. These features extend the existing autograder functionality without modifying the core grading pipeline.

### Current Autograder Capabilities

- ✅ Secure sandbox execution
- ✅ Multi-language support (Python, Java, C++, JavaScript/Node.js)
- ✅ Criteria tree-based grading
- ✅ AI-powered feedback generation
- ✅ Focus-based failure analysis
- ✅ Test result tree generation

### New Requirements from Prisma Integration

- 🆕 **Code execution without grading** (manual testing in IDE)
- 🔜 **Static code analysis** (pre-submission quality checks)
- 🔄 **Enhanced error reporting** (better student-facing messages)

---

## New Feature: Code Execution Without Grading

### Purpose

Allow students to run their code with custom input directly from the Prisma IDE without triggering the full grading pipeline. This enables rapid iteration and manual testing before submission.

### Use Cases

1. **Manual Testing**: Student writes code, provides input, sees output
2. **Debugging**: Student tests edge cases before submitting
3. **Learning**: Student experiments with code behavior
4. **Quick Validation**: Check syntax and runtime errors

### Endpoint Specification

#### POST /api/v1/execute

**Description**: Execute code in a sandbox with custom input, return output without grading.

**Authentication**: Required (Bearer token from Prisma)

**Request Body**:
```json
{
  "language": "python",
  "code": "n = int(input())\nprint(n * n)",
  "input": "5\n",
  "timeoutMs": 5000,
  "memoryLimitMb": 128
}
```

**Request Fields**:
- `language` (required): `python`, `java`, `cpp`, `javascript`
- `code` (required): Source code to execute
- `input` (required): stdin input for the program (can be empty string)
- `timeoutMs` (optional, default: 5000): Execution timeout in milliseconds
- `memoryLimitMb` (optional, default: 128): Memory limit in megabytes

**Response (Success)**:
```json
{
  "executionId": "exec_abc123",
  "status": "SUCCESS",
  "stdout": "25\n",
  "stderr": "",
  "exitCode": 0,
  "executionTimeMs": 42,
  "memoryUsedMb": 8.2,
  "timestamp": "2026-02-17T10:15:03Z"
}
```

**Response (Runtime Error)**:
```json
{
  "executionId": "exec_def456",
  "status": "RUNTIME_ERROR",
  "stdout": "",
  "stderr": "Traceback (most recent call last):\n  File \"main.py\", line 1, in <module>\n    print(1/0)\nZeroDivisionError: division by zero\n",
  "exitCode": 1,
  "executionTimeMs": 23,
  "memoryUsedMb": 8.1,
  "error": {
    "type": "ZeroDivisionError",
    "message": "division by zero",
    "line": 1,
    "studentFriendly": "Your code tried to divide by zero. Check your calculations!"
  },
  "timestamp": "2026-02-17T10:15:03Z"
}
```

**Response (Timeout)**:
```json
{
  "executionId": "exec_ghi789",
  "status": "TIMEOUT",
  "stdout": "partial output...",
  "stderr": "",
  "exitCode": null,
  "executionTimeMs": 5000,
  "memoryUsedMb": 15.3,
  "error": {
    "type": "TimeoutError",
    "message": "Execution exceeded 5000ms timeout",
    "studentFriendly": "Your code took too long to run (>5s). Check for infinite loops!"
  },
  "timestamp": "2026-02-17T10:15:08Z"
}
```

**Response (Memory Limit)**:
```json
{
  "executionId": "exec_jkl012",
  "status": "MEMORY_LIMIT_EXCEEDED",
  "stdout": "",
  "stderr": "Killed\n",
  "exitCode": 137,
  "executionTimeMs": 234,
  "memoryUsedMb": 128.0,
  "error": {
    "type": "MemoryError",
    "message": "Process used more than 128MB memory",
    "studentFriendly": "Your code used too much memory. Try using less data!"
  },
  "timestamp": "2026-02-17T10:15:03Z"
}
```

**Response (Compilation Error - Java/C++)**:
```json
{
  "executionId": "exec_mno345",
  "status": "COMPILATION_ERROR",
  "stdout": "",
  "stderr": "Main.java:5: error: ';' expected\n    System.out.println(\"Hello\")\n                               ^\n1 error\n",
  "exitCode": null,
  "executionTimeMs": 0,
  "memoryUsedMb": 0,
  "error": {
    "type": "CompilationError",
    "message": "';' expected",
    "line": 5,
    "column": 31,
    "studentFriendly": "Missing semicolon at line 5. Add ';' at the end of the statement!"
  },
  "timestamp": "2026-02-17T10:15:02Z"
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `SUCCESS` | Code executed successfully, no errors |
| `RUNTIME_ERROR` | Code crashed during execution |
| `TIMEOUT` | Execution exceeded time limit |
| `MEMORY_LIMIT_EXCEEDED` | Process used too much memory |
| `COMPILATION_ERROR` | Code failed to compile (Java/C++) |
| `SYSTEM_ERROR` | Internal autograder error |

### Implementation Details

#### Architecture

```
POST /api/v1/execute
    ↓
┌────────────────────────────┐
│  FastAPI Endpoint Handler  │
│  - Validate request        │
│  - Rate limit check        │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│   Execute Code Service     │
│  - NO grading logic        │
│  - NO test suite loading   │
│  - NO criteria tree        │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│    Sandbox Manager         │
│  - Acquire sandbox         │
│  - Write code + input      │
│  - Execute with limits     │
│  - Capture output          │
│  - Release sandbox         │
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│   Format Response          │
│  - Parse errors            │
│  - Student-friendly msgs   │
│  - Return JSON             │
└────────────────────────────┘
```

#### Key Differences from Grading Endpoint

**Code Execution (`/execute`)**:
- ❌ No criteria.json required
- ❌ No test suite execution
- ❌ No scoring calculation
- ❌ No feedback generation
- ❌ No result tree
- ✅ Single code execution
- ✅ Direct stdout/stderr capture
- ✅ Fast response (<500ms typical)

**Grading (`/submissions`)**:
- ✅ Requires criteria.json
- ✅ Executes multiple tests
- ✅ Calculates weighted scores
- ✅ Generates AI feedback
- ✅ Returns result tree
- ⏱️ Slower response (3-5s typical)

#### Sandbox Reuse

Leverage existing `SandboxManager` infrastructure:

```python
# autograder/services/execution_service.py
from sandbox_manager.manager import SandboxManager

class ExecutionService:
    def __init__(self, sandbox_manager: SandboxManager):
        self.sandbox_manager = sandbox_manager
    
    async def execute_code(self, request: ExecuteRequest) -> ExecuteResponse:
        """Execute code without grading logic."""
        
        # Acquire sandbox from pool
        sandbox = await self.sandbox_manager.acquire(
            language=request.language,
            timeout_ms=request.timeoutMs,
            memory_limit_mb=request.memoryLimitMb
        )
        
        try:
            # Write code to sandbox
            await sandbox.write_file("main.py", request.code)
            
            # Execute with stdin
            result = await sandbox.execute(
                command=self._get_run_command(request.language),
                stdin=request.input,
                timeout_ms=request.timeoutMs
            )
            
            # Parse output
            return ExecuteResponse(
                executionId=generate_id(),
                status=self._determine_status(result),
                stdout=result.stdout,
                stderr=result.stderr,
                exitCode=result.exit_code,
                executionTimeMs=result.duration_ms,
                memoryUsedMb=result.memory_mb,
                error=self._parse_error(result) if result.exit_code != 0 else None
            )
        
        finally:
            # Release sandbox back to pool
            await self.sandbox_manager.release(sandbox)
```

#### Error Parsing

Provide student-friendly error messages:

```python
def _parse_error(self, result: ExecutionResult) -> ErrorInfo:
    """Parse technical errors into student-friendly messages."""
    
    stderr = result.stderr
    
    # Python exceptions
    if "ZeroDivisionError" in stderr:
        return ErrorInfo(
            type="ZeroDivisionError",
            message="division by zero",
            line=self._extract_line_number(stderr),
            studentFriendly="Your code tried to divide by zero. Check your calculations!"
        )
    
    if "RecursionError" in stderr:
        return ErrorInfo(
            type="RecursionError",
            message="maximum recursion depth exceeded",
            line=self._extract_line_number(stderr),
            studentFriendly="Your recursive function is calling itself too many times. Add a base case!"
        )
    
    if "SyntaxError" in stderr:
        return ErrorInfo(
            type="SyntaxError",
            message=self._extract_syntax_error_message(stderr),
            line=self._extract_line_number(stderr),
            studentFriendly="There's a syntax error in your code. Check the line mentioned!"
        )
    
    # Java compilation errors
    if "error:" in stderr and request.language == "java":
        return self._parse_java_compilation_error(stderr)
    
    # Generic error
    return ErrorInfo(
        type="RuntimeError",
        message=stderr[:200],  # First 200 chars
        studentFriendly="Something went wrong. Check your code and try again!"
    )
```

#### Rate Limiting

Prevent abuse while allowing legitimate testing:

```python
# Rate limit: 10 executions per minute per user
from fastapi_limiter.depends import RateLimiter

@router.post("/api/v1/execute")
@limiter.limit("10/minute")
async def execute_code(
    request: ExecuteRequest,
    user_id: str = Depends(get_current_user)
):
    # ... execution logic
```

### Security Considerations

1. **Same Sandbox Isolation**: Use identical security as grading
2. **Resource Limits**: Enforce strict CPU, memory, time limits
3. **No Network Access**: Sandbox has no internet connectivity
4. **File System Restrictions**: Read-only except for `/tmp`
5. **Process Isolation**: Each execution in separate container
6. **Input Validation**: Sanitize code and input for common exploits

### Performance Requirements

- **Response Time**: < 500ms for typical execution (excluding code runtime)
- **Throughput**: Support 50+ concurrent executions
- **Sandbox Pool**: Pre-warmed containers ready for instant use
- **Cleanup**: Automatic sandbox cleanup after each execution

### Testing Requirements

#### Unit Tests

```python
# tests/test_execution_service.py
async def test_execute_simple_code():
    """Test successful code execution."""
    request = ExecuteRequest(
        language="python",
        code="print('Hello, World!')",
        input=""
    )
    
    response = await execution_service.execute_code(request)
    
    assert response.status == "SUCCESS"
    assert response.stdout == "Hello, World!\n"
    assert response.exitCode == 0

async def test_execute_with_input():
    """Test code execution with stdin."""
    request = ExecuteRequest(
        language="python",
        code="n = int(input())\nprint(n * 2)",
        input="5"
    )
    
    response = await execution_service.execute_code(request)
    
    assert response.status == "SUCCESS"
    assert response.stdout == "10\n"

async def test_execution_timeout():
    """Test timeout handling."""
    request = ExecuteRequest(
        language="python",
        code="import time\ntime.sleep(10)",
        input="",
        timeoutMs=1000
    )
    
    response = await execution_service.execute_code(request)
    
    assert response.status == "TIMEOUT"
    assert response.executionTimeMs >= 1000

async def test_runtime_error():
    """Test runtime error handling."""
    request = ExecuteRequest(
        language="python",
        code="print(1/0)",
        input=""
    )
    
    response = await execution_service.execute_code(request)
    
    assert response.status == "RUNTIME_ERROR"
    assert "ZeroDivisionError" in response.stderr
    assert response.error.studentFriendly is not None
```

#### Integration Tests

```python
# tests/integration/test_execute_endpoint.py
async def test_execute_endpoint_python():
    """Test execute endpoint with Python code."""
    response = await client.post(
        "/api/v1/execute",
        json={
            "language": "python",
            "code": "n = int(input())\nprint(n ** 2)",
            "input": "5"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["stdout"] == "25\n"

async def test_execute_endpoint_rate_limit():
    """Test rate limiting."""
    # Make 11 requests (limit is 10/minute)
    for i in range(11):
        response = await client.post("/api/v1/execute", json=valid_request)
        if i < 10:
            assert response.status_code == 200
        else:
            assert response.status_code == 429  # Too Many Requests
```

---

## Future Feature: Static Code Analysis

### Purpose

Analyze code quality before or during grading without executing the code. Provides early feedback on style, complexity, and potential issues.

### Use Cases

1. **Pre-Submission Analysis**: Show warnings before student submits
2. **Code Quality Scoring**: Include as bonus/penalty in grading
3. **Learning Opportunity**: Teach best practices
4. **Reduced Execution**: Catch obvious issues without running code

### Endpoint Specification (Proposed)

#### POST /api/v1/analyze

**Description**: Perform static analysis on code without executing it.

**Request Body**:
```json
{
  "language": "python",
  "code": "def factorial(n):\n    if n==0:\n        return 1\n    return n*factorial(n-1)",
  "analysisLevel": "standard",
  "rules": ["style", "complexity", "security", "best-practices"]
}
```

**Request Fields**:
- `language` (required): Programming language
- `code` (required): Source code to analyze
- `analysisLevel` (optional): `basic`, `standard`, `strict`
- `rules` (optional): Array of rule categories to check

**Response**:
```json
{
  "analysisId": "analysis_abc123",
  "language": "python",
  "status": "COMPLETED",
  "issues": [
    {
      "severity": "warning",
      "category": "style",
      "rule": "E225",
      "message": "missing whitespace around operator",
      "line": 2,
      "column": 9,
      "snippet": "    if n==0:",
      "suggestion": "    if n == 0:",
      "studentFriendly": "Add spaces around the == operator for better readability"
    },
    {
      "severity": "info",
      "category": "complexity",
      "rule": "C901",
      "message": "function is too complex (complexity: 3)",
      "line": 1,
      "function": "factorial",
      "suggestion": "Consider simplifying or breaking into smaller functions",
      "studentFriendly": "Your function could be simpler. Try an iterative approach!"
    },
    {
      "severity": "info",
      "category": "best-practices",
      "rule": "BP001",
      "message": "No docstring found",
      "line": 1,
      "suggestion": "Add a docstring explaining what the function does",
      "studentFriendly": "Add a comment at the start of your function explaining what it does"
    }
  ],
  "metrics": {
    "linesOfCode": 4,
    "cyclomaticComplexity": 3,
    "maintainabilityIndex": 78.5,
    "readabilityScore": 7.2,
    "commentRatio": 0.0
  },
  "summary": {
    "totalIssues": 3,
    "errors": 0,
    "warnings": 1,
    "info": 2,
    "qualityGrade": "B",
    "passesMinimumStandards": true
  },
  "timestamp": "2026-02-17T10:20:00Z"
}
```

### Analysis Tools by Language

#### Python
- **Style**: `flake8`, `pylint`, `pycodestyle`
- **Complexity**: `radon`, `mccabe`
- **Security**: `bandit`
- **Type Checking**: `mypy` (if type hints present)

#### Java
- **Style**: `Checkstyle`
- **Bugs**: `SpotBugs`, `PMD`
- **Security**: `Find Security Bugs`

#### C++
- **Style**: `clang-tidy`, `clang-format`
- **Issues**: `cppcheck`
- **Security**: Basic buffer overflow detection

#### JavaScript
- **Style**: `ESLint`, `Prettier`
- **Complexity**: `eslint-plugin-complexity`

### Integration with Grading

Static analysis can be integrated into the grading pipeline:

```json
{
  "test_library": "input_output",
  "base": {
    "weight": 100,
    "tests": [...]
  },
  "bonus": {
    "weight": 10,
    "tests": [
      {
        "name": "code_quality",
        "type": "static_analysis",
        "parameters": {
          "rules": ["style", "complexity"],
          "minimumQualityGrade": "B"
        },
        "weight": 100
      }
    ]
  },
  "penalty": {
    "weight": -5,
    "tests": [
      {
        "name": "style_violations",
        "type": "static_analysis",
        "parameters": {
          "maxWarnings": 5
        },
        "weight": 100
      }
    ]
  }
}
```

### Implementation Phases

**Phase 1** (Post-MVP):
- Basic style checking (Python: flake8)
- Simple metrics (lines of code, complexity)
- Student-friendly error messages

**Phase 2**:
- Multi-language support (Java, C++, JavaScript)
- Configurable rule sets
- Integration with grading criteria

**Phase 3**:
- Advanced security checks
- Machine learning for custom rule learning
- Real-time analysis in IDE (as student types)

### Student-Facing Integration

#### Pre-Submission Warnings

```
┌─────────────────────────────────────────┐
│  ⚠️  Code Quality Issues Detected       │
├─────────────────────────────────────────┤
│                                         │
│  3 issues found (none are blockers):    │
│                                         │
│  ⚠️  Line 2: Add spaces around ==       │
│  ℹ️  Line 1: Add a function docstring   │
│  ℹ️  Consider using an iterative approach│
│                                         │
│  [View Details] [Submit Anyway]         │
└─────────────────────────────────────────┘
```

#### Post-Submission Feedback

Included in feedback alongside test results:

```
📊 Code Quality Analysis

Grade: B (78.5/100)

✅ Strengths:
- Correct algorithm implementation
- Good variable naming

⚠️  Suggestions:
- Add whitespace around operators (line 2)
- Include function documentation
- Consider iterative vs recursive approach

Your code works correctly, but improving these areas will
make it more professional and maintainable!
```

---

## Implementation Guidelines

### Code Organization

```
autograder/
├── services/
│   ├── execution_service.py      # NEW: Code execution without grading
│   ├── analysis_service.py       # NEW: Static analysis (future)
│   ├── grading_service.py        # EXISTING: Full grading pipeline
│   └── feedback_service.py       # EXISTING: AI feedback generation
├── web/
│   ├── routers/
│   │   ├── execution.py          # NEW: /execute endpoint
│   │   ├── analysis.py           # NEW: /analyze endpoint (future)
│   │   └── submissions.py        # EXISTING: /submissions endpoint
└── models/
    ├── execution.py              # NEW: ExecuteRequest/Response models
    └── analysis.py               # NEW: AnalysisRequest/Response models (future)
```

### Configuration

```yaml
# autograder/config/execution.yaml
execution:
  defaults:
    timeout_ms: 5000
    memory_limit_mb: 128
    max_output_size_kb: 100
  
  rate_limits:
    per_user_per_minute: 10
    per_user_per_hour: 100
  
  sandbox:
    reuse_pool: true
    pool_size: 10
    max_lifetime_ms: 300000

analysis:
  enabled: false  # Feature flag for static analysis
  tools:
    python:
      - flake8
      - radon
    java:
      - checkstyle
```

### Logging

```python
# Structured logging for execution requests
logger.info(
    "Code execution started",
    extra={
        "execution_id": execution_id,
        "user_id": user_id,
        "language": request.language,
        "code_length": len(request.code),
        "input_length": len(request.input)
    }
)

# Log results
logger.info(
    "Code execution completed",
    extra={
        "execution_id": execution_id,
        "status": response.status,
        "execution_time_ms": response.executionTimeMs,
        "memory_used_mb": response.memoryUsedMb,
        "exit_code": response.exitCode
    }
)
```

### Monitoring

Track key metrics:
- Execution count per minute
- Average execution time
- Error rate by type
- Sandbox pool utilization
- Rate limit hits

```python
# Prometheus metrics
execution_count = Counter("autograder_executions_total", "Total executions", ["language", "status"])
execution_duration = Histogram("autograder_execution_duration_seconds", "Execution time", ["language"])
sandbox_pool_size = Gauge("autograder_sandbox_pool_size", "Available sandboxes", ["language"])
```

---

## Testing Requirements

### Test Coverage Goals

- **Unit Tests**: 90%+ coverage for new code
- **Integration Tests**: All endpoint scenarios covered
- **Load Tests**: Verify concurrent execution handling
- **Security Tests**: Sandbox escape attempts, malicious code

### Test Scenarios

#### Happy Path
- ✅ Simple Python script
- ✅ Code with stdin input
- ✅ Multi-line output
- ✅ Different languages

#### Error Handling
- ✅ Runtime errors (exceptions)
- ✅ Compilation errors (Java/C++)
- ✅ Timeout scenarios
- ✅ Memory limit exceeded
- ✅ Syntax errors

#### Edge Cases
- ✅ Empty code
- ✅ Empty input
- ✅ Large output (>100KB)
- ✅ Unicode characters
- ✅ Malformed requests

#### Security
- ✅ Attempted file system access
- ✅ Attempted network access
- ✅ Fork bombs
- ✅ Resource exhaustion attempts

### Performance Benchmarks

Run load tests to verify:
- 50 concurrent executions: < 1s response time
- 100 concurrent executions: < 2s response time
- Sandbox pool doesn't exhaust under normal load

```bash
# Load test with locust
locust -f tests/load/test_execute.py --headless -u 50 -r 10 -t 5m
```

---

**Document Maintained By**: Autograder Team  
**For Questions**: Contact autograder-dev@prisma.edu  
**Implementation Status**: `/execute` - Planned, `/analyze` - Future  
**Target Release**: Q1 2026
