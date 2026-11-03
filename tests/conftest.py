"""Give this test process its own sandbox ownership lease directory.

Sandbox managers reclaim only containers whose owner is proven dead through a
lease file in their lease directory. A fresh directory means tests can only
ever reclaim owners they created; other hosts sharing the Docker daemon (and
their live or dead containers) are never selected.
"""
import os
import tempfile

os.environ["SANDBOX_LEASE_DIR"] = tempfile.mkdtemp(prefix="autograder-test-leases-")
