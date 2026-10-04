"""Keep Docker integration tests from adopting or deleting another host's sandboxes."""
from uuid import uuid4
import sandbox_manager.language_pool as language_pool
import sandbox_manager.manager as manager

# Set before test modules import LABEL_APP. Existing implementation scopes both
# orphan cleanup and newly created containers by this key. The label value and
# lifecycle semantics remain unchanged; only this test process owns the key.
_TEST_OWNER_LABEL = f"autograder.test.{uuid4().hex}"
language_pool.LABEL_APP = _TEST_OWNER_LABEL
manager.LABEL_APP = _TEST_OWNER_LABEL
