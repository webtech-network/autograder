"""In-memory Docker stand-ins for sandbox lifecycle tests."""
import itertools
from unittest.mock import Mock

import docker

from sandbox_manager.models.pool_config import SandboxPoolConfig
from autograder.models.language import LANGUAGE_IDS, Language
from sandbox_manager.ownership import OwnerIdentity
from tests.sandbox_profiles import TEST_IMAGES

_ids = itertools.count(1)


class FakeContainer:
    def __init__(self, client, name, labels, kwargs):
        self.client = client
        self.id = f"{next(_ids):064x}"
        self.name = name
        self.labels = labels
        self.kwargs = kwargs
        self.remove_failures = []  # Exceptions raised by successive remove() calls.
        self.remove_calls = []
        self.exec_calls = []  # Control execs; a granted sandbox arms its lifetime with one.

    def exec_run(self, **kwargs):
        self.exec_calls.append(kwargs)
        if self.client.exec_failure is not None:
            raise self.client.exec_failure
        if self.client.on_exec is not None:
            return self.client.on_exec(kwargs)
        return Mock(exit_code=None if kwargs.get("detach") else 0, output=b"")

    def remove(self, **kwargs):
        self.remove_calls.append(kwargs)
        if self.remove_failures:
            raise self.remove_failures.pop(0)
        if self.id not in self.client.live:
            raise docker.errors.NotFound("gone")
        del self.client.live[self.id]


class FakeContainers:
    def __init__(self, client):
        self.client = client
        self.run_calls = []

    def run(self, **kwargs):
        self.run_calls.append(kwargs)
        if self.client.on_run is not None:
            self.client.on_run(kwargs)  # Tests block or observe creation here (outside any pool lock).
        if kwargs.get("runtime") == "runsc" and not self.client.gvisor:
            raise docker.errors.APIError("unknown or invalid runtime name: runsc")
        if self.client.run_failure is not None:
            raise self.client.run_failure
        container = FakeContainer(self.client, kwargs["name"], kwargs.get("labels", {}), kwargs)
        self.client.live[container.id] = container
        return container

    def get(self, name_or_id):
        for container in self.client.live.values():
            if name_or_id in (container.id, container.name):
                return container
        raise docker.errors.NotFound(name_or_id)

    def list(self, **kwargs):
        filters = kwargs.get("filters")
        wanted = (filters or {}).get("label", [])
        wanted = [wanted] if isinstance(wanted, str) else wanted
        pairs = [item.split("=", 1) for item in wanted]
        return [c for c in self.client.live.values() if all(c.labels.get(k) == v for k, v in pairs)]


class FakeImage:
    def __init__(self, labels):
        self.labels = labels


class FakeImages:
    """Every reference is present and declares every language unless a test says otherwise."""

    def __init__(self):
        self.missing = set()
        self.labels = {}  # reference -> label dict
        self.get_calls = []

    def get(self, reference):
        self.get_calls.append(reference)
        if reference in self.missing:
            raise docker.errors.ImageNotFound(f"No such image: {reference}")
        return FakeImage(self.labels.get(reference, {"autograder.runtime.languages": ",".join(LANGUAGE_IDS)}))


class FakeDocker:
    def __init__(self, gvisor=False):
        self.gvisor = gvisor
        self.live = {}
        self.run_failure = None
        self.exec_failure = None
        self.on_exec = None  # Scripted answers to control execs: kwargs -> result.
        self.on_run = None
        self.containers = FakeContainers(self)
        self.images = FakeImages()
        self.close = Mock()


def pool_config(language=Language.PYTHON, pool_size=0, running_timeout=900, disposal_attempts=3):
    return SandboxPoolConfig(language=language, image=TEST_IMAGES[language], pool_size=pool_size,
                             running_timeout=running_timeout, disposal_attempts=disposal_attempts)


def owner(**overrides):
    values = {"owner_id": "a" * 32, "hostname": "host-a", "boot_id": "boot-1", "pid": 4242,
              "start_ticks": "777"}
    values.update(overrides)
    return OwnerIdentity(**values)


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now
