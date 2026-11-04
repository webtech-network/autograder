"""In-memory Docker stand-ins for sandbox lifecycle tests."""
import itertools
from unittest.mock import Mock

import docker

from sandbox_manager.models.pool_config import SandboxPoolConfig
from autograder.models.language import Language
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


class FakeDocker:
    def __init__(self, gvisor=False):
        self.gvisor = gvisor
        self.live = {}
        self.run_failure = None
        self.containers = FakeContainers(self)
        self.close = Mock()


def pool_config(language=Language.PYTHON, pool_size=0, scale_limit=2, running_timeout=60,
                idle_timeout=300, disposal_attempts=3):
    return SandboxPoolConfig(language=language, image=TEST_IMAGES[language], pool_size=pool_size, scale_limit=scale_limit,
                             idle_timeout=idle_timeout, running_timeout=running_timeout,
                             disposal_attempts=disposal_attempts)


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
