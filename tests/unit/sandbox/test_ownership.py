"""Owner leases: only provably dead owners are reclaimed automatically."""
import json
import os

import pytest

from sandbox_manager import ownership, reclaim
from sandbox_manager.language_pool import LanguagePool, SandboxBudget
from sandbox_manager.manager import SandboxManager
from autograder.models.language import Language
from sandbox_manager.ownership import (
    APP_LABEL_VALUE,
    LABEL_APP,
    LABEL_OWNER,
    LABEL_OWNER_HOST,
    LABEL_OWNER_PROCESS,
    OwnerIdentity,
    owner_status,
    process_start_ticks,
    reclaim_dead_owners,
    reclaim_selected,
)
from tests.unit.sandbox.fakes import FakeDocker, owner, pool_config


def fake_proc(tmp_path, boot="boot-1", processes=None):
    (tmp_path / "sys/kernel/random").mkdir(parents=True)
    (tmp_path / "sys/kernel/random/boot_id").write_text(boot + "\n")
    for pid, start in (processes or {}).items():
        (tmp_path / str(pid)).mkdir()
        # comm may contain spaces and parentheses.
        fields = ["S"] + ["0"] * 18 + [str(start)] + ["0"] * 10
        (tmp_path / str(pid) / "stat").write_text(f"{pid} (odd ) name) " + " ".join(fields))
    return str(tmp_path)


def labels(host="host-a", token="boot-1:4242:777", owner_id="o" * 32):
    return {LABEL_APP: APP_LABEL_VALUE, LABEL_OWNER: owner_id, LABEL_OWNER_HOST: host,
            LABEL_OWNER_PROCESS: token}


def test_process_start_ticks_parses_field_22(tmp_path):
    proc = fake_proc(tmp_path, processes={10: 9999})
    assert process_start_ticks(10, proc) == "9999"
    assert process_start_ticks(11, proc) is None


def test_current_identity_reads_real_proc():
    me = OwnerIdentity.current()
    assert me.pid == os.getpid()
    if os.path.exists("/proc/self/stat"):
        assert me.boot_id and me.start_ticks
        assert me.process_token == f"{me.boot_id}:{me.pid}:{me.start_ticks}"
    other = OwnerIdentity.current()
    assert other.owner_id != me.owner_id  # One lease per manager, even in one process.


@pytest.mark.parametrize("container_labels,processes,expected", [
    (labels(), {4242: 777}, "alive"),
    (labels(), {}, "dead"),                                   # pid no longer running
    (labels(), {4242: 778}, "dead"),                          # pid reused by another process
    (labels(token="boot-0:4242:777"), {4242: 777}, "dead"),   # host rebooted
    (labels(host="host-b"), {}, "remote"),                    # never judged from here
    (labels(token="unknown:4242:777"), {}, "unknown"),
    (labels(token="garbage"), {}, "unknown"),
    ({LABEL_APP: APP_LABEL_VALUE}, {}, "legacy"),
])
def test_owner_status(tmp_path, container_labels, processes, expected):
    proc = fake_proc(tmp_path, processes=processes)
    assert owner_status(container_labels, owner(), proc) == expected


def test_unknown_local_boot_id_never_reclaims(tmp_path):
    proc = fake_proc(tmp_path)
    assert owner_status(labels(token="boot-0:1:1"), owner(boot_id=None), proc) == "unknown"


def test_reclaim_removes_only_dead_local_owners(tmp_path):
    proc = fake_proc(tmp_path, processes={4242: 777, 5000: 1})
    client = FakeDocker()
    run = client.containers.run
    keep = {
        "alive": run(name="alive", labels=labels(owner_id="alive")),
        "remote": run(name="remote", labels=labels(host="host-b", token="boot-0:1:1", owner_id="remote")),
        "legacy": run(name="legacy", labels={LABEL_APP: APP_LABEL_VALUE}),
        "self": run(name="self", labels=labels(owner_id="a" * 32, token="boot-1:9:9")),
        "unrelated": run(name="unrelated", labels={"other": "x"}),
    }
    dead = run(name="dead", labels=labels(owner_id="dead", token="boot-1:6000:5"))
    rebooted = run(name="rebooted", labels=labels(owner_id="rebooted", token="boot-0:4242:777"))
    removed = reclaim_dead_owners(client, owner(), proc)
    assert set(removed) == {dead.id, rebooted.id}
    assert {c.name for c in client.live.values()} == set(keep)
    assert dead.remove_calls == [{"force": True, "v": True}]


def test_two_owners_in_one_process_do_not_reclaim_each_other():
    client = FakeDocker()
    first = SandboxManager([pool_config(pool_size=1)], client, runtime="runc", max_sandboxes=2, monitor_interval=60)
    second = SandboxManager([pool_config(pool_size=1)], client, runtime="runc", max_sandboxes=2, monitor_interval=60)
    try:
        owners = {c.labels[LABEL_OWNER] for c in client.live.values()}
        assert owners == {first.owner.owner_id, second.owner.owner_id}
        assert len(client.live) == 2
    finally:
        first.shutdown()
        second.shutdown()
    assert client.live == {}


def test_startup_reclaims_a_fabricated_dead_owner():
    me = OwnerIdentity.current()
    client = FakeDocker()
    dead = client.containers.run(name="dead", labels=labels(
        host=me.hostname, owner_id="dead", token=f"{me.boot_id}:{2 ** 22 + 1}:1"))
    manager = SandboxManager([pool_config()], client, runtime="runc", max_sandboxes=2, monitor_interval=60)
    try:
        if me.boot_id:  # Linux: the dead owner is provable.
            assert dead.id not in client.live
        else:
            assert dead.id in client.live
    finally:
        manager.shutdown()


def test_reclaim_failure_is_logged_and_startup_continues(caplog):
    me = OwnerIdentity.current()
    client = FakeDocker()
    import docker
    dead = client.containers.run(name="dead", labels=labels(
        host=me.hostname, owner_id="dead", token=f"{me.boot_id}:{2 ** 22 + 1}:1"))
    dead.remove_failures = [docker.errors.APIError("busy")]
    manager = SandboxManager([pool_config()], client, runtime="runc", max_sandboxes=2, monitor_interval=60)
    manager.shutdown()
    if me.boot_id:
        assert "Failed to remove sandbox container" in caplog.text


def test_operator_selection(tmp_path):
    proc = fake_proc(tmp_path, processes={4242: 777})
    client = FakeDocker()
    run = client.containers.run
    remote = run(name="remote", labels=labels(host="host-b", owner_id="r1"))
    remote2 = run(name="remote2", labels=labels(host="host-b", owner_id="r2"))
    alive = run(name="alive", labels=labels(owner_id="alive"))
    legacy = run(name="legacy", labels={LABEL_APP: APP_LABEL_VALUE})
    assert reclaim_selected(client, owner="alive", local=owner(), proc_root=proc) == []
    assert alive.id in client.live
    rows = reclaim_selected(client, dead_host="host-b", local=owner(), dry_run=True, proc_root=proc)
    assert {row["owner"] for row in rows} == {"r1", "r2"} and remote.id in client.live
    reclaim_selected(client, owner="r1", local=owner(), proc_root=proc)
    assert remote.id not in client.live and remote2.id in client.live
    reclaim_selected(client, dead_host="host-b", local=owner(), proc_root=proc)
    assert remote2.id not in client.live
    reclaim_selected(client, legacy=True, local=owner(), proc_root=proc)
    assert legacy.id not in client.live and alive.id in client.live


def test_reclaim_command(monkeypatch, capsys):
    client = FakeDocker()
    client.containers.run(name="legacy", labels={LABEL_APP: APP_LABEL_VALUE})
    monkeypatch.setattr(reclaim.docker, "from_env", lambda: client)
    assert reclaim.main([]) == 0
    listed = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert listed[0]["status"] == "legacy"
    assert reclaim.main(["--legacy", "--dry-run"]) == 0
    assert len(client.live) == 1
    assert reclaim.main(["--legacy"]) == 0
    assert client.live == {}
    client.close.assert_called()


def test_pool_labels_carry_the_owner_lease():
    client = FakeDocker()
    pool = LanguagePool(Language.PYTHON, pool_config(), client, owner(), runtime="runc", budget=SandboxBudget(1))
    sandbox = pool.acquire()
    assert sandbox.container_ref.labels[LABEL_OWNER_PROCESS] == "boot-1:4242:777"
    assert sandbox.container_ref.labels[LABEL_OWNER_HOST] == "host-a"
    assert ownership.APP_FILTER == {"label": f"{LABEL_APP}={APP_LABEL_VALUE}"}
