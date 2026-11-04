"""Operator command for sandbox containers that automatic reclamation must not touch.

Automatic startup reclamation only removes containers whose owner is provably
dead on this host. Use this command for the rest, after confirming the owner is
really gone (for example, a decommissioned host or a recreated container with a
new hostname):

    python -m sandbox_manager.reclaim                     # list owners and status
    python -m sandbox_manager.reclaim --dead              # same as startup reclamation
    python -m sandbox_manager.reclaim --owner <owner-id>  # one owner lease
    python -m sandbox_manager.reclaim --dead-host <name>  # every owner on that host
    python -m sandbox_manager.reclaim --legacy            # containers without owner labels

Add ``--dry-run`` to print the selection without removing anything. Containers
whose owner is visibly alive on this host are always refused.
"""
import argparse
import json
import sys

import docker

from sandbox_manager.ownership import OwnerIdentity, describe, reclaim_dead_owners, reclaim_selected


def main(argv=None) -> int:
    """Run the operator command; returns a process exit status."""
    parser = argparse.ArgumentParser(prog="python -m sandbox_manager.reclaim", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--owner", help="remove containers of this owner id")
    parser.add_argument("--dead-host", help="remove containers owned by any process on this hostname")
    parser.add_argument("--legacy", action="store_true", help="remove containers without owner labels")
    parser.add_argument("--dead", action="store_true", help="remove containers of provably dead local owners")
    parser.add_argument("--dry-run", action="store_true", help="print the selection only")
    args = parser.parse_args(argv)
    client = docker.from_env()
    try:
        local = OwnerIdentity.current()
        if args.dead:
            if args.dry_run:
                rows = [row for row in describe(client, local) if row["status"] == "dead"]
            else:
                rows = [{"id": cid[:12], "status": "removed"} for cid in reclaim_dead_owners(client, local)]
        elif args.owner or args.dead_host or args.legacy:
            rows = reclaim_selected(client, owner=args.owner, dead_host=args.dead_host,
                                    legacy=args.legacy, local=local, dry_run=args.dry_run)
        else:
            rows = list(describe(client, local))
        for row in rows:
            print(json.dumps(row, sort_keys=True))
        return 1 if any(row.get("status") == "remove_failed" for row in rows) else 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
