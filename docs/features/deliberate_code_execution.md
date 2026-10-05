# Deliberate execution API

`POST /api/v1/execute` runs a submitted program for pre-submission testing. It
does not create a grading submission or score. The caller must be a trusted host
using `Authorization: Bearer <AUTOGRADER_INTEGRATION_TOKEN>`; Prisma must enforce
assignment and student access before calling it. The request is synchronous and
is not durably accepted. The endpoint and grading both acquire from the same
sandbox manager and language pool, so its `scale_limit` bounds active containers
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
are a prefix of the requested cases. `output` is the existing Prisma display
field: nonempty stdout then stderr joined by a newline. Prisma should prefer
`stdout`, `stderr`, and `exit_code` when it needs the exact process outcome.
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
blocked Docker call or asset provider: those lower-level deadlines belong to
#376/#377. No job ID or later status query exists.

| Condition | HTTP status | Machine-readable representation |
| --- | ---: | --- |
| Invalid input or limit | 422 | `detail[]` with path, code, message |
| Missing/invalid token | 401 | authentication detail |
| Student runtime/compile error or process timeout | 200 | `results[].category`, stdout/stderr/exit_code |
| Pool unavailable/full, asset or sandbox failure | 503 | `detail.code=EXECUTION_UNAVAILABLE` |
| Response deadline | 504 | `detail.code=EXECUTION_DEADLINE_EXCEEDED` |
| Caller disconnect | no response | worker completes cleanup; no persisted result |

## Prisma migration and cutover

The current `AutograderExecutionRequest` already sends `language`,
`submission_files`, `program_command`, `test_cases`, and `assets`; its
`AutograderExecutionResponse` reads `results[].output/category/error_message/
execution_time`. Those fields remain. The Prisma host must attach the
integration Bearer token, send normalized lower-case language and valid
asset paths, keep at most four cases, and handle 422/503/504 separately from
student results. It may add `stdout`, `stderr`, `exit_code`, `truncated`, and
`stopped_early` to its DTOs when needed. The
[contract test](../../tests/web/test_deliberate_execution_service.py) sends
Prisma's current request shape through the real HTTP endpoint and checks stdin,
result mapping, and cleanup. Configure the Prisma token and error mapping before
deploying this contract; no dual route or compatibility window is proposed.

This execution endpoint owns its own lifecycle in the web adapter. The grading
criteria tree remains for grading. #318 owns consistent authentication on the
other HTTP routes; #365/#366 own durable submission acceptance and retry.
This preserves #188's pre-submission capability and #296's asset injection.
The single worker keeps blocking sandbox I/O off the event loop, as requested
by #314; lower-level isolation and hard deadlines stay with #376/#377.
