"""Hostile-submission conformance suite: the sandbox profile's guarantees, per runtime (COR-04).

Every guarantee in docs/contracts/SANDBOX.md ("Isolation guarantees") names the
test that pins it, here or in a suite this one completes. Each test here runs
in real containers under every runtime this daemon offers, gVisor (``runsc``)
when it is installed and ``runc`` always, and is asserted both from inside the
sandbox (the submission's view) and from the host (``docker inspect``).
"""
# pylint: disable=missing-function-docstring,redefined-outer-name
import json

import docker
import pytest
from docker.models.containers import ContainerCollection

from autograder.models.language import Language
from autograder.models.process import ProcessRequest, ProcessStatus, SandboxExhausted
from sandbox_manager.docker_profile import (
    CONTROL_CAPABILITIES, FILE_SIZE_LIMIT_BYTES, GVISOR_RUNTIME, MEMORY_LIMIT_BYTES, MQUEUE_PATH, PIDS_LIMIT,
    RUNC_RUNTIME, SHM_SIZE_BYTES, WRITABLE_PATHS,
)
from sandbox_manager.language_pool import SandboxUnavailableError
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from tests.sandbox_profiles import TEST_IMAGES, offered_runtimes

PY = Language.PYTHON
#: Paths a submission might try to fill outside its writable mounts.
READ_ONLY_PATHS = ("/", "/home/sandbox", "/var/tmp", "/usr/local/lib", "/etc", "/run", "/root")

# Writes 9 MiB files (below the fsize limit) with fsync and POSIX_FADV_DONTNEED,
# so page cache never counts against the memory limit, until a write fails or
# the cap is reached. Prints {directory: [bytes written, errno name or null]};
# "remove" deletes the files first, so a full /tmp still has room for the output.
FILL = r'''
import errno, json, os, sys
cap = int(sys.argv[1]); chunk = b"x" * (9 * 1024 * 1024); report = {}; paths = []
for directory in sys.argv[3:]:
    written, error, index = 0, None, 0
    while written < cap:
        path = os.path.join(directory, f".fill-{os.getpid()}-{index}")
        index += 1
        paths.append(path)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        except OSError as exc:
            error = errno.errorcode.get(exc.errno, str(exc.errno)); break
        try:
            offset = 0
            while offset < len(chunk):
                offset += os.write(fd, chunk[offset:])
            os.fsync(fd)
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        except OSError as exc:
            error = errno.errorcode.get(exc.errno, str(exc.errno))
            written += os.fstat(fd).st_size
            os.close(fd); break
        os.close(fd)
        written += len(chunk)
    report[directory] = [written, error]
if sys.argv[2] == "remove":
    for path in paths:
        try: os.remove(path)
        except OSError: pass
print(json.dumps(report))
'''


@pytest.fixture(scope="module", params=offered_runtimes())
def runtime(request):
    return request.param


@pytest.fixture(scope="module")
def manager(runtime):
    pool = SandboxPoolConfig(language=PY, image=TEST_IMAGES[PY], pool_size=0, running_timeout=300)
    manager = SandboxManager([pool], max_sandboxes=2, runtime=runtime)
    yield manager
    manager.shutdown()


@pytest.fixture
def sandbox(manager):
    sandbox = manager.get_sandbox(PY)
    yield sandbox
    manager.dispose(sandbox)


def python(sandbox, program, *args, timeout=120):
    result = sandbox.run_process(ProcessRequest(argv=("python3", "-c", program, *args), timeout=timeout))
    assert result.status is ProcessStatus.EXITED and result.exit_code == 0, (result.stdout, result.stderr)
    return result.stdout


def inspect(sandbox, size=False):
    """The host's view of the container (``size`` adds the writable layer's ``SizeRw``)."""
    api = docker.from_env().api
    try:
        return api._result(api._get(api._url("/containers/{0}/json", sandbox.container_ref.id),  # pylint: disable=protected-access
                                     params={"size": int(size)}), True)
    finally:
        api.close()


def test_the_configured_runtime_and_the_one_profile_are_in_effect(sandbox, runtime):
    host = inspect(sandbox)["HostConfig"]
    assert host["Runtime"] == runtime
    assert host["ReadonlyRootfs"] is True
    assert set(host["Tmpfs"]) == set(WRITABLE_PATHS) - {"/dev/shm"}
    assert host["ShmSize"] == SHM_SIZE_BYTES
    assert host["NetworkMode"] == "none"
    assert host["Memory"] == host["MemorySwap"] == MEMORY_LIMIT_BYTES
    assert host["PidsLimit"] == PIDS_LIMIT
    assert host["CapDrop"] == ["ALL"]
    assert sorted(cap.removeprefix("CAP_") for cap in host["CapAdd"]) == sorted(CONTROL_CAPABILITIES)
    assert "no-new-privileges" in host["SecurityOpt"]
    assert [u for u in host["Ulimits"] if u["Name"] == "fsize"] == [
        {"Name": "fsize", "Soft": FILE_SIZE_LIMIT_BYTES, "Hard": FILE_SIZE_LIMIT_BYTES}]


def test_disk_fill_never_reaches_host_storage(sandbox):
    """The probe that grew SizeRw by 540 MB (runc) and 1 GiB (runsc) now writes nothing to host disk."""
    report = json.loads(python(sandbox, FILL, str(256 * 1024 * 1024), "keep", *READ_ONLY_PATHS))
    assert report == {path: [0, report[path][1]] for path in READ_ONLY_PATHS}, report
    assert {error for _, error in report.values()} <= {"EROFS", "EACCES"}, report
    state = inspect(sandbox, size=True)
    assert state["SizeRw"] == 0
    assert [m for m in state["Mounts"] if m["Type"] == "volume"] == []  # no anonymous VOLUME /app
    assert sandbox.container_ref.logs() == b""


def test_only_the_declared_paths_are_writable(sandbox, runtime):
    """The submission's view: every directory it may write, and no writable regular file."""
    seen = json.loads(python(sandbox, "import os, stat, json\n"
                                      "dirs, files = [], []\n"
                                      "for root, subdirs, names in os.walk('/'):\n"
                                      "    if root in ('/proc', '/sys'): subdirs[:] = []; continue\n"
                                      "    if os.access(root, os.W_OK): dirs.append(root); subdirs[:] = []; continue\n"
                                      "    for name in names:\n"
                                      "        path = os.path.join(root, name)\n"
                                      "        try: mode = os.lstat(path).st_mode\n"
                                      "        except OSError: continue\n"
                                      "        if stat.S_ISREG(mode) and os.access(path, os.W_OK): files.append(path)\n"
                                      "print(json.dumps({'dirs': dirs, 'files': files}))\n"))
    expected = set(WRITABLE_PATHS) | ({MQUEUE_PATH} if runtime == RUNC_RUNTIME else set())
    assert set(seen["dirs"]) == expected and seen["files"] == [], seen


@pytest.mark.parametrize("path", sorted(WRITABLE_PATHS))
def test_each_writable_path_is_bounded_in_memory_and_by_its_size(sandbox, path):
    size = WRITABLE_PATHS[path]
    report = json.loads(python(sandbox, FILL, str(4 * size), "remove", path))
    written, error = report[path]
    assert error == "ENOSPC" and 0 < written <= size, report
    assert inspect(sandbox, size=True)["SizeRw"] == 0


def test_writes_to_the_container_log_are_refused(sandbox):
    out = python(sandbox, "import os\n"
                          "for path in ('/proc/1/fd/1', '/proc/1/fd/2', '/dev/console'):\n"
                          "    try: open(path, 'w').write('x' * 1024); print('wrote', path)\n"
                          "    except OSError: pass\n")
    assert "wrote" not in out
    assert sandbox.container_ref.logs() == b""


def test_no_network_egress(sandbox):
    out = python(sandbox, "import socket\n"
                          "print(sorted(name for _, name in socket.if_nameindex()))\n"
                          "for address in (('1.1.1.1', 53), ('172.17.0.1', 2375), ('8.8.8.8', 443)):\n"
                          "    s = socket.socket(); s.settimeout(3)\n"
                          "    try: s.connect(address); print('connected', address)\n"
                          "    except OSError: pass\n"
                          "try: socket.getaddrinfo('example.com', 443); print('resolved')\n"
                          "except OSError: pass\n")
    assert out.splitlines() == ["['lo']"]


def test_no_host_credentials_environment_or_docker_socket(sandbox):
    out = python(sandbox, "import os, json\n"
                          "paths = ['/var/run/docker.sock', '/run/docker.sock', '/run/containerd/containerd.sock']\n"
                          "try: open('/proc/1/environ', 'rb').read(); pid1 = 'readable'\n"
                          "except OSError: pid1 = 'denied'\n"
                          "print(json.dumps({'env': dict(os.environ), 'sockets': [p for p in paths if os.path.exists(p)],\n"
                          "                  'pid1': pid1}))\n")
    seen = json.loads(out)
    assert seen["sockets"] == [] and seen["pid1"] == "denied"
    # The submission sees only the image's environment: no variable of the host, the manager
    # process or the configuration can reach it.
    image_env = {item.split("=", 1)[0] for item in docker.from_env().images.get(TEST_IMAGES[PY]).attrs["Config"]["Env"]}
    assert set(seen["env"]) <= image_env | {"HOME", "HOSTNAME", "PWD", "SHLVL", "_"}, seen["env"]


def test_no_privileges_capabilities_or_setuid_paths(sandbox):
    out = python(sandbox, "import os, stat, json\n"
                          "status = dict(line.split(':', 1) for line in open('/proc/self/status'))\n"
                          "setid = []\n"
                          "for root, dirs, files in os.walk('/'):\n"
                          "    if root.startswith(('/proc', '/sys', '/dev')): dirs[:] = []; continue\n"
                          "    for name in files:\n"
                          "        try: mode = os.lstat(os.path.join(root, name)).st_mode\n"
                          "        except OSError: continue\n"
                          "        if stat.S_ISREG(mode) and mode & (stat.S_ISUID | stat.S_ISGID):\n"
                          "            setid.append(os.path.join(root, name))\n"
                          "print(json.dumps({k: v.strip() for k, v in status.items()\n"
                          "                  if k in ('Uid', 'CapEff', 'CapPrm', 'NoNewPrivs')} | {'setid': setid}))\n")
    seen = json.loads(out)
    assert seen["Uid"].split()[0] != "0"
    assert int(seen["CapEff"], 16) == int(seen["CapPrm"], 16) == 0
    assert seen.get("NoNewPrivs", "1") == "1"  # gVisor's /proc omits the field; the host view pins the option.
    assert seen["setid"] == []


def test_signals_to_control_processes_are_refused(sandbox):
    out = python(sandbox, "import os, signal\n"
                          "refused = 0\n"
                          "for pid in filter(str.isdigit, os.listdir('/proc')):\n"
                          "    try: uid = os.stat(f'/proc/{pid}').st_uid\n"
                          "    except OSError: continue\n"
                          "    if uid == 0:\n"
                          "        try: os.kill(int(pid), signal.SIGKILL); print('killed', pid)\n"
                          "        except PermissionError: refused += 1\n"
                          "print('refused', refused)\n")
    assert "killed" not in out and int(out.split()[-1]) >= 1
    assert inspect(sandbox)["State"]["Running"] is True


def test_no_residue_reaches_the_next_submission(manager):
    first = manager.get_sandbox(PY)
    try:
        python(first, "import subprocess\n"
                      "for path in ('/app/residue', '/tmp/residue', '/dev/shm/residue'): open(path, 'w').write('x')\n"
                      "subprocess.Popen(['sleep', '600'], start_new_session=True)\n")
        first_id = first.container_ref.id
    finally:
        manager.dispose(first)
    with pytest.raises(docker.errors.NotFound):
        docker.from_env().containers.get(first_id)
    second = manager.get_sandbox(PY)
    try:
        out = python(second, "import os\n"
                             "print([p for p in ('/app/residue', '/tmp/residue', '/dev/shm/residue') if os.path.exists(p)])\n"
                             "print([p for p in os.listdir('/proc') if p.isdigit()\n"
                             "       and open(f'/proc/{p}/cmdline').read() == 'sleep\\x00600\\x00'])\n")
        assert out.splitlines() == ["[]", "[]"]
    finally:
        manager.dispose(second)


def test_memory_limit_ends_an_exhausting_submission(sandbox):
    with pytest.raises(SandboxExhausted):
        sandbox.run_process(ProcessRequest(argv=("python3", "-c", "b = []\nwhile True: b.append(bytearray(2**24))"),
                                           timeout=60))


# --------------------------------------------------------------- runtime-independent and runtime selection

@pytest.mark.parametrize("image", sorted(set(TEST_IMAGES.values())))
def test_no_built_image_carries_setuid_or_setgid_files(image):
    client = docker.from_env()
    try:
        output = client.containers.run(image, ["find", "/", "-xdev", "-type", "f", "-perm", "/6000"],
                                       user="root", network_mode="none", remove=True, entrypoint=[])
    finally:
        client.close()
    assert output.decode().split() == []


@pytest.mark.skipif(GVISOR_RUNTIME not in offered_runtimes(), reason="gVisor (runsc) is not installed")
def test_a_transient_gvisor_failure_fails_one_acquisition_and_never_downgrades(monkeypatch):
    real_run = ContainerCollection.run
    failures = [docker.errors.APIError("500 Server Error: failed to create task for container: OCI runtime "
                                       "start failed: runsc: sandbox did not start in time")]

    def flaky(self, *args, **kwargs):
        if failures:
            raise failures.pop()
        return real_run(self, *args, **kwargs)

    pool = SandboxPoolConfig(language=PY, image=TEST_IMAGES[PY], pool_size=0, running_timeout=60)
    with SandboxManager([pool], max_sandboxes=1, runtime=GVISOR_RUNTIME) as manager:
        monkeypatch.setattr(ContainerCollection, "run", flaky)
        with pytest.raises(SandboxUnavailableError):
            manager.get_sandbox(PY)
        assert manager.get_budget_stats()["held"] == 0
        for _ in range(2):  # The failure is not remembered: every later acquisition still uses gVisor.
            with manager.acquire_sandbox(PY) as sandbox:
                assert inspect(sandbox)["HostConfig"]["Runtime"] == GVISOR_RUNTIME
                assert python(sandbox, "print('ok')").strip() == "ok"
