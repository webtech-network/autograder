# Execution Helpers

This document describes the execution helper modules located at  
`autograder/builder/execution_helpers`. These helpers provide the primary
execution strategies used by the autograder.

All execution helpers implement a common abstract contract
(`ExecutionHelper`) and are intended to be used by the builder and grader
components when evaluating student submissions.

Currently, two execution strategies are available:

- `AiExecutor` (in `AI_Executor.py`) — runs automated grading via an AI model.
- `SandboxExecutor` (in `sandbox_executor.py`) — runs student code either inside
  an isolated Docker container (sandbox) or via a remote execution proxy.

---

## Locations

- `autograder/builder/execution_helpers/base.py`
- `autograder/builder/execution_helpers/AI_Executor.py`
- `autograder/builder/execution_helpers/sandbox_executor.py`

---

## Base Contract: ExecutionHelper (`base.py`)

Purpose:
- Define a minimal lifecycle contract for any execution environment used by the
  autograder.

The base class enforces a common interface so the builder can switch execution
strategies without coupling to implementation details.

```py
class ExecutionHelper(ABC):
    @abstractmethod
    def start(self):
        """Initialize resources (e.g., spin up Docker, connect to API)."""

    @abstractmethod
    def stop(self):
        """Finalize execution / cleanup resources."""
```
---

## AiExecutor (`AI_Executor.py`)

### Purpose

Send a batch of human-designed tests (textual prompts) plus the submission files
to an AI model and parse a deterministic JSON response containing scores and
feedback for each test.

The parsed AI results are mapped back into
`autograder.core.models.test_result.TestResult` objects used by the grading
pipeline.

---

### Key classes / models

- `TestInput` — Pydantic model representing a single test prompt.
- `TestOutput` — Pydantic model representing a single AI-evaluated result.
- `AIResponseModel` — Top-level Pydantic model describing the expected AI
  response structure.
- `AiExecutor` — main execution helper class.

---

### AiExecutor — main methods

- `start()` (classmethod)  
  Creates and returns a new `AiExecutor` instance.

- `_ensure_context()`  
  Lazily initializes context-dependent resources:
  - Loads submission files from `request_context`
  - Creates the OpenAI client using `get_secret(...)`

- `add_test(test_name: str, test_prompt: str)`  
  Adds a test to the batch and creates a placeholder `TestResult` used by the
  grading pipeline.

- `send_submission_files(submission_files)`  
  Overrides the submission files that will be included in the prompt.

- `_create_test_batch()`  
  Serializes the added tests into a JSON array for inclusion in the prompt.

- `_create_submission_files_string()`  
  Concatenates submission files into a formatted string block.

- `stop()`  
  Finalizes execution by sending prompts to the AI model, parsing the response,
  and mapping results back to `TestResult` objects.  
  This method does **not** perform resource cleanup.

---

### Important details

- Submission files are loaded lazily unless overridden.
- Uses the OpenAI **Responses API** via the `OpenAI` client.
- API keys are resolved using  
  `get_secret("OPENAI_API_KEY", "AUTOGRADER_OPENAI_KEY", ...)`.
- The AI must return a single valid JSON object matching `AIResponseModel`.

---

### Usage example (conceptual)

```py
from autograder.builder.execution_helpers.AI_Executor import AiExecutor

ai = AiExecutor.start()
ai.send_submission_files({'main.py': 'print("hi")'})
ai.add_test('Functionality: prints greeting', 'Does the program print "hi"?')
ai.stop()
```

---

### When to use

- Use `AiExecutor` for natural-language-based evaluation, rubric synthesis, or
  when tests are expressed as textual prompts evaluated by an LLM.

---

## SandboxExecutor (`sandbox_executor.py`)

### Purpose

Create, populate, execute commands in, and clean up an execution environment used
to run student submissions. This executor supports both local Docker-based
sandboxes and remote execution via a proxy.

---

## Configuration & Execution Modes

The `SandboxExecutor` determines its operation mode at runtime based on
environment variables.

### 1. LOCAL Mode (Default)

Activated when `TARGET_HOST` is **not set**.

- **Behavior:** Uses the local Docker daemon to spin up ephemeral containers.
- **Requirements:**
  - Local Docker socket access (`/var/run/docker.sock`).
  - `runtime_image` must be specified in `setup.json`.
- **Networking:** Maps container ports to random ephemeral ports on `localhost`.

---

### 2. PROXY Mode

Activated when `TARGET_HOST` is **set**.

- **Behavior:** Connects to a remote execution agent via HTTP. The executor waits
  (polls) for the agent to become available before starting tests.
- **Does not require Docker on the client machine.**
- **Configuration variables:**
  - `TARGET_HOST`: IP or hostname of the remote agent (**required**).
  - `TARGET_AGENT_PORT`: Port of the remote agent (default: `8080`).
- **Networking:** Uses the static `container_port` defined in config; no dynamic
  port mapping is performed on the client side.

---

### Internal Methods Reference

- `get_address()`
  - **Local:** Returns `http://localhost:<mapped_random_port>`
  - **Proxy:** Returns `http://<TARGET_HOST>:<container_port>`

- `start()`
  - **Local:** Immediately creates and starts the Docker container.
  - **Proxy:** Enters a retry loop (`_wait_for_agent_startup`), polling the agent
    until it responds or times out (30 seconds).

---

### Key methods

- `run_command(command: str, in_background=False)`  
  Executes a shell command locally in the container or remotely via the proxy API.

- `get_mapped_port(container_port: int)`  
  Returns the mapped host port (LOCAL) or the container port itself (PROXY).

- `stop()`  
  Removes the Docker container and cleans up resources (LOCAL mode only).

---

### Example `setup.json`

```json
{
  "file_checks": ["app.py", "requirements.txt"],
  "runtime_image": "python:3.11-slim",
  "container_port": 8000,
  "commands": [
    "pip install --no-cache-dir -r requirements.txt",
    "python app.py"
  ]
}
```

---

### When to use

- Use `SandboxExecutor` for evaluations that require running student code in
  isolation (unit tests, integration tests, compilation, or HTTP API testing).

---

## Extending and testing

- To add new execution strategies, create a new helper module in
  `execution_helpers` and implement the `ExecutionHelper` contract.
- Keep selection logic in the builder layer.

Testing tips:
- **AiExecutor:** mock the OpenAI client and `get_secret`, assert correct
  `TestResult` mapping.
- **SandboxExecutor:** mock Docker or HTTP requests for unit tests; use real
  Docker images for integration tests.

---

## Troubleshooting

- **AI parsing failures:** inspect printed system and user prompts and validate
  JSON structure.
- **Sandbox startup failures:** ensure Docker is running, the image exists, and
  the user has permission to manage containers.
- **Proxy issues:** verify `TARGET_HOST` and `TARGET_AGENT_PORT`.

---

## Links

- `autograder/builder/execution_helpers/base.py`
- `autograder/builder/execution_helpers/AI_Executor.py`
- `autograder/builder/execution_helpers/sandbox_executor.py`
