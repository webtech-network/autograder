"""ENV-04: the runtime images hosts use hold only their documented runtime (real Docker).

The images are the ones named by ``sandbox_config.yml`` (``make sandbox-build-all``
builds them locally; CI builds them from scratch before publishing). A missing
image is a failure here, never a skip: these are the images students run in.
"""
import uuid

import docker
import pytest

from autograder.models.language import Language
from sandbox_manager.errors import RuntimeImageError
from sandbox_manager.manager import RUNTIME_LANGUAGES_LABEL, SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from tests.sandbox_profiles import TEST_IMAGES, suite_runtime

#: The student-facing runtime of each language, as documented in docs/contracts/LANGUAGES.md.
DOCUMENTED_RUNTIMES = {
    Language.PYTHON: ("python3 --version", "Python 3.13."),
    Language.JAVA: ("java -version 2>&1 | head -n 1", 'openjdk version "21.'),
    Language.NODE: ("node --version", "v24."),
    Language.CPP: ("g++ --version | head -n 1", "g++ (Alpine 15."),
    Language.C: ("gcc --version | head -n 1", "gcc (Alpine 15."),
}
#: Never in a runtime image: package managers, downloaders, container daemons, test tools.
FORBIDDEN = ("apk", "pip", "pip3", "npm", "npx", "yarn", "corepack", "curl", "wget", "nc",
             "docker", "dockerd", "containerd", "pytest")


@pytest.fixture(scope="module")
def client():
    try:
        client = docker.from_env()
        client.ping()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        pytest.skip(f"Docker is required: {exc}")
    yield client
    client.close()


def shell(client, image, script):
    output = client.containers.run(image, ["sh", "-c", script], remove=True, network_mode="none",
                                   name=f"ag-image-check-{uuid.uuid4().hex[:12]}")
    return output.decode().strip()


@pytest.mark.parametrize("language", list(Language), ids=lambda language: language.value)
def test_runtime_image_holds_only_its_documented_runtime(client, language):
    image = TEST_IMAGES[language]
    labels = client.images.get(image).labels or {}
    assert language.value in [item.strip() for item in labels.get(RUNTIME_LANGUAGES_LABEL, "").split(",")]

    command, version = DOCUMENTED_RUNTIMES[language]
    assert shell(client, image, command).startswith(version)
    assert shell(client, image, "id -un") == "sandbox" and shell(client, image, "id -u") != "0"

    forbidden = FORBIDDEN + (() if language is Language.NODE else ("node", "nodejs"))
    present = shell(client, image, " ".join(["for tool in", *forbidden, "; do command -v $tool; done; true"]))
    assert present == "", f"{image} ships {present.split()}"
    assert shell(client, image, "find / -xdev -perm /6000 -type f 2>/dev/null; true") == ""


def manager_for(image, language=Language.PYTHON):
    return SandboxManager([SandboxPoolConfig(language=language, image=image, pool_size=1, running_timeout=60)],
                          runtime=suite_runtime(), max_sandboxes=1, reclaim_orphans=False)


def test_missing_image_fails_at_startup_without_pulling(client):
    absent = f"ag-missing-runtime-{uuid.uuid4().hex[:12]}:never-built"
    with pytest.raises(RuntimeImageError, match=f"docker pull {absent}"):
        manager_for(absent)
    with pytest.raises(docker.errors.ImageNotFound):
        client.images.get(absent)


def test_image_of_another_runtime_fails_at_startup(client):
    with pytest.raises(RuntimeImageError, match="does not declare the 'python' runtime"):
        manager_for(TEST_IMAGES[Language.JAVA])
