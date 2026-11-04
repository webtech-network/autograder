# Process contract

Every process the system runs in a sandbox uses one operation:

```python
result = session.run_process(ProcessRequest(...))   # autograder/models/process.py
```

Preparation setup commands, the I/O and artifact evaluators, and deliberate
execution all call it. They differ only in how they grade or report the result.
The local Docker backend (`SandboxContainer`, also used by GitHub Actions) and the
remote backend (`RemoteSandboxContainer` → `POST /sandboxes/{id}/process`)
implement the same contract and agree byte for byte.

## Request

| Field | Meaning |
| --- | --- |
| `argv` | The exact argument vector. No shell runs, so `&&`, `\|`, `>`, `;`, `$HOME` and `*` are ordinary arguments. |
| `shell` | Instead of `argv`: an explicit trusted script, run as `/bin/sh -c <script>`. |
| `stdin` | The exact bytes on standard input (at most 1 MiB). `b""` means immediate EOF. |
| `cwd` | A normalized absolute working directory, `/app` by default. |
| `timeout` | Process deadline in seconds (0–600; the control API also requires at most the pool's `running_timeout`). |
| `max_output_bytes` | Bound for each of stdout and stderr (1 B–8 MiB, 1 MiB by default). |

A request has exactly one of `argv` or `shell`. `ProcessRequest.command(text)`
builds `argv` with POSIX splitting: quotes group words, and a backslash escapes
the next character. Malformed quoting (`python3 'main.py`) is a `ValueError`.
The process is never retried through a shell. Definitions are checked when they
are compiled: malformed quoting in an I/O `program_command` fails with
`INVALID_COMMAND`, and in a preparation `setup_commands[].command` with a
validation error. A standalone unquoted shell operator (`&&`, `|`, `;`, `>`,
`2>&1`, ...) in either fails with `SHELL_OPERATOR` (`shell_operator(text)`), since
it would silently become an argument. Compile in setup commands, one step each;
write an explicit shell only for a real pipeline, for example
`sh -c 'python3 gen.py | sort'`. Quoted operators stay literal arguments.

`lines_to_stdin(lines)` turns line-oriented inputs into exact bytes. Each line
is followed by `\n`, so `[]` gives no bytes at all and `[""]` gives one empty
line. Nothing is interpreted: `-n`, `-e` and backslashes reach the program
unchanged.

## Result

A `ProcessResult` describes a process that the backend ran or tried to start:

| `status` | Meaning | `exit_code` |
| --- | --- | --- |
| `exited` | The process ran and returned. | The returned code, whatever it is. |
| `timed_out` | The deadline passed. The backend killed the process and every process it started, and confirmed they were gone. | `None` |
| `not_started` | The executable (`argv[0]`) was not found or is not executable. `missing_executable` names it. | `None` |

`stdout` and `stderr` are decoded UTF-8 (invalid bytes are replaced) after
bounding. `stdout_truncated`/`stderr_truncated` report a cut, and a cut never
splits a character. `duration` is in seconds.

Classification uses only the exit status, never the wording of stderr. Exit 0
is `success`; any other returned code is `runtime_error`, even when stderr is
empty. A `timed_out` process is `timeout`. Code 137 stays a returned exit
(`runtime_error`). It may come from `exit(137)` or from a SIGKILL such as the
memory limit, so it is never reported as a timeout without timeout evidence.
There is no `compilation_error` or `system_error` result: a failed compilation
is a failed setup command (`PREPARATION_FAILED`), and infrastructure failures
are exceptions.

## Failures are exceptions, never results

| Exception | When |
| --- | --- |
| `ProcessExecutionError` (control API `500 SANDBOX_ERROR`, remote `RemoteSandboxError`) | The backend could not run the process or read its result back. |
| `SandboxInvalidatedError` (control API `409 SANDBOX_INVALIDATED`) | An earlier failure made the sandbox untrustworthy, for example termination that could not be confirmed. Every later operation fails until disposal. |
| `SandboxHandleNotFound` (`404 HANDLE_NOT_FOUND`), `SandboxHandleGone` (`410 HANDLE_CLOSED`/`HANDLE_EXPIRED`) | The remote handle is unknown, closed or expired ([SANDBOX.md](SANDBOX.md)). |
| `RemoteSandboxError` with code `TRANSPORT_ERROR` | The remote outcome is unknown. Process requests are never replayed. |
| `FileNotFoundError` (remote `ArtifactNotFound`, `404 ARTIFACT_NOT_FOUND`) | Artifact readback only: no regular file exists at the path. |
| `ArtifactReadError` (`500 ARTIFACT_READ_FAILED`) | The artifact exists but could not be read back. |
| `ArtifactTooLargeError`, a `ValueError` (`422 ARTIFACT_INVALID`) | The artifact is above the readback bound. |

The local and remote backends raise the same `SandboxInvalidatedError` and
`ArtifactReadError`. All of these except `FileNotFoundError` and
`ArtifactTooLargeError` are `RuntimeError`s. Only a missing artifact is ever a
student's missing file.

## Consumer policies

| Consumer | `exited` 0 | `exited` ≠ 0 / `timed_out` | `not_started` | Exception |
| --- | --- | --- | --- | --- |
| Preparation (`setup_commands`, argv, empty stdin, 30 s) | continue | `PREPARATION_FAILED` (no score) | `PREPARATION_ERROR` (capability) | `PREPARATION_ERROR` |
| `expect_output`, `dont_fail`, `expect_file_artifact` (30 s) | assess | assessed zero (exit code or stderr / timeout report) | `PROCESS_START_FAILED` (no score) | `SANDBOX_ERROR` (no score) |
| `expect_file_artifact` readback | compare | missing file → assessed zero | | readback failure / unknown handle → `SANDBOX_ERROR` |
| Deliberate execution (8 s per case, 16 KiB per stream) | `success` | `runtime_error` / `timeout` (ends the batch) | 503 `EXECUTION_UNAVAILABLE` | 503 |

This keeps the outcome rule intact: assessed failures can score zero, and
required infrastructure failures cannot.

## Deadlines and termination

`timeout` bounds the process itself: wall-clock time from the start of the exec
to exit, measured by the host that runs it. Staging stdin and reading output
back are separate operations, each bounded to 60 s; when one exceeds its bound,
the sandbox is invalidated. The remote client allows `timeout` plus 15 s for
the whole HTTP exchange. Deliberate execution also applies its 45 s response
deadline.

When the deadline passes, the local backend kills every process of the sandbox
user except the container's keep-alive PID 1. It waits until none is left
(zombies are already dead), and only then returns `timed_out`. The same sweep
runs after every process, so background processes never outlive their run or
reach the next criterion. If termination cannot be confirmed, the sandbox is
invalidated and every later operation fails. If a program takes the whole
container down (for example by exhausting the memory limit, when the host's
OOM handling stops the container rather than only the process), its returned
exit code is still its result, its output is lost, and the sandbox is
invalidated: a later criterion fails with `SANDBOX_ERROR` instead of being
scored. Whether memory exhaustion stops the container is host dependent; the
tests accept either outcome but never a fabricated result. A real-container test runs a
program that forks a background writer and then blocks. It shows that the
writer is gone and its file has stopped growing before the next criterion runs.

## Output and readback bounds

The program's stdout and stderr go to files inside the sandbox, never to a
Docker buffer. They are read back with at most `max_output_bytes` each, so host
memory is bounded no matter how much the program writes. The container's file
size limit, 10 MB, bounds the files themselves. Artifacts are read with
`max_bytes + 1` and checked against the reported size. The default bound and
the control API's limit are 1 MiB. Evaluators assess output up to this bound.
The terminal outcome keeps only a bounded excerpt of any report that quotes it
([OUTCOMES.md](OUTCOMES.md#size-bounds)).

## Migration from `run_command`/`run_commands`

| Before | Now |
| --- | --- |
| `run_command(cmd)` split with `shlex`, but malformed quoting silently ran `/bin/sh -c cmd` | `ProcessRequest.command(cmd)` raises. Compilation rejects such definitions (`INVALID_COMMAND`). |
| `run_commands(inputs, program_command=...)` ran `echo '<joined>' \| cmd` | Exact stdin: `lines_to_stdin(inputs)` |
| `inputs: []` sent one newline (`echo ''`) | Empty stdin (EOF). Use `[""]` to send one empty line. |
| An input `-n` (or `-e`, `-E`) could be taken as an `echo` option and lost | Sent literally, as `-n\n` |
| Exit ≠ 0 with unrecognised stderr was `SYSTEM_ERROR` → `SANDBOX_ERROR`, a failed grade | Assessed zero (`runtime_error`) |
| Exit 137 was `TIMEOUT` | `runtime_error` with exit code 137 |
| `compilation_error` from stderr keywords (`error:`, `gcc`, ...) | `runtime_error`. Compile in `setup_commands` to get `PREPARATION_FAILED`. |
| Unbounded `exec_run` output buffering | Bounded per stream at the host |
| A timeout stopped waiting but left the process running | The process and its children are killed before the call returns |
| Control API `POST /run`, `POST /run-batch` | `POST /process` |

Definitions that depended on the old behaviour need these changes:

* An `expect_output` test with `inputs: []` whose program calls `input()` now
  gets EOF. Add `[""]` if the program must read an empty line.
* A `program_command` or setup command that relied on shell syntax never ran
  through a shell before (it was split into arguments) unless its quoting was
  malformed. Write `sh -c '...'` explicitly. Malformed quoting and standalone
  shell operators are now rejected when the definition is compiled or loaded.
* Assignments that expected `compilation_error` from an I/O run should compile
  in `preparation.languages.<language>.setup_commands`.
