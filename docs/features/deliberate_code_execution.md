# Deliberate execution API

`POST /api/v1/execute` runs a submitted program for pre-submission testing. It
does not create a grading submission or score. The caller must be a trusted host
using `Authorization: Bearer <AUTOGRADER_INTEGRATION_TOKEN>`. The host must
authorize its own users and resource access before calling it. The request is
synchronous and is not durably accepted. The endpoint and grading both acquire
from the same sandbox manager and language pool, so its `scale_limit` bounds active containers
for both paths. Pool exhaustion is a service failure, not a student result.

## Request and stdin

```json
{
  "language": "python",
  "submission_files": [
    {"filename": "main.py", "content": "name = input()\nprint('Hello, ' + name)"}
  ],
  "program_command": "python main.py",
  "test_cases": [["Alice"], ["Bob"]],
  "assets": []
}
```

Save this JSON as `execute.json` and send it with
`curl -H "Authorization: Bearer $AUTOGRADER_INTEGRATION_TOKEN" -H "Content-Type: application/json" --data-binary @execute.json http://localhost:8000/api/v1/execute`.

`test_cases` is an optional, nonempty array of stdin cases. Each case is an
array of **lines** joined with newline and delivered to a fresh process in the
same sandbox workspace. Omit `test_cases` for one run with empty stdin. These
strings are stdin, never command arguments. A process can leave files in the
workspace for a later case; the sandbox is destroyed after the request. The
command is parsed into an executable and arguments, without an implicit shell.
Use an explicit `sh -c '...'` command for compilation chains or shell syntax.
Invalid quoting and unknown fields, including the old misleading `inputs`
field, receive 422.

`assets` is an optional list of `{source, target, read_only}` references. It
is for a trusted host to forward assignment assets from its own authorization
checks. `source` is a normalized relative provider key; `target` is a
normalized path under `/tmp`. The service resolves and injects these before
the first case. This does not make arbitrary callers trusted.

## Process response

```json
{
  "results": [
    {
      "category": "success",
      "stdout": "Hello, Alice\n",
      "stderr": "",
      "exit_code": 0,
      "execution_time": 0.01,
      "output": "Hello, Alice\n",
      "error_message": null,
      "truncated": false
    },
    {
      "category": "success",
      "stdout": "Hello, Bob\n",
      "stderr": "",
      "exit_code": 0,
      "execution_time": 0.01,
      "output": "Hello, Bob\n",
      "error_message": null,
      "truncated": false
    }
  ],
  "stopped_early": false
}
```

`results` follows request order. `success`, `runtime_error`,
`compilation_error`, and `timeout` are process outcomes (HTTP 200).
A timed-out process ends the batch, and `stopped_early: true` means the results
are a prefix of the requested cases. `output` is a display field: nonempty
stdout then stderr joined by a newline. Clients should use `stdout`,
`stderr`, and `exit_code` when they need the exact process outcome.
Each stream is capped at 16 KiB UTF-8 on the wire; `truncated` indicates a
cut. `execution_time` is seconds.

## Limits and lifecycle

| Limit | Value |
| --- | ---: |
| Files | 20, 64 KiB each, 256 KiB total UTF-8 content |
| Asset references | 5; resolved content 256 KiB total |
| Stdin cases | 1–4, 16 KiB per case |
| Process time | 8 seconds per case |
| HTTP response deadline | 45 seconds |
| Response output | 16 KiB per stream per case |

The host acquires one sandbox for the request, prepares files and assets, then
runs cases sequentially. Acquisition, preparation, execution, and release stay
in one worker. When the HTTP request is cancelled or reaches 45 seconds, the
caller receives no result (or 504 for a connected caller); the worker continues
to completion and releases or destroys the sandbox. A timed-out process's
sandbox is destroyed. Cleanup failure is logged and never replaces a known
process result. This is a bounded *response* deadline, not a hard stop for a
blocked Docker call or asset provider. No job ID or later status query exists.

| Condition | HTTP status | Machine-readable representation |
| --- | ---: | --- |
| Invalid input or limit | 422 | `detail[]` with path, code, message |
| Missing/invalid token | 401 | authentication detail |
| Student runtime/compile error or process timeout | 200 | `results[].category`, stdout/stderr/exit_code |
| Pool unavailable/full, asset or sandbox failure | 503 | `detail.code=EXECUTION_UNAVAILABLE` |
| Response deadline | 504 | `detail.code=EXECUTION_DEADLINE_EXCEEDED` |
| Caller disconnect | no response | worker completes cleanup; no persisted result |

## Client integration

Send the integration Bearer token, a supported lower-case language, normalized
file and asset paths, and at most four stdin cases. Treat 422, 503, and 504 as
request or service failures. Treat `results[].category` as the student process
outcome. A caller that only displays output can use `output`; one that needs
precise process details should read `stdout`, `stderr`, `exit_code`,
`truncated`, and `stopped_early`.

The web adapter owns this execution lifecycle independently of the grading
criteria tree. Blocking sandbox operations run in a worker thread, leaving the
HTTP event loop available for other requests.
