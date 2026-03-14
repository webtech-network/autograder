# Deliberate Code Execution (DCE) Feature

## Overview

The Deliberate Code Execution (DCE) feature allows users to execute code in sandboxed environments **without going through the full autograder pipeline**. This is a stateless feature designed for quick testing and debugging purposes.

## Use Cases

- **Pre-submission Testing**: Students can test their code before submitting it for grading
- **Debugging**: Quick feedback on code errors without creating a submission record
- **Interactive Execution**: Run code with stdin inputs to test interactive programs
- **Syntax Validation**: Verify code compiles/runs before final submission

## Key Features

✅ **Stateless**: No data is persisted - perfect for testing  
✅ **Multi-language**: Supports Python, Java, Node.js, and C++  
✅ **Interactive Input**: Support for stdin inputs  
✅ **Multiple Files**: Execute projects with multiple source files  
✅ **Error Classification**: Automatic categorization of errors (runtime, compilation, timeout, etc.)  
✅ **Fast**: Direct sandbox execution without grading overhead  

## API Endpoint

### POST `/api/v1/execute`

Execute code in a sandbox environment.

#### Request Body

```json
{
  "language": "python",
  "submission_files": [
    {
      "filename": "main.py",
      "content": "print('Hello, World!')"
    }
  ],
  "program_command": "python main.py",
  "test_cases": [["optional", "stdin", "inputs"]]
}
```

#### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | string | ✓ | Programming language: `python`, `java`, `node`, or `cpp` |
| `submission_files` | array | ✓ | List of files with `filename` and `content` |
| `program_command` | string | ✓ | Command to execute (e.g., `python main.py`) |
| `test_cases` | array | ✗ | Optional test cases. Each test case is a list of stdin inputs. If omitted, the program runs once with no input. |

#### Response

```json
{
  "results": [
    {
      "output": "Hello, World!\n",
      "category": "success",
      "error_message": null,
      "execution_time": 0.123
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `results` | array | One result object per test case (or one result if no test cases provided) |
| `results[].output` | string | Combined stdout/stderr output |
| `results[].category` | string | Result category: `success`, `runtime_error`, `compilation_error`, `timeout`, `system_error` |
| `results[].error_message` | string\|null | Error details if execution failed |
| `results[].execution_time` | float | Execution time in seconds |

## Examples

### 1. Simple Python Execution

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "submission_files": [
      {
        "filename": "main.py",
        "content": "print(\"Hello, World!\")"
      }
    ],
    "program_command": "python main.py"
  }'
```

### 2. Python with Interactive Input

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "submission_files": [
      {
        "filename": "calculator.py",
        "content": "a = int(input())\nb = int(input())\nprint(a + b)"
      }
    ],
    "program_command": "python calculator.py",
    "test_cases": [["10"], ["20"]]
  }'
```

### 3. Java Compilation and Execution

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "java",
    "submission_files": [
      {
        "filename": "Main.java",
        "content": "public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"Hello from Java!\");\n    }\n}"
      }
    ],
    "program_command": "javac Main.java && java Main"
  }'
```

### 4. C++ Compilation and Execution

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "cpp",
    "submission_files": [
      {
        "filename": "main.cpp",
        "content": "#include <iostream>\nint main() {\n    std::cout << \"Hello from C++!\" << std::endl;\n    return 0;\n}"
      }
    ],
    "program_command": "g++ main.cpp -o main && ./main"
  }'
```

### 5. Node.js Execution

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "node",
    "submission_files": [
      {
        "filename": "app.js",
        "content": "console.log(\"Hello from Node.js!\");"
      }
    ],
    "program_command": "node app.js"
  }'
```

### 6. Multiple Files

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "submission_files": [
      {
        "filename": "main.py",
        "content": "from utils import greet\ngreet(\"World\")"
      },
      {
        "filename": "utils.py",
        "content": "def greet(name):\n    print(f\"Hello, {name}!\")"
      }
    ],
    "program_command": "python main.py"
  }'
```

## Error Categories

The API automatically classifies execution results into categories:

| Category | Description | Example |
|----------|-------------|---------|
| `success` | Code executed successfully | Normal program completion |
| `runtime_error` | Program crashed during execution | Division by zero, null pointer |
| `compilation_error` | Code failed to compile | Syntax errors in Java/C++ |
| `timeout` | Execution exceeded time limit | Infinite loops |
| `system_error` | Infrastructure failure | Docker errors |

## Implementation Details

### Architecture

```
Client Request
    ↓
FastAPI Endpoint (/api/v1/execute)
    ↓
DeliberateExecutionService
    ↓
Sandbox Manager (acquire sandbox)
    ↓
Sandbox Container (prepare workdir + execute)
    ↓
Result Classification
    ↓
Response to Client
```

### Key Components

1. **Schema** (`web/schemas/execution.py`):
   - `DeliberateCodeExecutionRequest`: Request validation
   - `DeliberateCodeExecutionResponse`: Response structure

2. **Service** (`web/service/deliberate_execution_service.py`):
   - `execute_code()`: Core execution logic
   - Sandbox acquisition and release
   - Error handling

3. **Endpoint** (`web/api/v1/execution.py`):
   - POST `/execute` handler
   - Request validation
   - Error responses

### Sandbox Integration

The DCE feature uses the existing **Sandbox Manager** infrastructure:

- Acquires sandboxes from the pool
- Prepares workdir with submission files
- Executes commands with optional stdin
- Automatically releases sandbox back to pool
- Handles timeouts (30 seconds default)

### Security

- ✅ Sandboxed execution (Docker containers)
- ✅ Resource limits (CPU, memory)
- ✅ Network isolation
- ✅ Timeout protection
- ✅ No data persistence (stateless)

## Testing

Run the integration tests:

```bash
# Start the API server first
cd /path/to/project-root
python -m web.main

# In another terminal, run tests
python tests/integration/test_execution_endpoint.py
```

The test suite covers:
- ✅ Simple execution (all languages)
- ✅ Interactive input
- ✅ Runtime errors
- ✅ Compilation errors
- ✅ Multiple files
- ✅ Invalid language validation

## Limitations

1. **Stateless**: No execution history is stored
2. **Timeout**: 30 seconds maximum execution time
3. **No Grading**: This feature does not produce scores or feedback
4. **Single Execution**: Each request is independent

## Future Enhancements

- [ ] Configurable timeout per request
- [ ] Output size limits
- [ ] Execution history (optional persistence)
- [ ] Streaming output for long-running processes
- [ ] Custom resource limits per request

## Comparison with Submission Grading

| Feature | DCE | Submission Grading |
|---------|-----|-------------------|
| Purpose | Testing/Debugging | Grade assignment |
| Persistence | No | Yes (database) |
| Feedback | No | Yes |
| Scoring | No | Yes |
| Speed | Fast | Slower (full pipeline) |
| Use Case | Pre-submission | Final submission |

## Conclusion

The Deliberate Code Execution feature provides a lightweight, fast way for users to test their code before submission. It leverages the existing sandbox infrastructure while remaining completely stateless and optimal for quick feedback loops.

