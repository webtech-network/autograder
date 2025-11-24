# Execution Helpers

This document describes the execution helper modules located at
`autograder/builder/execution_helpers`. These helpers provide two
primary execution strategies used by the autograder:

- `AiExecutor` (in `AI_Executor.py`) — runs automated grading via an AI model.
- `SandboxExecutor` (in `sandbox_executor.py`) — runs student code inside an
  isolated Docker container (sandbox) for dynamic execution and API testing.

Both helpers are intended to be used by the builder and grader components
when evaluating student submissions.

## Locations

- `autograder/builder/execution_helpers/AI_Executor.py`
- `autograder/builder/execution_helpers/sandbox_executor.py`

## AiExecutor (AI_Executor.py)

Purpose:
- Send a batch of human-designed tests (prompts) plus the submission files to
  an AI model (via the OpenAI client) and parse a deterministic JSON response
  containing scores and feedback for each test.

Key classes / functions:
- `TestInput` / `TestOutput` / `AIResponseModel` — Pydantic models describing
  the request and expected AI response structure.
- `AiExecutor` — main class:
  - `add_test(test_name: str, test_prompt: str)` — add a test to the batch. It
    also creates a `TestResult` placeholder used by the rest of the grading
    pipeline.
  - `send_submission_files(submission_files)` — replace the submission files
    that will be included in the prompt.
  - `_create_test_batch()` — serialize added tests into JSON for the prompt.
  - `_create_submission_files_string()` — concatenate submission files into a
    single string block for inclusion in the user prompt.
  - `stop()` — sends the prompts to the AI model, parses the response into
    `test_results`, and calls `mapback()` to map AI outputs back to
    `TestResult` references.
  - `mapback()` — copies scores and feedback from AI response models back to
    `autograder.core.models.test_result.TestResult` objects.

Important details:
- The class reads `request_context.get_request().submission_files` by default
  when constructed, but `send_submission_files` lets callers provide a
  different dictionary.
- The AI call uses `OpenAI` client and `get_secret('OPENAI_API_KEY', ...)` to
  obtain the API key (via the project's secrets fetcher). Ensure secrets are
  available in env or secrets manager.
- The `stop()` method expects the AI to return a single JSON object matching
  `AIResponseModel` and will parse `response.output[1].content[0].parsed.results`.
  If the AI call fails or returns unexpected data, `stop()` will report an
  exception and return an empty list.

Usage example (conceptual):

```py
from autograder.builder.execution_helpers.AI_Executor import AiExecutor

ai = AiExecutor()
ai.send_submission_files({'main.py': 'print("hi")'})
ai.add_test('Functionality: prints greeting', 'Does the program print "hi"?')
ai.stop()  # sends request to AI and populates test_result references
```

When to use:
- Use `AiExecutor` when you want natural-language-based evaluation, rubric
  synthesis, or when tests are expressed as textual prompts evaluated by an
  LLM.

Limitations and notes:
- The AI is required to respond with strict JSON. The code enforces a schema
  but still prints and logs prompts and errors.
- Model names and endpoint details are embedded in the implementation, update
  them if you change providers/models.

## SandboxExecutor (sandbox_executor.py)

Purpose:
- Create, populate, run commands in, and clean up a Docker container used as a
  sandbox for executing student submissions. Useful for running tests that
  require executing code (scripts, servers) or calling student-provided APIs.

Key classes / functions:
- `SandboxExecutor` — main class:
  - `start()` (classmethod) — construct an instance using the global request
    context (`request_context.get_request()`) and its assignment `setup`
    configuration, then start a container.
  - `_start_container()` — internal method to create and run the Docker
    container, optionally with dynamic host port mapping.
  - `_place_submission_files()` — packages `request.submission_files` into a
    tar archive and copies them into `/home/user/` inside the container.
  - `run_command(command: str, in_background=False)` — execute commands
    inside the container, returns `(exit_code, stdout, stderr)` for
    foreground commands or `None` when `in_background=True`.
  - `get_mapped_port(container_port: int)` — read container network mapping to
    discover which host port Docker assigned for a forwarded container port.
  - `stop()` — remove the container and clean up resources.

Important configuration:
- The executor expects an assignment setup config containing at least
  `runtime_image` (Docker image to run). Example `setup.json` fields used by
  the executor:
  - `runtime_image` (required)
  - `container_port` (optional) — integer container port that will be
    dynamically mapped to a host port.

Usage example (conceptual):

```py
from autograder.builder.execution_helpers.sandbox_executor import SandboxExecutor

# Create and start from request context
sandbox = SandboxExecutor.start()

# Run tests inside container
exit_code, out, err = sandbox.run_command('python main.py')

# If the student runs a server on configured container_port, find the host port
host_port = sandbox.get_mapped_port(8000)

# Cleanup
sandbox.stop()
```

When to use:
- Use `SandboxExecutor` for any evaluation that requires running student code
  in isolation (unit tests that execute code, integration tests hitting a
  student-served HTTP endpoint, compilation, etc.).

Security and operational notes:
- The code sets `security_opt=['no-new-privileges']` and uses `user='root'` in
  the current implementation. Review and adjust user privileges according to
  your security posture — running containers as non-root is recommended when
  possible.
- The sandbox uses Docker, the runtime environment must have Docker available
  and the user running the autograder must have permissions to manage
  containers.
- Containers are started with `sleep infinity` then files are copied inside
  and commands executed. This pattern works well for deterministic test runs
  and for keeping the container available for multiple commands.

## Extending and testing

- To add more execution strategies, create a new helper module in the
  `execution_helpers` package and expose a consistent interface (start/stop,
  place files, run commands or evaluate). Keep a small adapter layer in the
  builder that can choose between `AiExecutor` and `SandboxExecutor`.
- Unit-test tips:
  - For `AiExecutor`, mock the `OpenAI` client and `get_secret` to return a
    deterministic response, assert that `mapback()` updates `TestResult`
    objects correctly.
  - For `SandboxExecutor`, run tests that mock `docker` to avoid requiring
    actual Docker in CI. For integration tests, use a real Docker host and
    a lightweight image (alpine, python:slim) and assert that files are
    copied and commands return expected outputs.

## Troubleshooting

- If AI responses fail to parse, first inspect printed `system_prompt` and
  `user_prompt` logged by `AiExecutor.stop()` to verify the request structure.
- If `SandboxExecutor` fails to start, ensure Docker is running, the image
  specified in `setup.json` exists locally or is pullable, and the current
  user has permission to run Docker commands.

## Links

- Execution helper sources:
  - `autograder/builder/execution_helpers/AI_Executor.py`
  - `autograder/builder/execution_helpers/sandbox_executor.py`


