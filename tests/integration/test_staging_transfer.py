"""Staging is one transfer, byte-exact, in real sandboxes (PRF-03).

Every test runs under each runtime this daemon offers: gVisor (``runsc``) when it
is installed, and Docker's default runtime (``runc``). Sandboxes are created with
the shipped Docker profile; the Docker client records every exec it creates, so
the counts below are the Docker calls the sandbox actually made.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name,unused-argument
import gc
import hashlib
import json
import sys
import time
import warnings

import docker
import pytest

from autograder import HostCapabilities, compile_definition
from autograder.models.capabilities import requirements_for
from autograder.models.dataclass.asset import ResolvedAsset
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.language import Language
from autograder.models.process import ProcessRequest, ProcessStatus
from autograder.services.preparation import prepare_session
from execution_host.docker import DockerSession
from sandbox_manager.docker_profile import FIXTURE_TMPFS_BYTES, GVISOR_RUNTIME, container_options
from sandbox_manager.errors import ProcessExecutionError, SandboxInvalidatedError
from sandbox_manager.sandbox_container import INLINE_STDIN_BYTES, SandboxContainer
from sandbox_manager.submission_contract import MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_FILE_BYTES
from tests.sandbox_profiles import TEST_IMAGES

MIB = 1024 * 1024

# Run as root (which reads everything): path -> [sha256, mode, owner] of every file
# under the given roots, plus the mode of each root.
INVENTORY = """import hashlib, json, os, pwd, sys
files, roots = {}, {}
for root in sys.argv[1:]:
    roots[root] = oct(os.stat(root).st_mode & 0o7777)
    for directory, _, names in os.walk(root):
        for name in names:
            path = os.path.join(directory, name)
            info = os.lstat(path)
            files[path] = [hashlib.sha256(open(path, 'rb').read()).hexdigest(), oct(info.st_mode & 0o7777),
                           pwd.getpwuid(info.st_uid).pw_name]
print(json.dumps({'files': files, 'roots': roots}))
"""
STDIN_PROBE = ("python3", "-c", "import hashlib, sys\n"
               "data = sys.stdin.buffer.read()\nprint(len(data), hashlib.sha256(data).hexdigest())")


def _daemon_runtimes():
    client = docker.from_env()
    try:
        offered = client.info().get("Runtimes", {})
    finally:
        client.close()
    return [runtime for runtime in ("runsc", "runc") if runtime == "runc" or runtime in offered]


class RecordingClient:
    """The Docker client the sandbox uses, counting every exec it creates."""

    def __init__(self):
        self.client = docker.from_env()
        self.execs = 0
        self.before_send = None  # called with the container once a staging upload has started
        api = self.client.api
        create, start = api.exec_create, api.exec_start

        def exec_create(*args, **kwargs):
            self.execs += 1
            return create(*args, **kwargs)

        def exec_start(*args, **kwargs):
            connection = start(*args, **kwargs)
            if kwargs.get("socket") and self.before_send is not None:
                return _Interrupting(connection, self.before_send)
            return connection

        api.exec_create, api.exec_start = exec_create, exec_start


class _Interrupting:
    """A Docker attach socket that runs ``hook`` after the first half of the upload."""

    def __init__(self, connection, hook):
        self._socket = getattr(connection, "_sock", connection)
        self._sock = self  # the sandbox writes to the raw socket, which is this proxy
        self._hook = hook

    def sendall(self, data):
        half = len(data) // 2
        self._socket.sendall(data[:half])
        self._hook()
        self._socket.sendall(data[half:])

    def __getattr__(self, name):
        return getattr(self._socket, name)


@pytest.fixture(scope="module", params=_daemon_runtimes())
def runtime(request):
    return request.param


@pytest.fixture
def recorder():
    recording = RecordingClient()
    yield recording
    recording.client.close()


@pytest.fixture
def sandbox(runtime, recorder):
    options = container_options(TEST_IMAGES[Language.PYTHON], f"prf03-staging-{runtime}-{time.monotonic_ns()}",
                                {"prf03": "test"}, 600)
    if runtime == "runsc":
        options["runtime"] = GVISOR_RUNTIME
    container = recorder.client.containers.run(**options)
    try:
        container.reload()
        assert container.attrs["HostConfig"].get("Runtime") == runtime
        recorder.execs = 0
        yield SandboxContainer(Language.PYTHON, container)
    finally:
        container.remove(force=True, v=True)


def inventory(sandbox, *roots):
    result = sandbox.container_ref.exec_run(["python3", "-c", INVENTORY, *roots], user="root")
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def submission(count, size):
    """``count`` files of ``size`` UTF-8 bytes each, spread over nested directories."""
    return {f"pkg/{index % 7}/m{index}.py": SubmissionFile(f"pkg/{index % 7}/m{index}.py",
                                                           f"# {index}\n".ljust(size, "x")[:size])
            for index in range(count)}


# ----- a constant number of Docker calls whatever the count or size ------------------

@pytest.mark.parametrize("count, size", [(1, 2048), (10, 2048), (MAX_FILES, 2048),
                                         (MAX_TOTAL_FILE_BYTES // MAX_FILE_BYTES, MAX_FILE_BYTES)],
                         ids=["1-file", "10-files", "100-files", "5-MiB"])
def test_a_submission_is_staged_in_one_exec(sandbox, recorder, count, size):
    files = submission(count, size)
    sandbox.prepare_workdir(files)
    assert recorder.execs == 1
    staged = inventory(sandbox, "/app")["files"]
    assert staged == {f"/app/{name}": [digest(item.content.encode()), "0o644", "sandbox"]
                      for name, item in files.items()}


def test_a_fixture_set_at_the_tmpfs_maximum_is_staged_in_one_exec(sandbox, recorder):
    pieces = 4  # each stays below the profile's 10 MB file-size limit
    fixtures = [ResolvedAsset(f"/tmp/app/set/{index}.bin", bytes([index]) * (FIXTURE_TMPFS_BYTES // pieces),
                              read_only=bool(index % 2)) for index in range(pieces)]
    sandbox.inject_assets(fixtures)
    assert recorder.execs == 1
    assert inventory(sandbox, "/tmp/app")["files"] == {
        item.target: [digest(item.content), "0o444" if item.read_only else "0o644", "root"] for item in fixtures}


class _Lender:
    """A manager that lends the test's sandbox to the host session."""

    def __init__(self, sandbox):
        self.sandbox = sandbox

    def get_sandbox(self, language, wait_seconds, lifetime_seconds=None):
        del language, wait_seconds, lifetime_seconds
        return self.sandbox


def _fixture_definition(fixtures):
    return compile_definition({
        "schema_version": "2.0", "languages": ["python"],
        "criteria": {"base": {"tests": [{
            "id": "runs", "type": "expect_output", "name": "Runs",
            "parameters": {"program_command": "python3 main.py", "inputs": [], "expected_output": "ok"}}]}},
        "preparation": {"fixtures": [{"reference": reference, "path": path, "read_only": read_only}
                                     for reference, (path, _, read_only) in fixtures.items()]}})


@pytest.mark.parametrize("count, size", [(1, 2048), (10, 2048), (100, 2048), (4, FIXTURE_TMPFS_BYTES // 4)],
                         ids=["1-fixture", "10-fixtures", "100-fixtures", "32-MiB"])
def test_grading_stages_the_whole_fixture_set_in_one_exec(sandbox, recorder, count, size):
    """The grading path (``prepare_session`` through the Docker host's session), not only ``inject_assets``."""
    fixtures = {f"course/{index}": (f"set/{index % 7}/{index}.bin", bytes([index % 256]) * size, bool(index % 2))
                for index in range(count)}
    compiled = _fixture_definition(fixtures)
    session = DockerSession(_Lender(sandbox), Language.PYTHON)
    prepare_session(session, compiled, requirements_for(compiled, Language.PYTHON),
                    HostCapabilities(fixtures=lambda reference: fixtures[reference][1]))
    assert recorder.execs == 1
    assert inventory(sandbox, "/tmp/app")["files"] == {
        f"/tmp/app/{path}": [digest(content), "0o444" if read_only else "0o644", "root"]
        for path, content, read_only in fixtures.values()}


# ----- exact bytes, paths, owners and modes ---------------------------------------

def test_submission_paths_and_bytes_are_exact(sandbox):
    files = {
        "main.py": "print('ok')\n",
        "empty.py": "",
        "deep/a/b/c/d/e/f.py": "x = 1\n",
        "été/文件 with spaces.py": "s = 'é文'\n",
        ("n" * 120) + "/" + ("m" * 131): "long path\n",  # 252 bytes, near the 255-byte maximum
        "crlf.txt": "a\r\nb\r\n",
    }
    sandbox.prepare_workdir({name: SubmissionFile(name, text) for name, text in files.items()})
    state = inventory(sandbox, "/app")
    assert state["files"] == {f"/app/{name}": [digest(text.encode()), "0o644", "sandbox"]
                              for name, text in files.items()}
    assert state["roots"]["/app"] == "0o1777"
    result = sandbox.run_process(ProcessRequest(argv=("python3", "main.py"), cwd="/app"))
    assert (result.status, result.stdout) == (ProcessStatus.EXITED, "ok\n")


def test_fixtures_keep_bytes_owner_and_mode_and_the_submission_cannot_write_read_only_ones(sandbox):
    fixtures = [ResolvedAsset("/tmp/app/binary.bin", bytes(range(256)) * 512, True),
                ResolvedAsset("/tmp/app/empty.txt", b"", True),
                ResolvedAsset("/tmp/app/nested/é文.csv", b"a,b\n1,2\n", False),
                ResolvedAsset("/tmp/top-level.txt", b"directly under /tmp", True)]
    sandbox.inject_assets(fixtures)
    state = inventory(sandbox, "/tmp")
    expected = {item.target: [digest(item.content), "0o444" if item.read_only else "0o644", "root"]
                for item in fixtures}
    assert {path: value for path, value in state["files"].items() if path in expected} == expected
    # /tmp itself stays the sticky, world-writable tmpfs: runs still stage their own files there.
    assert state["roots"]["/tmp"] == "0o1777"
    for item in fixtures:
        result = sandbox.run_process(ProcessRequest(shell=f"echo x >> '{item.target}'", cwd="/tmp"))
        assert result.exit_code != 0, item.target
    assert inventory(sandbox, "/tmp")["files"] == state["files"]


#: Text: every printable ASCII character, newlines and a two-byte character.
TEXT = ("".join(map(chr, range(32, 127))) + "\n\u00e9\n").encode()


@pytest.mark.parametrize("size, binary", [(INLINE_STDIN_BYTES, False), (INLINE_STDIN_BYTES + 1, False), (MIB, False),
                                          (INLINE_STDIN_BYTES, True), (1, True)],
                         ids=["48KiB", "48KiB+1", "1MiB", "48KiB-binary", "NUL"])
def test_stdin_is_byte_exact_with_a_constant_number_of_execs(sandbox, recorder, size, binary):
    stdin = (bytes(range(256)) * (size // 256 + 1))[:size] if binary else (TEXT * (size // len(TEXT) + 1))[:size]
    if not binary:
        stdin = stdin.decode("utf-8", "ignore").encode()  # never cut the two-byte character
        stdin += b"x" * (size - len(stdin))
    result = sandbox.run_process(ProcessRequest(argv=STDIN_PROBE, cwd="/app", stdin=stdin))
    assert (result.status, result.exit_code, result.stdout) == (ProcessStatus.EXITED, 0, f"{size} {digest(stdin)}\n")
    # The run and its collector, plus one staging transfer for stdin above the inline
    # size or not text (NUL or invalid UTF-8) that an argument cannot carry.
    assert recorder.execs == (3 if binary or size > INLINE_STDIN_BYTES else 2)


def test_staging_releases_its_docker_connection(sandbox, monkeypatch):
    """Each transfer closes docker-py's response and socket: nothing is left for the
    garbage collector to report on a worker's stderr (``ResourceWarning`` for the
    socket, or ``ValueError: I/O operation on closed file`` from the response)."""
    unraisable = []
    monkeypatch.setattr(sys, "unraisablehook", lambda report: unraisable.append(repr(report.exc_value)))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        for index in range(20):
            sandbox.prepare_workdir(submission(1, 10 + index))
            sandbox.run_process(ProcessRequest(argv=("true",), stdin=b"x" * (INLINE_STDIN_BYTES + 1)))
        gc.collect()
    assert unraisable == []
    assert [str(item.message) for item in caught if issubclass(item.category, ResourceWarning)] == []


# ----- failures stage nothing, or invalidate the sandbox -------------------------------

@pytest.mark.parametrize("bad", ["../escape.py", "/etc/passwd", "a/../../b.py"])
def test_traversal_is_rejected_before_anything_is_staged(sandbox, recorder, bad):
    files = {"ok.py": SubmissionFile("ok.py", "x"), bad: SubmissionFile(bad, "x")}
    with pytest.raises(RuntimeError) as raised:
        sandbox.prepare_workdir(files)
    assert isinstance(raised.value.__cause__, ValueError)
    with pytest.raises(ValueError):
        sandbox.inject_assets([ResolvedAsset("/tmp/ok", b"x"), ResolvedAsset("/tmp/../etc/x", b"x")])
    assert recorder.execs == 0
    assert inventory(sandbox, "/app", "/tmp")["files"] == {}
    assert sandbox.invalidated is None


def test_fixtures_beyond_the_tmpfs_fail_and_invalidate_the_sandbox(sandbox):
    oversize = [ResolvedAsset(f"/tmp/app/{index}.bin", b"\xff" * (8 * MIB), True) for index in range(5)]
    with pytest.raises(ProcessExecutionError):
        sandbox.inject_assets(oversize)
    assert sandbox.invalidated is not None
    with pytest.raises(SandboxInvalidatedError):
        sandbox.run_process(ProcessRequest(argv=("true",)))


@pytest.fixture
def interrupted(recorder, sandbox, monkeypatch):
    """The host kills the container halfway through the next upload.

    gVisor's daemon side then stops reading stdin without closing the connection,
    so the upload ends at the control deadline; it is shortened to keep this fast.
    """
    monkeypatch.setattr("sandbox_manager.sandbox_container.CONTROL_TIMEOUT_SECONDS", 10)
    recorder.before_send = sandbox.container_ref.kill


def test_a_sandbox_killed_mid_transfer_never_reports_a_partial_workdir(sandbox, interrupted):
    with pytest.raises(RuntimeError) as raised:
        sandbox.prepare_workdir(submission(MAX_TOTAL_FILE_BYTES // MAX_FILE_BYTES, MAX_FILE_BYTES))
    assert isinstance(raised.value.__cause__, ProcessExecutionError)
    assert sandbox.invalidated is not None
    for later in (lambda: sandbox.prepare_workdir(submission(1, 10)),
                  lambda: sandbox.inject_assets([ResolvedAsset("/tmp/a", b"x")]),
                  lambda: sandbox.run_process(ProcessRequest(argv=("true",)))):
        with pytest.raises(SandboxInvalidatedError):
            later()


def test_a_fixture_set_interrupted_by_a_kill_raises_the_same_error(sandbox, interrupted):
    with pytest.raises(ProcessExecutionError):
        sandbox.inject_assets([ResolvedAsset("/tmp/app/big.bin", b"\x00" * (4 * MIB), True)])
    assert sandbox.invalidated is not None
