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


class SandboxInvalidatedError(RuntimeError):
    """The sandbox can no longer be trusted.

    A timed-out process could not be confirmed terminated, an internal exec did
    not complete, or output readback failed. Every later operation on the
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
