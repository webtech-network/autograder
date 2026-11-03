"""In-memory lease handles of the private control API.

A handle is an opaque random ID bound to a client-generated lease secret. The
secret is both the ownership proof for every operation and the idempotency key
for acquisition: replaying an acquisition with the same secret returns the same
handle, so a lost acquire response does not leak a second sandbox.

Handles live in one process. Deploy the control API as exactly one worker; see
``docs/contracts/SANDBOX.md``.
"""
import hashlib
import hmac
import logging
import secrets
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

from sandbox_manager.errors import SandboxCleanupError, SandboxHandleError
from sandbox_manager.models.sandbox_models import SandboxState
from autograder.models.language import Language

logger = logging.getLogger(__name__)

ACQUIRE_WAIT_SECONDS = 120


def lease_digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


@dataclass
class Handle:
    handle_id: str
    digest: str
    language: Language
    sandbox: object
    state: str = "active"  # active | closing


@dataclass
class Tombstone:
    digest: str
    reason: str  # disposed | expired


class HandleRegistry:
    """Bounded handle table: active/closing handles plus recent tombstones."""

    def __init__(self, manager, *, tombstone_limit: int = 4096):
        self.manager = manager
        self._lock = threading.Lock()
        self._handles: dict[str, Handle] = {}
        self._by_digest: dict[str, str] = {}
        self._pending: dict[str, threading.Event] = {}
        self._tombstones: OrderedDict[str, Tombstone] = OrderedDict()
        self._tombstone_limit = tombstone_limit

    # ----- acquisition ---------------------------------------------------------------
    def acquire(self, language: Language, secret: str) -> Handle:
        digest = lease_digest(secret)
        while True:
            with self._lock:
                self._sweep()
                existing = self._by_digest.get(digest)
                if existing is not None:
                    handle = self._handles[existing]
                    if handle.language is not language:
                        raise ValueError("This lease secret is already bound to another language")
                    return handle  # replayed acquisition after a lost response
                waiting = self._pending.get(digest)
                if waiting is None:
                    self._pending[digest] = threading.Event()
                    break
            if not waiting.wait(ACQUIRE_WAIT_SECONDS):
                raise SandboxHandleError("sandbox_not_found", "A concurrent acquisition did not finish")
        try:
            sandbox = self.manager.acquire(language)
            handle = Handle(handle_id=secrets.token_hex(16), digest=digest, language=language, sandbox=sandbox)
            with self._lock:
                self._handles[handle.handle_id] = handle
                self._by_digest[digest] = handle.handle_id
            return handle
        finally:
            with self._lock:
                self._pending.pop(digest).set()

    # ----- lookups -------------------------------------------------------------------
    def _owned(self, handle_id: str, secret: Optional[str]) -> Handle:
        """Return an operable handle, or raise the distinct not-found/expired error."""
        digest = lease_digest(secret or "")
        with self._lock:
            self._sweep()
            handle = self._handles.get(handle_id)
            if handle is not None and hmac.compare_digest(handle.digest, digest):
                if handle.state == "active":
                    return handle
                raise SandboxHandleError("sandbox_expired", "The sandbox lease is closing")
            tombstone = self._tombstones.get(handle_id)
            if tombstone is not None and hmac.compare_digest(tombstone.digest, digest):
                raise SandboxHandleError("sandbox_expired", f"The sandbox lease has ended ({tombstone.reason})")
        # Unknown and not-owned are indistinguishable to the caller.
        raise SandboxHandleError("sandbox_not_found", "Sandbox lease not found")

    def sandbox(self, handle_id: str, secret: Optional[str]):
        return self._owned(handle_id, secret).sandbox

    # ----- disposal ------------------------------------------------------------------
    def dispose(self, handle_id: str, secret: Optional[str]) -> str:
        """Dispose idempotently. Returns ``disposed`` or ``closing`` (retained for retry)."""
        digest = lease_digest(secret or "")
        with self._lock:
            self._sweep()
            handle = self._handles.get(handle_id)
            if handle is None or not hmac.compare_digest(handle.digest, digest):
                tombstone = self._tombstones.get(handle_id)
                if tombstone is not None and hmac.compare_digest(tombstone.digest, digest):
                    return "disposed"  # replayed delete after a lost response, or expired lease
                raise SandboxHandleError("sandbox_not_found", "Sandbox lease not found")
            handle.state = "closing"  # the record stays until destruction is confirmed
        try:
            self.manager.dispose(handle.sandbox)
        except SandboxCleanupError:
            return "closing"
        with self._lock:
            self._retire(handle, "disposed")
        return "disposed"

    def close_all(self) -> None:
        """Host shutdown: end every handle; the manager shutdown confirms destruction."""
        with self._lock:
            handles = list(self._handles.values())
        for handle in handles:
            try:
                self.manager.dispose(handle.sandbox)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Handle %s cleanup failed at shutdown", handle.handle_id[:8])
            with self._lock:
                self._retire(handle, "disposed")

    # ----- bookkeeping ---------------------------------------------------------------
    def _retire(self, handle: Handle, reason: str) -> None:
        if self._handles.pop(handle.handle_id, None) is None:
            return
        self._by_digest.pop(handle.digest, None)
        self._tombstones[handle.handle_id] = Tombstone(digest=handle.digest, reason=reason)
        while len(self._tombstones) > self._tombstone_limit:
            self._tombstones.popitem(last=False)

    def _sweep(self) -> None:
        """Retire handles whose sandbox the pool already destroyed (lease expiry/retry)."""
        for handle in list(self._handles.values()):
            if handle.sandbox.state is SandboxState.STOPPED:
                self._retire(handle, "expired" if handle.state == "active" else "disposed")
            elif handle.sandbox.state is SandboxState.CLOSING and handle.state == "active":
                handle.state = "closing"  # the pool expired the lease; its cleanup is retrying

    def stats(self) -> dict:
        with self._lock:
            self._sweep()
            states = [handle.state for handle in self._handles.values()]
            return {"active": states.count("active"), "closing": states.count("closing"),
                    "tombstones": len(self._tombstones)}
