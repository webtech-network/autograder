"""Sandbox errors shared by the local manager, the control API and the remote client.

Every error here except :class:`ArtifactTooLargeError` is a ``RuntimeError``:
an infrastructure failure, never a student result. Remote handle and transport
failures are the :mod:`sandbox_manager.remote_client` exceptions.
"""


class RuntimeUnavailableError(RuntimeError):
    """This host has no runtime profile (image) for the requested language.

    The language may be valid and allowed by the definition; the host simply
    cannot execute it. Callers report a capability failure, never an invalid
    language. The control API answers ``501 RUNTIME_UNAVAILABLE``.
    """


class RuntimeImageError(RuntimeError):
    """A configured runtime image is absent from the Docker host or serves another language.

    Raised when a :class:`~sandbox_manager.manager.SandboxManager` starts, before
    it creates any container. A manager never pulls: the HTTP host's operator
    pulls (or builds) exactly the references in ``sandbox_config.yml``, and the
    Action's ``RunnerHost`` pulls the selected language's reference first.
    """


class SandboxCapacityTimeout(RuntimeError):
    """No slot of the host sandbox budget became free within the caller's wait.

    Saturation is transient: grading reports it as a retryable capability
    failure, never as an assessed result, and deliberate execution answers
    ``503 EXECUTION_BUSY``. The control API answers ``503 CAPACITY_TIMEOUT``.
    """


class SandboxInvalidatedError(RuntimeError):
    """The sandbox can no longer be trusted.

    A timed-out process could not be confirmed terminated, an internal exec did
    not complete, output readback failed, or the host stopped or removed the
    container. A submission that exhausted the sandbox raises the core
    ``SandboxExhausted`` instead, never this error. Every later operation on the
    sandbox raises this error until it is disposed. The control API answers
    ``409 SANDBOX_INVALIDATED``.
    """


class ProcessExecutionError(RuntimeError):
    """The backend could not run a process or read its result back.

    This is never a student outcome: a process that ran and returned any exit
    code is a ``ProcessResult``. The control API answers ``500 SANDBOX_ERROR``.
    """


class ArtifactReadError(RuntimeError):
    """An existing artifact could not be read back (as opposed to a missing one).

    The control API answers ``500 ARTIFACT_READ_FAILED``.
    """


class ArtifactTooLargeError(ValueError):
    """A requested artifact exceeds the caller's byte limit (``422 ARTIFACT_INVALID``)."""
