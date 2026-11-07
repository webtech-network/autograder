"""One leased Docker sandbox: staging, the process contract, artifact readback.

Every process runs through :meth:`SandboxContainer.run_process` (see
``autograder.models.process``). Fixed shell scripts below receive every value
as a positional parameter; nothing supplied by a caller is ever interpolated
into shell text. The process itself is ``exec``-ed with its exact argument
vector, its stdin from a staged file and its outputs redirected to files, so
output is bounded when it is read back rather than buffered by Docker.

Staging (submission files, a fixture set, stdin above the inline size) is one
transfer: the host builds a tar archive of regular files from validated paths
and streams it to the stdin of one ``tar`` exec, so it costs a constant number
of Docker calls whatever the file count or size. Docker cannot copy an archive
into the tmpfs mounts ``/app`` and ``/tmp``, so the exec's stdin is the transport.

Who ended a run is decided from host-side evidence, never from an exit code
(see ``docs/contracts/PROCESSES.md``): the container's own limit counters, the
pool's disposal record and Docker's record of how the container stopped. A
submission that exhausts the sandbox raises :class:`SandboxExhausted`; a host
that stops or removes it raises :class:`ProcessExecutionError`.
"""
import base64
import io
import math
import os
import posixpath
import socket
import struct
import tarfile
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
from sandbox_manager.docker_profile import CONTROL_USER, LIFETIME
from sandbox_manager.errors import (
    ArtifactReadError, ArtifactTooLargeError, ProcessExecutionError, SandboxInvalidatedError,
)
from autograder.models.execution import ExtractedFile
from sandbox_manager.models.sandbox_models import HttpResponse, SandboxState

if TYPE_CHECKING:
    from autograder.models.dataclass.asset import ResolvedAsset
    from autograder.models.dataclass.submission import SubmissionFile

USER = "sandbox"                    # the submission's processes; control runs as CONTROL_USER
RUN_ROOT = "/tmp/.autograder-run"  # a run's files: <RUN_ROOT>-<id>.in, .out and .err
INLINE_STDIN_BYTES = 48 * 1024     # text stdin up to this size is one argument; other stdin is staged
CONTROL_TIMEOUT_SECONDS = 60        # staging, termination and readback execs
KILL_GRACE_SECONDS = 10             # wait for the killed process's exec to return
STOP_SETTLE_SECONDS = 10            # wait for Docker to record a container that stopped
COLLECT_ATTEMPTS = 5                # starts of the collector while the pids limit leaves no pid for it
PIDS_SAMPLES = 5                    # Docker stats samples taken when a control exec still failed
DEFAULT_ARTIFACT_BYTES = 1_048_576

# $1 the run's file prefix, $2 "-" when stdin was staged, else "=" and the stdin
# text; the rest is the exact argv. Runs as the submission's user. Its
# processes are the kernel's first choice when the container's memory runs out,
# so control execs are never starved. It forks nothing: every step is a shell
# builtin, so its only process is the one it ``exec``s.
RUNNER = r'''
f=$1; data=$2; shift 2
if [ "$data" != - ]; then
  printf %s "${data#=}" > "$f.in" || { printf 'autograder:staging-failed\n'; exit 125; }
fi
{ printf 1000 > /proc/self/oom_score_adj; } 2>/dev/null
command -v "$1" >/dev/null 2>&1 || { printf 'autograder:not-found\n'; exit 127; }
printf 'autograder:started\n'
exec "$@" < "$f.in" > "$f.out" 2> "$f.err"
'''

# Runs as root, which the submission cannot signal. Kills every non-root
# process (all of them are the submission's) and waits, up to a deadline read
# from /proc/uptime, until none is left, not even a zombie that PID 1 has yet to
# reap (a zombie still holds its pid). Until then it never forks: the sweep, the
# wait and the counters use shell builtins only, because a submission that used
# up the pids limit leaves no pid for a child and busybox ash aborts the script
# on a failed fork. Reports the cgroup's own count of memory-limit OOMs and
# refused forks (cgroup v2 under runc; gVisor has none, and its container stops
# instead) before anything that forks. Then, with no process of the submission
# left to change them, it reports each output's size (-1 when it is not a regular
# file: /tmp belongs to root, so only the file itself can be a planted link),
# writes at most $2 raw bytes of each, out first, and removes the run's files.
# The readback forks five helpers in all (a stat and a head per output, one rm);
# under gVisor each costs about as much CPU as a small program, charged to the
# submission's CPU quota. Its report is its stdout alone (see _control): when the
# readback cannot fork, ash's complaint must never displace the report.
COLLECT = r'''
f=$1; n=$2; me=$$
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
  if [ -f "$f.$s" ] && [ ! -L "$f.$s" ]; then printf '%s %s\n' "$s" "$(stat -c %s "$f.$s")"; else printf '%s -1\n' "$s"; fi
done
for s in out err; do
  if [ -f "$f.$s" ] && [ ! -L "$f.$s" ]; then head -c "$n" "$f.$s"; fi
done
rm -f "$f.in" "$f.out" "$f.err"
'''

# Extracts the archive on stdin at the root, without a shell. Member names are
# normalized relative paths built by the host, never caller text; ``-o`` keeps the
# extracting user as owner (root holds no CHOWN), ``-m`` stamps the current time.
STAGE = ["tar", "-x", "-m", "-o", "-f", "-", "-C", "/"]

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


class _Exec:  # pylint: disable=too-few-public-methods
    """The exit code and combined output of an exec, as ``Container.exec_run`` returns them."""

    def __init__(self, exit_code: Optional[int], output: bytes):
        self.exit_code, self.output = exit_code, output


def _inline_text(stdin: bytes) -> Optional[str]:
    """The runner's stdin argument (``=`` and the text) when ``stdin`` can be one; ``None`` to stage it.

    An argument carries text exactly: UTF-8 without NUL, up to
    :data:`INLINE_STDIN_BYTES`. The runner writes it with a shell builtin, so it
    needs no helper process; any other stdin is staged in one transfer.
    """
    if len(stdin) > INLINE_STDIN_BYTES or b"\x00" in stdin:
        return None
    try:
        return "=" + stdin.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _demultiplex(stream: bytes) -> bytes:
    """Join the payloads of Docker's multiplexed (non-TTY) attach stream."""
    output, offset = bytearray(), 0
    while offset + 8 <= len(stream):
        size = struct.unpack(">I", stream[offset + 4:offset + 8])[0]
        output += stream[offset + 8:offset + 8 + size]
        offset += 8 + size
    return bytes(output)


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
        # The absolute lifetime armed at the grant (arm_lifetime): seconds, and the
        # monotonic instant the container stops by itself (never later than its real stop).
        self.lifetime: Optional[float] = None
        self.expires_at: Optional[float] = None

    def activate(self, now: Optional[float] = None) -> None:
        """Hand the sandbox to one caller; it is disposed after this use."""
        self.state = SandboxState.ACTIVE
        self.activated_at = time.monotonic() if now is None else now

    def arm_lifetime(self, seconds: float) -> None:
        """Make the container stop itself ``seconds`` from now, whether or not its owner survives.

        A root control exec the submission cannot signal sleeps, then kills every
        process; PID 1 then exits (see ``docker_profile.LIFETIME``).
        """
        expires_at = time.monotonic() + seconds  # taken first: the real stop is never earlier
        call = _Call(lambda: self.container_ref.exec_run(
            cmd=["/bin/sh", "-c", LIFETIME, "autograder-lifetime", str(math.ceil(seconds))],
            user=CONTROL_USER, detach=True)).start()
        if not call.join(CONTROL_TIMEOUT_SECONDS) or call.error is not None:
            raise ProcessExecutionError("The sandbox lifetime could not be armed") from call.error
        self.lifetime = seconds
        self.expires_at = expires_at

    @property
    def expired(self) -> bool:
        """Whether the armed lifetime has passed: the container stopped, or is stopping, by itself."""
        return self.expires_at is not None and time.monotonic() >= self.expires_at

    @property
    def short_id(self) -> str:
        return (self.container_ref.id or "")[:12]

    # ----- integrity -----------------------------------------------------------------
    def _check_usable(self) -> None:
        if self.exhausted:
            raise SandboxExhausted("The submission exhausted the sandbox's memory or process limit")
        if self.expired:
            self._invalidate("the sandbox reached its lifetime")
        if self.invalidated is not None:
            raise SandboxInvalidatedError(f"The sandbox was invalidated: {self.invalidated}")

    def _invalidate(self, reason: str) -> None:
        if self.invalidated is None:
            self.invalidated = reason

    def _control(self, cmd: List[str], *, user: str = CONTROL_USER, workdir: str = "/",
                 stdin: Optional[bytes] = None) -> tuple:
        """A bounded internal exec, fed ``stdin`` when given. Failure to complete it invalidates the sandbox.

        Without stdin the exec's output is its stdout alone, the protocol the control
        scripts report on. Docker forwards an exec's stdout and stderr through
        independent copies, so a combined stream has no defined order: a diagnostic
        written after the report (the collector's readback refused a fork) can arrive
        ahead of it. Their stderr is not attached; the process's stderr is ``/dev/null``.
        """
        if stdin is None:
            call = _Call(lambda: self.container_ref.exec_run(cmd=cmd, user=user, workdir=workdir, demux=False,
                                                             stdout=True, stderr=False, stdin=False)).start()
        else:
            call = _Call(lambda: self._exec_with_stdin(cmd, user, workdir, stdin)).start()
        if not call.join(CONTROL_TIMEOUT_SECONDS):
            self._invalidate("an internal sandbox operation did not complete")
            raise ProcessExecutionError("A sandbox operation did not complete in time")
        if call.error is not None:
            self._invalidate("an internal sandbox operation failed")
            raise ProcessExecutionError(f"A sandbox operation failed: {call.error}") from call.error
        return call.result.exit_code, call.result.output or b""

    def _exec_with_stdin(self, cmd: List[str], user: str, workdir: str, data: bytes) -> "_Exec":
        """Run ``cmd`` with ``data`` as its whole stdin: three Docker calls whatever the size.

        Output is read only after stdin is closed; the staging command writes
        nothing unless it fails. Each socket operation is bounded. Closing stdin
        is a half-close of the attach socket, which a TLS connection cannot do,
        so the daemon must be reached over its unix socket or plain TCP.
        """
        api = self.container_ref.client.api
        if str(getattr(api, "base_url", "")).startswith("https://"):
            raise ProcessExecutionError("Staging needs the Docker daemon's unix socket or plain TCP, not TLS")
        exec_id = api.exec_create(self.container_ref.id, cmd, stdout=True, stderr=True, stdin=True,
                                  user=user, workdir=workdir)["Id"]
        connection = api.exec_start(exec_id, socket=True)
        raw = getattr(connection, "_sock", connection)
        try:
            raw.settimeout(CONTROL_TIMEOUT_SECONDS)
            raw.sendall(data)
            raw.shutdown(socket.SHUT_WR)
            received = bytearray()
            while chunk := raw.recv(65536):
                received += chunk
        finally:
            # Close docker-py's HTTP response (it owns the buffered reader over this
            # socket) before the socket, so its release later has nothing left to flush.
            response = getattr(connection, "_response", None)
            if response is not None:
                response.close()
            raw.close()
        return _Exec(api.exec_inspect(exec_id).get("ExitCode"), _demultiplex(bytes(received)))

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

    def _stage(self, files: List[tuple], *, user: str) -> None:
        """Write ``(absolute path, bytes, mode)`` regular files in one transfer, as ``user``.

        Missing parent directories are created (``0755`` under Docker's umask);
        existing ones are left as they are. A transfer that does not complete
        cleanly may have staged part of the files, so it invalidates the sandbox
        and raises :class:`ProcessExecutionError`: a partial workdir is never a success.
        """
        if not files:
            return
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for path, content, mode in files:
                member = tarfile.TarInfo(path.lstrip("/"))
                member.size, member.mode = len(content), mode
                tar.addfile(member, io.BytesIO(content))
        code, output = self._control(STAGE, user=user, stdin=archive.getvalue())
        if code != 0:
            self._invalidate("staging did not complete")
            raise ProcessExecutionError(f"Staging failed ({code}): {output.decode('utf-8', 'replace')[:500]}")

    def prepare_workdir(self, submission_files: Dict[str, 'SubmissionFile']) -> None:
        """Stage submission files into ``/app`` in one transfer, creating parent directories.

        Every path is validated before anything is transferred.
        """
        self._check_usable()
        try:
            self._stage([(f"/app/{self._normalize_relative_path(item.filename)}", item.content.encode("utf-8"), 0o644)
                         for item in (submission_files or {}).values()], user=USER)
        except Exception as e:
            raise RuntimeError(f"Error preparing workdir: {str(e)}") from e

    def inject_assets(self, resolved_assets: List['ResolvedAsset']) -> None:
        """Stage resolved fixtures under ``/tmp`` in one transfer, owned by root, ``0444`` when read-only."""
        self._check_usable()
        files = []
        for asset in resolved_assets or []:
            target_path = asset.target
            if not target_path.startswith('/tmp/'):
                target_path = os.path.join('/tmp', target_path.lstrip('/'))
            files.append((self._normalize_tmp_path(target_path), asset.content, 0o444 if asset.read_only else 0o644))
        self._stage(files, user="root")

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
        run = f"{RUN_ROOT}-{uuid.uuid4().hex}"
        data = _inline_text(request.stdin)
        if data is None:
            self._stage([(f"{run}.in", request.stdin, 0o644)], user=USER)
            data = "-"
        command = ["/bin/sh", "-c", RUNNER, "autograder-run", run, data, *request.program]
        started = time.monotonic()
        call = _Call(lambda: self.container_ref.exec_run(
            cmd=command, workdir=request.cwd, user=USER, demux=False,
            stdout=True, stderr=True, stdin=False)).start()
        finished = call.join(request.timeout)
        duration = time.monotonic() - started
        # Kill whatever remains (the timed-out process, or orphans) and read outputs back.
        try:
            survivors, outputs = self._collect(run, request.max_output_bytes)
        except ProcessExecutionError:
            self._attribute_failed_control()
            raise
        if self.expired:
            # The lifetime may have ended this run before the collector reported:
            # nothing it read back is the submission's own result.
            self._invalidate("the sandbox reached its lifetime")
            raise ProcessExecutionError("The sandbox reached its lifetime during the process")
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
        if self.expired:
            self._invalidate("the sandbox reached its lifetime")  # it stopped itself: the host's limit
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

    def _collect(self, run: str, limit: int):
        """Run the collector; return the survivors and each output as ``(bytes, truncated)``.

        Outputs are read only when no process survived: a survivor could still
        change them, and the run then fails anyway.
        """
        for _ in range(COLLECT_ATTEMPTS):
            code, output = self._control(["/bin/sh", "-c", COLLECT, "autograder-collect", run, str(limit)])
            if output.startswith(b"survivors "):
                break
            # The collector never reported: under runc, a submission at its pids limit
            # leaves no pid to start an exec. It removes nothing before it reports, so
            # starting it again is safe.
        lines = output.split(b"\n", 4)
        try:
            if len(lines) < 2 or not lines[0].startswith(b"survivors ") or not lines[1].startswith(b"limits "):
                raise ValueError("unexpected collector output")
            survivors = int(lines[0].split()[1])
            limit_ooms, refused_forks = (int(value) for value in lines[1].split()[1:])
        except (ValueError, IndexError) as exc:
            self._invalidate("process output readback failed")
            raise ProcessExecutionError("Process output could not be read back") from exc
        if limit_ooms or refused_forks:
            # The container's cgroup recorded the limit; outputs may be unreadable now.
            self._exhaust()
        if survivors:
            return survivors, None
        try:
            if code != 0 or len(lines) != 5:
                raise ValueError("unexpected collector output")
            sizes = []
            for line, name in ((lines[2], b"out"), (lines[3], b"err")):
                label, size = line.split(b" ")
                if label != name or int(size) < -1:
                    raise ValueError("unexpected collector output")
                sizes.append(int(size))
            data, offset, streams = lines[4], 0, []
            for size in sizes:
                length = min(max(size, 0), limit)
                streams.append((data[offset:offset + length], size > limit))
                offset += length
            if offset != len(data):
                raise ValueError("the collector read back a different number of bytes than it reported")
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
