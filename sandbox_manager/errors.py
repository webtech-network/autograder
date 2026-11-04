"""Sandbox errors shared by the local manager, the control API and the remote client."""


class RuntimeUnavailableError(RuntimeError):
    """This host has no runtime profile (image) for the requested language.

    The language may be valid and allowed by the definition; the host simply
    cannot execute it. Callers report a capability failure, never an invalid
    language. The control API answers ``501 RUNTIME_UNAVAILABLE``.
    """
