"""A real sandbox owner process for the lifetime tests (run by ``test_execution_budget``).

``python -m tests.integration.lifetime_owner local <runtime> <lifetime>``
    A local-mode host: its own ``SandboxManager`` acquires one sandbox with a
    short lifetime, prints ``<container id>`` and then runs an endless student
    program in it until the test SIGKILLs this process.

``python -m tests.integration.lifetime_owner service <runtime> <fd>``
    The private sandbox control service on the listening socket ``fd``,
    served by uvicorn exactly as in production, until the test SIGKILLs it.

Both owners carry a hostname nobody else uses (a recreated container's random
hostname), so no later manager could ever prove them dead and reclaim their
sandboxes: only the sandbox's own lifetime can end them.
"""
import sys
import uuid

from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.language import Language
from autograder.models.process import ProcessRequest
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.ownership import OwnerIdentity
from tests.sandbox_profiles import TEST_IMAGES

TOKEN = "cor02-lifetime-token"
LOOP = "while True:\n    pass\n"


def manager(runtime: str) -> SandboxManager:
    current = OwnerIdentity.current()
    owner = OwnerIdentity(owner_id=current.owner_id, hostname=f"cor02-{uuid.uuid4().hex[:12]}",
                          boot_id=current.boot_id, pid=current.pid, start_ticks=current.start_ticks)
    created = SandboxManager([SandboxPoolConfig(language=Language.PYTHON, image=TEST_IMAGES[Language.PYTHON],
                                                pool_size=0, running_timeout=900)],
                             max_sandboxes=2, owner=owner, runtime=runtime)
    return created


def local(runtime: str, lifetime: float) -> None:
    sandbox = manager(runtime).get_sandbox(Language.PYTHON, lifetime_seconds=lifetime)
    sandbox.prepare_workdir({"loop.py": SubmissionFile("loop.py", LOOP)})
    print(sandbox.container_ref.id, flush=True)
    sandbox.run_process(ProcessRequest.command("python3 loop.py", timeout=600))


def service(runtime: str, fd: int) -> None:
    import uvicorn
    from sandbox_manager.api import ControlSettings, create_app
    app = create_app(ControlSettings(token=TOKEN, reaper_interval_seconds=1), manager_factory=lambda: manager(runtime))
    uvicorn.run(app, fd=fd, log_level="warning")


if __name__ == "__main__":
    if sys.argv[1] == "local":
        local(sys.argv[2], float(sys.argv[3]))
    else:
        service(sys.argv[2], int(sys.argv[3]))
