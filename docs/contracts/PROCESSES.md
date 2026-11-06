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
| `timeout` | Process deadline in seconds (0–600; the control API also requires at most the pool's `running_timeout`). Evaluators declare the deadlines they use in `process_timeouts`; they make up the run's execution budget ([CAPABILITIES.md](CAPABILITIES.md#execution-budget)). |
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

A process during which the submission exhausted the sandbox's memory or
process limit has no result: the backend raises `SandboxExhausted` (see
[Who ended a run](#who-ended-a-run)).

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
| `SandboxExhausted` (control API `409 SANDBOX_EXHAUSTED`) | **A student outcome, not a `RuntimeError`.** The submission exhausted the sandbox's memory or process limit during this process or an earlier one. Every later operation of the session raises it. |
| `ProcessExecutionError` (control API `500 SANDBOX_ERROR`, remote `RemoteSandboxError`) | The backend could not run the process or read its result back, or the host stopped or removed the sandbox under it. |
| `SandboxInvalidatedError` (control API `409 SANDBOX_INVALIDATED`) | An earlier failure made the sandbox untrustworthy, for example termination that could not be confirmed. Every later operation fails until disposal. |
| `SandboxHandleNotFound` (`404 HANDLE_NOT_FOUND`), `SandboxHandleGone` (`410 HANDLE_CLOSED`/`HANDLE_EXPIRED`) | The remote handle is unknown, closed or expired ([SANDBOX.md](SANDBOX.md)). |
| `RemoteSandboxError` with code `TRANSPORT_ERROR` | The remote outcome is unknown. Process requests are never replayed. |
| `FileNotFoundError` (remote `ArtifactNotFound`, `404 ARTIFACT_NOT_FOUND`) | Artifact readback only: no regular file exists at the path. A symbolic link, or a path through one, is not a regular file. |
| `ArtifactReadError` (`500 ARTIFACT_READ_FAILED`) | The artifact exists but could not be read back. |
| `ArtifactTooLargeError`, a `ValueError` (`422 ARTIFACT_INVALID`) | The artifact is above the readback bound. |

The local and remote backends raise the same `SandboxExhausted`,
`SandboxInvalidatedError` and `ArtifactReadError`. All of these except
`SandboxExhausted`, `FileNotFoundError` and `ArtifactTooLargeError` are
`RuntimeError`s. Only a missing artifact is ever a student's missing file. The
host reads artifacts and outputs whatever permissions the submission gave them,
and never through a symbolic link the submission planted (readback runs as
`root`, so following one could read files the submission cannot, and runc and
gVisor treat such links differently). So `ArtifactReadError` is never caused by
the submission.

## Consumer policies

| Consumer | `exited` 0 | `exited` ≠ 0 / `timed_out` | `not_started` | `SandboxExhausted` | Other exception |
| --- | --- | --- | --- | --- | --- |
| Preparation (`setup_commands`, argv, empty stdin, 30 s) | continue | `PREPARATION_FAILED` (no score) | `PREPARATION_ERROR` (capability) | `PREPARATION_FAILED` | `PREPARATION_ERROR` |
| `expect_output`, `dont_fail`, `expect_file_artifact` (30 s) | assess | assessed zero (exit code or stderr / timeout report) | workspace program (`./a.out`, `bin/run`, `/app/...`): assessed zero; runtime command (`python3`, `/usr/bin/x`, `../usr/bin/x`): `PROCESS_START_FAILED` (no score) | assessed zero | `SANDBOX_ERROR` (no score) |
| `expect_file_artifact` readback | compare | missing file or symbolic link → assessed zero | | assessed zero | readback failure / unknown handle → `SANDBOX_ERROR` |
| Deliberate execution (8 s per case, 16 KiB per stream) | `success` | `runtime_error` / `timeout` (ends the batch) | 503 `EXECUTION_UNAVAILABLE` | `runtime_error`, exit code 137 (ends the batch) | 503 |

The workspace belongs to the submission: a program in it that is missing or not
executable (deleted, never built, `chmod -x`) is the submission's result. A
path is in the workspace when it resolves under `/app` from the workspace.
A runtime command comes from the host's image, so when it cannot start the
host lacks a capability.

This keeps the outcome rule intact: assessed failures can score zero, and
required infrastructure failures cannot.

## Deadlines and termination

`timeout` bounds the process itself: wall-clock time from the start of the exec
to exit, measured by the host that runs it. Staging stdin and reading output
back are separate operations, each bounded to 60 s; when one exceeds its bound,
the sandbox is invalidated. The remote client allows `timeout` plus 15 s for
the whole HTTP exchange. Deliberate execution also applies its 45 s response
deadline.

When the deadline passes, the local backend kills every process of the
submission. It waits until none is left, not even a zombie the container's init
has yet to reap (a zombie still holds a pid), and only then returns
`timed_out`. The same sweep
runs after every process, so background processes never outlive their run or
reach the next criterion. If termination cannot be confirmed, the sandbox is
invalidated and every later operation fails. A real-container test runs a
program that forks a background writer and then blocks. It shows that the
writer is gone and its file has stopped growing before the next criterion runs.

## Who ended a run

The submission's processes run as the unprivileged `sandbox` user. The
container's PID 1 (Docker's init) and every control exec that can run beside
them (the termination sweep, output and artifact readback) run as `root`, so
the submission cannot signal them. Its processes are also the kernel's first
choice when the container's memory runs out, so control execs are never
starved.

A submission at its process limit leaves no pid for anything else, and the
images' shell (busybox ash) aborts a script whose fork fails. So the sweep, its
wait (a deadline read from `/proc/uptime`, never `sleep`) and the cgroup
counters use shell builtins only, and the counters are reported before anything
that forks. The report is the collector's stdout alone: control execs that
report on stdout do not attach stderr. Docker forwards an exec's two streams
through independent copies, so in a combined stream a refused fork during the
later readback (ash's `can't fork` on stderr) could arrive ahead of the report
it follows. Under runc a full pids cgroup can also refuse to start the
collector exec itself. Nothing ran then, so the host starts it again (up to 5
times). If it never starts, Docker's `pids_stats` for the running container
decides (below). See
[SANDBOX.md](SANDBOX.md#one-owner-from-acquisition-to-confirmed-disposal) for the profile.

Assessed and infrastructure failures are decided from host-side evidence,
never from an exit code alone:

| Evidence | Meaning | Result |
| --- | --- | --- |
| The sweep runs; the container's cgroup counts its memory limit reached (`memory.events oom`) or a refused fork (`pids.events max`) (runc) | The submission exhausted memory or processes | `SandboxExhausted` |
| The collector exec cannot start and Docker reports the running container's `pids_stats.current` at its limit (runc) | The submission left no pid for control | `SandboxExhausted` |
| A control exec fails; Docker reports the container stopped by itself: `OOMKilled`, or the runtime exited without a signal (gVisor's Sentry cannot continue at the pids limit) | The submission exhausted the sandbox | `SandboxExhausted` |
| The pool disposed the sandbox (its lifetime passed, shutdown) | The host ended it | `ProcessExecutionError` |
| The sandbox's own lifetime passed before the run was read back (checked first, so a run it ended is never a result) | The host's limit ended it | `ProcessExecutionError` |
| Docker no longer has the container, or a signal stopped PID 1 (`docker rm -f`, `kill`, `stop`) | The host ended it | `ProcessExecutionError` |
| A control exec fails and the container is still running below its pids limit | Infrastructure (daemon) failure | `ProcessExecutionError` |
| None of the above; exit code 137 | The program's own exit (`exit(137)`, or a SIGKILL it sent itself) | `exited` 137 |

A host or operator that stops or removes a sandbox under a correct program
therefore never costs the student points: the grade fails with retryable
`SANDBOX_ERROR`.

**Exhaustion ends the sandbox.** Under gVisor the whole container stops; under
runc the kernel kills a process and the container survives. To give one
deterministic result under both runtimes, the sandbox is spent either way: the
process that reached the limit and every later operation in the session raise
`SandboxExhausted`, which evaluators assess as zero with the same report. The
grade still completes. Its output is not reported, because gVisor loses it.

The runc evidence requires cgroup v2 (`/sys/fs/cgroup/memory.events` and
`pids.events` inside the container). It counts the container's own memory limit
(`oom`), not OOM kills (`oom_kill`), because a host-wide OOM kill of a
container process also counts as an `oom_kill` and is not the submission's
doing; such a host kill ends the run as an ordinary exit 137.

Known limitations of the evidence:

- A host-wide OOM kill of a gVisor Sentry, and any other Sentry crash that
  stops the container without a signal, look like the submission exhausting
  the sandbox (assessed zero). Size hosts so that container limits, not host
  memory, are what bind.
- Any refused fork counts as exhaustion, even when the program handled `EAGAIN`
  and printed the right answer: the limit is part of the assignment's sandbox.

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
| A container stopped under a process kept the process's exit code (`_stopped_result`): a reaper or `docker kill` turned a correct run into a zero | Host-ended containers raise `ProcessExecutionError` (`SANDBOX_ERROR`); only host evidence of exhaustion is the submission's (`SandboxExhausted`) |
| PID 1 and the collector ran as `sandbox`: a submission could kill them and turn a bad grade into a retryable `SANDBOX_ERROR` | PID 1 and control execs run as `root`; the submission cannot signal them |
| A missing or non-executable `./a.out` was `PROCESS_START_FAILED` | Assessed zero (only a runtime command that cannot start is a capability failure) |
| An artifact the submission made unreadable was `ARTIFACT_READ_FAILED` → `SANDBOX_ERROR` | Read and graded |
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
