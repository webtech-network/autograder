"""The Action's execution host: one sandbox, on demand, on the runner's own Docker.

A container action reaches the runner's Docker daemon through the socket the
runner mounts at ``/var/run/docker.sock``. Submissions run in the web host's
single sandbox profile (``sandbox_manager.docker_profile``) under the OCI runtime
this host explicitly requests, :data:`RUNNER_RUNTIME` (``runc``, which every
GitHub-hosted runner offers; GitHub-hosted runners have no gVisor). The manager
verifies the daemon offers it before grading and never switches runtime. The
sandbox gets no network, no Docker socket and no environment from the Action, so
the runner's tokens stay out of reach (docs/contracts/DECISIONS.md, "Action
execution on the runner"). Each sandbox stops itself when the grading's
execution budget ends, bounded by ``sandbox_config.yml``'s ``running_timeout``.

Unlike the web host it keeps no pool, control API or orphan reclamation: the
host serves the one language the definition selected, from the versioned image
``sandbox_config.yml`` names (pulled when the runner lacks it), with a budget of
one sandbox that the grading acquires and the host removes before the Action
publishes anything.
"""
import logging
from dataclasses import replace

import docker

from autograder.models.capabilities import HostCapabilities
from execution_host.docker import ConfiguredAssessmentProvider, DockerSession
from execution_host.fixtures import S3FixtureProvider
from sandbox_manager.docker_profile import RUNC_RUNTIME
from sandbox_manager.errors import RuntimeImageError, RuntimeUnavailableError
from sandbox_manager.manager import SandboxManager
from sandbox_manager.models.pool_config import SandboxHostConfig

logger = logging.getLogger(__name__)

#: The Action's explicit isolation runtime (the web host's ``general.runtime`` does
#: not apply): the runner VM, discarded after the job, is the outer boundary.
RUNNER_RUNTIME = RUNC_RUNTIME


class DockerUnavailableError(RuntimeError):
    """The runner has no reachable Docker daemon, so execution-based criteria cannot run.

    Raised before grading; documented in docs/github_action/README.md#requirements.
    """

    def __init__(self, language):
        super().__init__(
            f"Docker is not available to the Action. This definition runs {language.value} code, which the "
            "Action executes in a sandbox on the runner's Docker daemon (/var/run/docker.sock). Run the job on a "
            "Linux GitHub-hosted runner (runs-on: ubuntu-latest) or on a Linux self-hosted runner with Docker. "
            "See https://github.com/webtech-network/autograder/blob/main/docs/github_action/README.md#requirements.")


def provider_capabilities():
    """Fixture and AI providers configured by the workflow; no execution."""
    return HostCapabilities(fixtures=S3FixtureProvider.from_environment(),
                            ai=ConfiguredAssessmentProvider.from_environment())


def ensure_image(client, reference):
    """Pull ``reference`` unless the daemon has it; the reference is versioned, never a floating tag."""
    try:
        client.images.get(reference)
        return
    except docker.errors.ImageNotFound:
        pass
    logger.info("Pulling sandbox image %s", reference)
    try:
        client.images.pull(reference)
    except docker.errors.APIError as exc:
        raise RuntimeImageError(
            f"Sandbox image '{reference}' could not be pulled: {exc.explanation or exc}. The Action runs the "
            "runtime images its sandbox_config.yml pins; they must be public (see "
            "docs/github_action/README.md#versions-and-images).") from None


class RunnerHost:
    """Execution for one language on the runner's Docker: at most one sandbox, created on demand.

    Construction connects to Docker and provisions the language's image, so a
    runner without Docker fails before grading with :class:`DockerUnavailableError`
    and a daemon that does not offer ``runc`` with ``IsolationRuntimeError``.
    The caller owns the host and calls :meth:`close`, which removes any sandbox
    still present; it is safe to call repeatedly.
    """

    def __init__(self, language, *, config_file="sandbox_config.yml", client=None):
        config = SandboxHostConfig.load_from_yaml(config_file)
        profile = next((pool for pool in config.pools if pool.language is language), None)
        if profile is None:
            raise RuntimeUnavailableError(f"No sandbox runtime is configured for {language.value}")
        owns_client = client is None
        try:
            client = client or docker.from_env()
            client.ping()
        except docker.errors.DockerException as exc:
            raise DockerUnavailableError(language) from exc
        try:
            ensure_image(client, profile.image)
            self._manager = SandboxManager([replace(profile, pool_size=0)], client, max_sandboxes=1,
                                           runtime=RUNNER_RUNTIME, reclaim_orphans=False)
        except BaseException:
            if owns_client:
                client.close()
            raise
        self._client = client if owns_client else None
        self.language = language
        providers = provider_capabilities()
        self.capabilities = HostCapabilities(execution=self.acquire, fixtures=providers.fixtures, ai=providers.ai,
                                             max_session_seconds=config.running_timeout)

    def acquire(self, language, budget=None):
        """The run's sandbox, stopping itself when ``budget`` ends: an owned session the pipeline closes."""
        if language is not self.language:
            raise RuntimeUnavailableError(f"This Action host serves {self.language.value}, not {language.value}")
        return DockerSession(self._manager, language, budget)

    def close(self):
        """Remove every sandbox of this host, then release the Docker client."""
        manager, self._manager = self._manager, None
        if manager is None:
            return
        try:
            manager.shutdown()
        finally:
            if self._client is not None:
                self._client.close()
