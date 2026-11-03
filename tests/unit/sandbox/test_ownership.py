"""Dead-owner proof by lease lock: live, dead, unknown and legacy owners."""
import os
import signal
import subprocess
import sys
import textwrap

from sandbox_manager.ownership import APP_VALUE, LABEL_APP, LABEL_OWNER, OwnerLease, reclaim_dead_owners
from tests.unit.sandbox.test_pool_lifecycle import FakeDocker


def labelled(client, owner):
    labels = {LABEL_APP: APP_VALUE}
    if owner is not None:
        labels[LABEL_OWNER] = owner
    return client.run("img", f"c-{len(client.created)}", labels)


def hold_lease_in_child(lease_dir):
    code = textwrap.dedent(f"""
        import sys, time
        from sandbox_manager.ownership import OwnerLease
        lease = OwnerLease({lease_dir!r}); lease.acquire()
        print(lease.owner_id, flush=True)
        time.sleep(120)
    """)
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True,
                             cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    return child, child.stdout.readline().strip()


def test_live_owner_in_another_process_is_never_reclaimed_until_it_dies(tmp_path):
    client = FakeDocker()
    child, owner = hold_lease_in_child(str(tmp_path))
    try:
        container = labelled(client, owner)
        report = reclaim_dead_owners(client, str(tmp_path))
        assert owner in report.live_owners and not container.removed
        child.send_signal(signal.SIGKILL)
        child.wait(timeout=10)
        report = reclaim_dead_owners(client, str(tmp_path))
        assert report.reclaimed == [container.id] and container.removed
        assert not os.path.exists(tmp_path / f"{owner}.lease")
    finally:
        child.kill()
        child.wait()


def test_same_process_managers_are_distinct_owners(tmp_path):
    client = FakeDocker()
    live = OwnerLease(str(tmp_path))
    live.acquire()
    mine = labelled(client, live.owner_id)
    assert reclaim_dead_owners(client, str(tmp_path)).live_owners == {live.owner_id} and not mine.removed
    live.release(resources_remain=True)  # e.g. shutdown could not confirm cleanup
    assert reclaim_dead_owners(client, str(tmp_path)).reclaimed == [mine.id]


def test_unverifiable_owners_are_left_alone(tmp_path):
    client = FakeDocker()
    legacy = labelled(client, None)                        # created before ownership labels
    elsewhere = labelled(client, "a" * 32)                  # lease in another directory/machine
    traversal = labelled(client, "../../etc/passwd")        # never used as a path
    report = reclaim_dead_owners(client, str(tmp_path))
    assert report.unverifiable == 3 and not report.reclaimed
    assert not (legacy.removed or elsewhere.removed or traversal.removed)


def test_failed_reclamation_keeps_the_lease_file_for_a_later_start(tmp_path):
    client = FakeDocker()
    dead = OwnerLease(str(tmp_path))
    dead.acquire()
    container = labelled(client, dead.owner_id)
    dead.release(resources_remain=True)
    client.remove_failures = 1
    report = reclaim_dead_owners(client, str(tmp_path))
    assert report.failed and os.path.exists(dead.path) and not container.removed
    report = reclaim_dead_owners(client, str(tmp_path))
    assert report.reclaimed == [container.id] and not os.path.exists(dead.path)
