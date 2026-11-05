"""One leased Docker sandbox: staging, the process contract, artifact readback.

Every process runs through :meth:`SandboxContainer.run_process` (see
``autograder.models.process``). Fixed shell scripts below receive every value
as a positional parameter; nothing supplied by a caller is ever interpolated
into shell text. The process itself is ``exec``-ed with its exact argument
vector, its stdin from a staged file and its outputs redirected to files, so
output is bounded when it is read back rather than buffered by Docker.

Who ended a run is decided from host-side evidence, never from an exit code
(see ``docs/contracts/PROCESSES.md``): the container's own limit counters, the
pool's disposal record and Docker's record of how the container stopped. A
submission that exhausts the sandbox raises :class:`SandboxExhausted`; a host
that stops or removes it raises :class:`ProcessExecutionError`.
"""
import base64
import os
import posixpath
import threading
import time
import uuid
from typing import Dict, List, Optional, TYPE_CHECKING

import requests
import docker
from docker.models.containers import Container

from autograder.models.language import Language
from autograder.models.process import (
    ProcessRequest, ProcessResult, ProcessStatus, SandboxExhausted, decode_output,
)
from sandbox_manager.docker_profile import CONTROL_USER
from sandbox_manager.errors import (
    ArtifactReadError, ArtifactTooLargeError, ProcessExecutionError, SandboxInvalidatedError,
)
from autograder.models.execution import ExtractedFile
from sandbox_manager.models.sandbox_models import HttpResponse, SandboxState

if TYPE_CHECKING:
    from autograder.models.dataclass.asset import ResolvedAsset
    from autograder.models.dataclass.submission import SubmissionFile

USER = "sandbox"                    # the submission's processes; control runs as CONTROL_USER
RUN_ROOT = "/tmp/.autograder-run"
WRITE_CHUNK_BYTES = 48 * 1024       # 64 KiB of base64: well below the kernel's per-argument limit
INLINE_STDIN_BYTES = 48 * 1024
CONTROL_TIMEOUT_SECONDS = 60        # staging, termination and readback execs
KILL_GRACE_SECONDS = 10             # wait for the killed process's exec to return
STOP_SETTLE_SECONDS = 10            # wait for Docker to record a container that stopped
COLLECT_ATTEMPTS = 5                # starts of the collector while the pids limit leaves no pid for it
PIDS_SAMPLES = 5                    # Docker stats samples taken when a control exec still failed
DEFAULT_ARTIFACT_BYTES = 1_048_576

# $1 run dir, $2 base64 stdin or "-" when staged; the rest is the exact argv.
# Runs as the submission's user. Its processes are the kernel's first choice
# when the container's memory runs out, so control execs are never starved.
RUNNER = r'''
d=$1; data=$2; shift 2
if [ "$data" != - ]; then
  mkdir -p "$d" && printf %s "$data" | base64 -d > "$d/in" || { printf 'autograder:staging-failed\n'; exit 125; }
fi
{ printf 1000 > /proc/self/oom_score_adj; } 2>/dev/null
command -v "$1" >/dev/null 2>&1 || { printf 'autograder:not-found\n'; exit 127; }
printf 'autograder:started\n'
exec "$@" < "$d/in" > "$d/out" 2> "$d/err"
'''

# Runs as root, which the submission cannot signal. Kills every non-root
# process (all of them are the submission's) and waits, up to a deadline read
# from /proc/uptime, until none is left, not even a zombie that PID 1 has yet to
# reap (a zombie still holds its pid). Until then it never forks: the sweep, the
# wait and the counters use shell builtins only, because a submission that used
# up the pids limit leaves no pid for a child and busybox ash aborts the script
# on a failed fork. Reports the cgroup's own count of memory-limit OOMs and
# refused forks (cgroup v2 under runc; gVisor has none, and its container stops
# instead) before anything that forks, then reads back at most $2 bytes of each
# output and removes the run dir.
COLLECT = r'''
d=$1; n=$2; me=$$
sweep() {
  live=0; dead=0
  for p in /proc/[0-9]*; do
    p=${p#/proc/}
    [ "$p" = "$me" ] && continue
    s=; u=
    while read -r k v _; do
      case $k in State:) s=$v ;; Uid:) u=$v; break ;; esac
    done 2>/dev/null < "/proc/$p/status"
    if [ -z "$u" ] || [ "$u" = 0 ]; then continue; fi
    if [ "$s" = Z ]; then dead=$((dead + 1)); continue; fi
    kill -9 "$p" 2>/dev/null
    live=$((live + 1))
  done
}
now() { read -r t _ < /proc/uptime; t=${t%%.*}; }
count() {
  c=0
  while read -r k v; do [ "$k" = "$2" ] && c=$v; done 2>/dev/null < "$1"
}
now; end=$((t + 6))
sweep
while [ $((live + dead)) -gt 0 ]; do
  now; [ "$t" -lt "$end" ] || break
  sweep
done
count /sys/fs/cgroup/memory.events oom; oom=$c
count /sys/fs/cgroup/pids.events max; forks=$c
printf 'survivors %s\nlimits %s %s\n' "$live" "$oom" "$forks"
for s in out err; do
  f="$d/$s"
  if [ -f "$f" ] && [ ! -L "$f" ] && [ "$(readlink -f "$f")" = "$f" ]; then
    printf '%s %s\n' "$s" "$(stat -c %s "$f")"
    head -c "$n" "$f" | base64 | tr -d '\n'
    printf '\n'
  else
    printf '%s -1\n\n' "$s"
  fi
done
rm -rf "$d"
'''

# $1 path, $2 "new" or "append", $3 base64 chunk.
WRITE = r'''
f=$1
mkdir -p "$(dirname "$f")" || exit 1
if [ "$2" = new ]; then : > "$f" || exit 1; fi
printf %s "$3" | base64 -d >> "$f"
'''

# $1 normalized absolute path, $2 byte limit + 1. Exit 3: no regular file at the
# path. Runs as root, so it never follows a symbolic link the submission planted
# (in the path or as the file): the path must name the file itself.
READ = r'''
set -o pipefail
f=$1
if [ ! -f "$f" ] || [ "$(readlink -f "$f")" != "$f" ]; then exit 3; fi
stat -c %s "$f" || exit 1
head -c "$2" "$f" | base64 | tr -d '\n'
'''


class _Call:
    """Run a blocking Docker call in a daemon thread so the caller can bound it."""

    def __init__(self, function):
        self.result = None
        self.error: Optional[BaseException] = None
        self._thread = threading.Thread(target=self._run, args=(function,), daemon=True)

    def _run(self, function):
        try:
            self.result = function()
        except BaseException as exc:  # pylint: disable=broad-exception-caught
            self.error = exc

    def start(self) -> "_Call":
        self._thread.start()
        return self

    def join(self, timeout: float) -> bool:
        """Wait up to ``timeout``; return whether the call finished."""
        self._thread.join(timeout)
        return not self._thread.is_alive()


class SandboxContainer:
    """Manages a Docker container used as a sandbox for code execution."""

    def __init__(self, language: Language, container_ref: Container, port: int = None):
        self.language = language
        self.container_ref = container_ref
        self.port = port
        self.state = SandboxState.IDLE
        self.created_at = time.monotonic()
        self.activated_at: Optional[float] = None
        # Pool bookkeeping, owned by the pool under its lock. A sandbox holds a
        # host budget slot from its acquisition until Docker confirms removal.
        self.holds_slot = False
        self.disposal_attempts = 0
        self.next_disposal_at = 0.0
        self.last_disposal_error: Optional[str] = None
        # Set when the sandbox can no longer be trusted; every later operation fails.
        self.invalidated: Optional[str] = None
        # Set when the submission exhausted a limit; every later operation raises SandboxExhausted.
        self.exhausted = False

    def activate(self, now: Optional[float] = None) -> None:
        """Hand the sandbox to one caller; it is disposed after this use."""
        self.state = SandboxState.ACTIVE
        self.activated_at = time.monotonic() if now is None else now

    @property
    def short_id(self) -> str:
        return (self.container_ref.id or "")[:12]

    # ----- integrity -----------------------------------------------------------------
    def _check_usable(self) -> None:
        if self.exhausted:
            raise SandboxExhausted("The submission exhausted the sandbox's memory or process limit")
        if self.invalidated is not None:
            raise SandboxInvalidatedError(f"The sandbox was invalidated: {self.invalidated}")

    def _invalidate(self, reason: str) -> None:
        if self.invalidated is None:
            self.invalidated = reason

    def _control(self, cmd: List[str], *, user: str = CONTROL_USER, workdir: str = "/") -> tuple:
        """A bounded internal exec. Failure to complete it invalidates the sandbox."""
        call = _Call(lambda: self.container_ref.exec_run(cmd=cmd, user=user, workdir=workdir, demux=False,
                                                         stdout=True, stderr=True, stdin=False)).start()
        if not call.join(CONTROL_TIMEOUT_SECONDS):
            self._invalidate("an internal sandbox operation did not complete")
            raise ProcessExecutionError("A sandbox operation did not complete in time")
        if call.error is not None:
            self._invalidate("an internal sandbox operation failed")
            raise ProcessExecutionError(f"A sandbox operation failed: {call.error}") from call.error
        return call.result.exit_code, call.result.output or b""

    # ----- staging -------------------------------------------------------------------
    @staticmethod
    def _normalize_relative_path(path: str) -> str:
        """Normalize user-provided relative paths and prevent traversal/absolute paths."""
        if not path:
            raise ValueError("Path cannot be empty")
        normalized = os.path.normpath(path).replace("\\", "/")
        if normalized in ("", ".", ".."):
            raise ValueError(f"Invalid path: {path}")
        if normalized.startswith("/") or normalized.startswith("../") or "/../" in f"/{normalized}":
            raise ValueError(f"Path must stay within working directory: {path}")
        return normalized

    @staticmethod
    def _normalize_tmp_path(path: str) -> str:
        """Normalize absolute asset paths and keep them constrained under /tmp."""
        normalized = os.path.normpath(path).replace("\\", "/")
        if not normalized.startswith("/tmp/"):
            raise ValueError(f"Asset target must be under /tmp: {path}")
        return normalized

    def _write_file(self, path: str, content: bytes, *, user: str) -> None:
        """Write exact bytes in bounded chunks (no size limit from argument length)."""
        chunks = [content[i:i + WRITE_CHUNK_BYTES] for i in range(0, len(content), WRITE_CHUNK_BYTES)] or [b""]
        for index, chunk in enumerate(chunks):
            code, output = self._control(["/bin/sh", "-c", WRITE, "autograder-write", path,
                                          "new" if index == 0 else "append",
                                          base64.b64encode(chunk).decode("ascii")], user=user)
            if code != 0:
                raise RuntimeError(f"Failed to write {path}: {output.decode('utf-8', 'replace')}")

    def prepare_workdir(self, submission_files: Dict[str, 'SubmissionFile']) -> None:
        """Copy submission files into ``/app``, creating parent directories."""
        self._check_usable()
        try:
            for submission_file in (submission_files or {}).values():
                path = self._normalize_relative_path(submission_file.filename)
                self._write_file(f"/app/{path}", submission_file.content.encode("utf-8"), user=USER)
        except Exception as e:
            raise RuntimeError(f"Error preparing workdir: {str(e)}") from e

    def inject_assets(self, resolved_assets: List['ResolvedAsset']) -> None:
        """Write resolved fixtures under ``/tmp`` as root, read-only when requested."""
        self._check_usable()
        for asset in resolved_assets or []:
            target_path = asset.target
            if not target_path.startswith('/tmp/'):
                target_path = os.path.join('/tmp', target_path.lstrip('/'))
            target_path = self._normalize_tmp_path(target_path)
            parent_dir = os.path.dirname(target_path)
            code, output = self._control(["mkdir", "-p", parent_dir], user="root")
            if code == 0:
                code, output = self._control(["chmod", "755", parent_dir], user="root")
            if code != 0:
                raise RuntimeError(f"Failed to create asset directory {parent_dir}: {output.decode('utf-8', 'replace')}")
            self._write_file(target_path, asset.content, user="root")
            code, output = self._control(["chmod", "444" if asset.read_only else "644", target_path], user="root")
            if code != 0:
                raise RuntimeError(f"Failed to set permissions on {target_path}: {output.decode('utf-8', 'replace')}")

    # ----- the process contract ------------------------------------------------------
    def run_process(self, request: ProcessRequest) -> ProcessResult:
        """Run one process to completion or its deadline; see ``autograder.models.process``.

        On timeout every process of the sandbox user is killed and confirmed gone
        before this returns, so nothing from this run reaches the next one; the
        same sweep also ends background processes left by a run that exited.
        If termination cannot be confirmed the sandbox is invalidated.

        Raises :class:`SandboxExhausted` when the submission reached the
        container's memory or process limit during this run (or an earlier
        one), and :class:`ProcessExecutionError` when the host stopped or
        removed the container or could not complete an operation.
        """
        self._check_usable()
        run_dir = f"{RUN_ROOT}-{uuid.uuid4().hex}"
        if len(request.stdin) > INLINE_STDIN_BYTES:
            self._write_file(f"{run_dir}/in", request.stdin, user=USER)
            data = "-"
        else:
            data = base64.b64encode(request.stdin).decode("ascii")
        command = ["/bin/sh", "-c", RUNNER, "autograder-run", run_dir, data, *request.program]
        started = time.monotonic()
        call = _Call(lambda: self.container_ref.exec_run(
            cmd=command, workdir=request.cwd, user=USER, demux=False,
            stdout=True, stderr=True, stdin=False)).start()
        finished = call.join(request.timeout)
        duration = time.monotonic() - started
        # Kill whatever remains (the timed-out process, or orphans) and read outputs back.
        try:
            survivors, outputs = self._collect(run_dir, request.max_output_bytes)
        except ProcessExecutionError:
            self._attribute_failed_control()
            raise
        if not finished and not call.join(KILL_GRACE_SECONDS):
            self._invalidate("a timed-out process did not terminate")
            raise ProcessExecutionError("A timed-out process could not be confirmed terminated")
        if survivors:
            self._invalidate("processes survived termination")
            raise ProcessExecutionError(f"{survivors} process(es) survived termination")
        if call.error is not None:
            self._invalidate("process execution failed")
            raise ProcessExecutionError(f"Process execution failed: {call.error}") from call.error
        marker = call.result.output or b""
        if b"autograder:not-found" in marker:
            return ProcessResult(ProcessStatus.NOT_STARTED, duration=duration, missing_executable=request.program[0])
        (stdout, stdout_cut), (stderr, stderr_cut) = outputs
        if not finished:
            return ProcessResult(ProcessStatus.TIMED_OUT, None, decode_output(stdout, stdout_cut),
                                 decode_output(stderr, stderr_cut), stdout_cut, stderr_cut, request.timeout)
        if b"autograder:started" not in marker or call.result.exit_code is None:
            raise ProcessExecutionError("The process could not be started in the sandbox")
        return ProcessResult(ProcessStatus.EXITED, call.result.exit_code, decode_output(stdout, stdout_cut),
                             decode_output(stderr, stderr_cut), stdout_cut, stderr_cut, duration)

    def _attribute_failed_control(self) -> None:
        """Decide from host-side evidence who ended a sandbox whose control exec failed.

        The pool disposed it (running timeout, shutdown), Docker no longer has it,
        or a signal stopped its PID 1 (``docker kill``/``stop``): the host ended
        it, an infrastructure failure. A running container whose process count
        Docker reports at the pids limit had no pid left for the control exec
        (runc): the submission exhausted it. Otherwise Docker reports that the
        container stopped by itself: the kernel's OOM killer stopped it, or the
        runtime itself (gVisor's Sentry) could not continue within the
        container's limits. The submission, which cannot signal PID 1, exhausted
        it. A container that is still running had a control operation fail.
        """
        if self.state in (SandboxState.CLOSING, SandboxState.QUARANTINED, SandboxState.DISPOSED):
            self._invalidate("the host disposed the sandbox")
            return
        state: dict = {}
        try:
            # runc could not start the control exec when the submission left it no pid.
            at_pids_limit = bool(self._state().get("Running")) and self._pids_at_limit()
            if not at_pids_limit:
                try:
                    self.container_ref.wait(timeout=STOP_SETTLE_SECONDS)
                except docker.errors.NotFound:
                    raise
                except Exception:  # pylint: disable=broad-exception-caught
                    pass  # still running, or no answer: Docker's record below decides
                state = self._state()
        except docker.errors.NotFound:
            self._invalidate("the sandbox was removed")
            return
        except Exception:  # pylint: disable=broad-exception-caught
            self._invalidate("an internal sandbox operation failed")  # no answer from Docker
            return
        if at_pids_limit:
            self._exhaust()
        if state.get("Running", True):
            self._invalidate("an internal sandbox operation failed")
            return
        if not state.get("OOMKilled") and (state.get("ExitCode") or 0) > 128:
            self._invalidate("the host stopped the sandbox")
            return
        self._exhaust()

    def _state(self) -> dict:
        self.container_ref.reload()
        return self.container_ref.attrs.get("State") or {}

    def _pids_at_limit(self) -> bool:
        """Whether Docker reports the running container's process count at its pids limit.

        Only the submission's processes can fill it (control holds at most a few
        pids beside PID 1). A fork bomb's count moves, so a few samples are taken.
        """
        for _ in range(PIDS_SAMPLES):
            try:
                pids = self.container_ref.stats(stream=False, one_shot=True).get("pids_stats") or {}
            except Exception:  # pylint: disable=broad-exception-caught
                return False
            if pids.get("limit") and pids.get("current", 0) >= pids["limit"]:
                return True
        return False

    def _exhaust(self) -> None:
        self.exhausted = True
        raise SandboxExhausted("The submission exhausted the sandbox's memory or process limit")

    def _collect(self, run_dir: str, limit: int):
        for _ in range(COLLECT_ATTEMPTS):
            code, output = self._control(["/bin/sh", "-c", COLLECT, "autograder-collect", run_dir, str(limit)])
            if output.startswith(b"survivors "):
                break
            # The collector never reported: under runc, a submission at its pids limit
            # leaves no pid to start an exec. It removes nothing before it reports, so
            # starting it again is safe.
        lines = output.decode("ascii", "replace").split("\n")
        try:
            if len(lines) < 2 or not lines[0].startswith("survivors ") or not lines[1].startswith("limits "):
                raise ValueError("unexpected collector output")
            survivors = int(lines[0].split()[1])
            limit_ooms, refused_forks = (int(value) for value in lines[1].split()[1:])
        except (ValueError, IndexError) as exc:
            self._invalidate("process output readback failed")
            raise ProcessExecutionError("Process output could not be read back") from exc
        if limit_ooms or refused_forks:
            # The container's cgroup recorded the limit; outputs may be unreadable now.
            self._exhaust()
        try:
            if code != 0:
                raise ValueError("unexpected collector output")
            streams = []
            for index, name in ((2, "out"), (4, "err")):
                label, size = lines[index].split()
                if label != name:
                    raise ValueError("unexpected collector output")
                data = base64.b64decode(lines[index + 1]) if int(size) >= 0 else b""
                streams.append((data, int(size) > len(data)))
        except (ValueError, IndexError) as exc:
            self._invalidate("process output readback failed")
            raise ProcessExecutionError("Process output could not be read back") from exc
        return survivors, streams

    # ----- artifacts -----------------------------------------------------------------
    def extract_file(self, path: str, max_bytes: int = DEFAULT_ARTIFACT_BYTES) -> ExtractedFile:
        """Read back at most ``max_bytes`` of a regular file.

        Raises ``FileNotFoundError`` only when no regular file exists at ``path``
        (a symbolic link, or a path through one, is not one),
        ``ArtifactTooLargeError`` above ``max_bytes`` and ``ArtifactReadError``
        when an existing file could not be read; sandbox failures stay distinct.
        """
        if not path.startswith("/"):
            raise ValueError(f"Path must be absolute inside container: {path}")
        self._check_usable()
        target = "/" + posixpath.normpath(path).lstrip("/")
        try:
            code, output = self._control(["/bin/sh", "-c", READ, "autograder-read", target, str(max_bytes + 1)])
        except ProcessExecutionError as exc:
            raise ArtifactReadError(f"Artifact readback failed: {exc}") from exc
        if code == 3:
            raise FileNotFoundError(f"File not found in container: {path}")
        lines = output.decode("ascii", "replace").split("\n")
        try:
            if code != 0:
                raise ValueError(f"exit code {code}")
            size = int(lines[0])
            content_bytes = base64.b64decode(lines[1] if len(lines) > 1 else "")
        except (ValueError, IndexError) as exc:
            raise ArtifactReadError(f"Artifact readback failed: {exc}") from exc
        if len(content_bytes) < min(size, max_bytes + 1):
            raise ArtifactReadError("Artifact readback returned fewer bytes than the file holds")
        if size > max_bytes or len(content_bytes) > max_bytes:
            raise ArtifactTooLargeError(
                f"File exceeds maximum size: {max(size, len(content_bytes))} bytes > {max_bytes} bytes")
        try:
            content_text, encoding = content_bytes.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            content_text, encoding = content_bytes.decode("latin-1"), "latin-1"
        return ExtractedFile(path=path, content_bytes=content_bytes, size=len(content_bytes),
                             content_text=content_text, encoding=encoding)

    def make_request(self, method: str, endpoint: str, **kwargs) -> HttpResponse:
        """Make an HTTP request to a containerized web application."""
        if self.port is None:
            raise ValueError("Container port not configured for HTTP requests")

        url = f"http://localhost:{self.port}{endpoint}"
        method = method.upper()
        timeout = kwargs.pop('timeout', 5)
        method_map = {'GET': requests.get, 'POST': requests.post, 'PUT': requests.put,
                      'DELETE': requests.delete, 'PATCH': requests.patch}
        if method not in method_map:
            raise ValueError(f"Unsupported HTTP method: {method}")
        try:
            return HttpResponse(method_map[method](url, timeout=timeout, **kwargs))
        except requests.RequestException as e:
            raise requests.RequestException(f"HTTP {method} request to {url} failed: {str(e)}") from e

    def __repr__(self):
        name = self.container_ref.name or "unnamed"
        return f"<SandboxContainer lang={self.language.value} state={self.state.value} name={name} id={self.container_ref.id[:12]}>"
