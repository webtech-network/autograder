"""One leased Docker sandbox: staging, the process contract, artifact readback.

Every process runs through :meth:`SandboxContainer.run_process` (see
``autograder.models.process``). Fixed shell scripts below receive every value
as a positional parameter; nothing supplied by a caller is ever interpolated
into shell text. The process itself is ``exec``-ed with its exact argument
vector, its stdin from a staged file and its outputs redirected to files, so
output is bounded when it is read back rather than buffered by Docker.
"""
import base64
import os
import threading
import time
import uuid
from typing import Dict, List, Optional, TYPE_CHECKING

import requests
from docker.models.containers import Container

from autograder.models.language import Language
from autograder.models.process import ProcessRequest, ProcessResult, ProcessStatus, decode_output
from sandbox_manager.errors import (
    ArtifactReadError, ArtifactTooLargeError, ProcessExecutionError, SandboxInvalidatedError,
)
from sandbox_manager.models.sandbox_models import ExtractedFile, HttpResponse, SandboxState

if TYPE_CHECKING:
    from autograder.models.dataclass.asset import ResolvedAsset
    from autograder.models.dataclass.submission import SubmissionFile

USER = "sandbox"
RUN_ROOT = "/tmp/.autograder-run"
WRITE_CHUNK_BYTES = 48 * 1024       # 64 KiB of base64: well below the kernel's per-argument limit
INLINE_STDIN_BYTES = 48 * 1024
CONTROL_TIMEOUT_SECONDS = 60        # staging, termination and readback execs
KILL_GRACE_SECONDS = 10             # wait for the killed process's exec to return
DEFAULT_ARTIFACT_BYTES = 1_048_576

# $1 run dir, $2 base64 stdin or "-" when staged; the rest is the exact argv.
RUNNER = r'''
d=$1; data=$2; shift 2
if [ "$data" != - ]; then
  mkdir -p "$d" && printf %s "$data" | base64 -d > "$d/in" || { printf 'autograder:staging-failed\n'; exit 125; }
fi
command -v "$1" >/dev/null 2>&1 || { printf 'autograder:not-found\n'; exit 127; }
printf 'autograder:started\n'
exec "$@" < "$d/in" > "$d/out" 2> "$d/err"
'''

# Terminates every process of the sandbox user except PID 1 (the container's
# keep-alive) and itself, waits until none is left (zombies are already dead),
# then reads back at most $2 bytes of each output and removes the run dir.
COLLECT = r'''
d=$1; n=$2; me=$$
sweep() {
  left=0
  for p in /proc/[0-9]*; do
    p=${p#/proc/}
    if [ "$p" = 1 ] || [ "$p" = "$me" ]; then continue; fi
    read -r s < "/proc/$p/stat" 2>/dev/null || continue
    s=${s##*) }; s=${s%% *}
    [ "$s" = Z ] && continue
    kill -9 "$p" 2>/dev/null
    left=$((left + 1))
  done
}
i=0
sweep
while [ "$left" -gt 0 ] && [ "$i" -lt 50 ]; do sleep 0.1; sweep; i=$((i + 1)); done
printf 'survivors %s\n' "$left"
for s in out err; do
  f="$d/$s"
  if [ -f "$f" ] && [ ! -L "$f" ]; then
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

# $1 path, $2 byte limit + 1. Exit 3: no regular file at the path.
READ = r'''
set -o pipefail
f=$1
if [ ! -f "$f" ]; then exit 3; fi
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
        # Disposal bookkeeping, owned by the pool under its lock.
        self.disposal_attempts = 0
        self.next_disposal_at = 0.0
        self.last_disposal_error: Optional[str] = None
        # Set when the sandbox can no longer be trusted; every later operation fails.
        self.invalidated: Optional[str] = None

    def activate(self, now: Optional[float] = None) -> None:
        """Hand the sandbox to one caller; it is disposed after this use."""
        self.state = SandboxState.ACTIVE
        self.activated_at = time.monotonic() if now is None else now

    @property
    def short_id(self) -> str:
        return (self.container_ref.id or "")[:12]

    # ----- integrity -----------------------------------------------------------------
    def _check_usable(self) -> None:
        if self.invalidated is not None:
            raise SandboxInvalidatedError(f"The sandbox was invalidated: {self.invalidated}")

    def _invalidate(self, reason: str) -> None:
        if self.invalidated is None:
            self.invalidated = reason

    def _control(self, cmd: List[str], *, user: str = USER, workdir: str = "/") -> tuple:
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

    def _write_file(self, path: str, content: bytes, *, user: str = USER) -> None:
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
                self._write_file(f"/app/{path}", submission_file.content.encode("utf-8"))
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
        """
        self._check_usable()
        run_dir = f"{RUN_ROOT}-{uuid.uuid4().hex}"
        if len(request.stdin) > INLINE_STDIN_BYTES:
            self._write_file(f"{run_dir}/in", request.stdin)
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
            stopped = self._stopped_result(call, finished, duration)
            if stopped is None:
                raise
            return stopped
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

    def _stopped_result(self, call: _Call, finished: bool, duration: float) -> Optional[ProcessResult]:
        """The process's own exit when the whole container stopped under it.

        A program can take the container down with it (for example by exhausting
        the memory limit). Every process is then gone and the sandbox is
        invalidated, but the exit code the process returned is still its result;
        its outputs are lost with the container.
        """
        try:
            self.container_ref.reload()
            running = self.container_ref.status == "running"
        except Exception:  # pylint: disable=broad-exception-caught
            running = False  # removed: nothing can still run in it
        if running or not finished or call.error is not None or call.result is None:
            return None
        marker = call.result.output or b""
        if b"autograder:started" not in marker or call.result.exit_code in (None, 0):
            return None
        self._invalidate("the sandbox stopped during a process")
        return ProcessResult(ProcessStatus.EXITED, call.result.exit_code, duration=duration)

    def _collect(self, run_dir: str, limit: int):
        code, output = self._control(["/bin/sh", "-c", COLLECT, "autograder-collect", run_dir, str(limit)])
        lines = output.decode("ascii", "replace").split("\n")
        try:
            if code != 0 or not lines[0].startswith("survivors "):
                raise ValueError("unexpected collector output")
            survivors = int(lines[0].split()[1])
            streams = []
            for index, name in ((1, "out"), (3, "err")):
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

        Raises ``FileNotFoundError`` only when no regular file exists at ``path``,
        ``ArtifactTooLargeError`` above ``max_bytes`` and ``ArtifactReadError``
        when an existing file could not be read; sandbox failures stay distinct.
        """
        if not path.startswith("/"):
            raise ValueError(f"Path must be absolute inside container: {path}")
        self._check_usable()
        try:
            code, output = self._control(["/bin/sh", "-c", READ, "autograder-read", path, str(max_bytes + 1)])
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
