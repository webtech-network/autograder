"""HTTP client for the Autograder Cloud API used by the GitHub Action.

Retry contract (INT-04):

* GET requests and POST requests that carry an ``Idempotency-Key`` are retried on
  transient failures: network errors, timeouts and HTTP 408/425/429/500/502/503/504.
* POST requests without a key are never retried automatically.
* Other 4xx responses (authentication, validation, 409 key conflicts) are permanent.
* Delays grow exponentially with jitter, honour ``Retry-After`` (seconds or an HTTP
  date) and never exceed the total deadline. ``connect_timeout`` bounds the TCP/TLS
  connection, ``read_timeout`` bounds each socket read and ``total_timeout`` bounds the
  whole operation including back-off.
"""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from functools import partial
import http.client
import json
import logging
import random
import socket
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


class CloudClientError(Exception):
    """A permanent (non-retryable) response such as 401, 403, 404, 409 or 422.

    Attributes:
        status_code: HTTP status code.
        code: Optional machine-readable server code (for example ``IDEMPOTENCY_KEY_REUSED``).
        detail: Safe server-provided explanation, truncated; never contains the token.
    """

    def __init__(self, message: str, status_code: int, *, code: str | None = None, detail: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.detail = detail


class CloudConnectionError(Exception):
    """Transient failures persisted until the retry budget or deadline was exhausted.

    ``uncertain`` is true when a request body may have reached the server (a POST
    whose response was lost). The caller must not assume the operation failed; with
    an idempotency key a later retry safely returns the original receipt.
    """

    def __init__(self, message: str, *, uncertain: bool = False, status_code: int | None = None) -> None:
        super().__init__(message)
        self.uncertain = uncertain
        self.status_code = status_code


_DEFAULT_CONNECT_TIMEOUT: float = 10.0
_DEFAULT_READ_TIMEOUT: float = 30.0
_DEFAULT_TOTAL_TIMEOUT: float = 120.0
_DEFAULT_MAX_RETRIES: int = 3
_RETRY_BASE_DELAY: float = 1.0
_RETRY_MAX_DELAY: float = 30.0
_DETAIL_LIMIT = 300


class _DeadlineConnection(http.client.HTTPConnection):
    """Apply the connect timeout while connecting and the read timeout afterwards."""

    def __init__(self, *args, connect_timeout: float, read_timeout: float, **kwargs):
        super().__init__(*args, **kwargs)
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout

    def connect(self):
        self.timeout = self._connect_timeout
        super().connect()
        self.sock.settimeout(self._read_timeout)


class _DeadlineHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, connect_timeout: float, read_timeout: float, **kwargs):
        super().__init__(*args, **kwargs)
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout

    def connect(self):
        self.timeout = self._connect_timeout
        super().connect()  # includes the TLS handshake
        self.sock.settimeout(self._read_timeout)


class _HTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, connect_timeout, read_timeout):
        super().__init__()
        self._timeouts = {"connect_timeout": connect_timeout, "read_timeout": read_timeout}

    def http_open(self, req):
        return self.do_open(partial(_DeadlineConnection, **self._timeouts), req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, connect_timeout, read_timeout):
        super().__init__()
        self._timeouts = {"connect_timeout": connect_timeout, "read_timeout": read_timeout}

    def https_open(self, req):
        return self.do_open(partial(_DeadlineHTTPSConnection, **self._timeouts), req,
                            context=self._context)


def _urlopen(req, *, connect_timeout: float, read_timeout: float):
    """Open ``req`` with separate connect and read deadlines (seam for tests)."""
    opener = urllib.request.build_opener(_HTTPHandler(connect_timeout, read_timeout),
                                         _HTTPSHandler(connect_timeout, read_timeout))
    return opener.open(req, timeout=read_timeout)


def _retry_after(headers, now: float | None = None) -> float | None:
    value = headers.get("Retry-After") if headers is not None else None
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    current = datetime.now(timezone.utc).timestamp() if now is None else now
    return max(0.0, moment.timestamp() - current)


def _problem(exc: urllib.error.HTTPError) -> tuple[str | None, str | None]:
    """Extract a safe machine code and short explanation from an error body."""
    try:
        body = exc.read().decode("utf-8", "replace") if exc.fp is not None else ""
        detail = json.loads(body).get("detail") if body else None
    except (ValueError, AttributeError, OSError):
        return None, None
    if isinstance(detail, dict):
        return detail.get("code"), str(detail.get("message", ""))[:_DETAIL_LIMIT] or None
    if isinstance(detail, str):
        return None, detail[:_DETAIL_LIMIT]
    if isinstance(detail, list):
        messages = [f"{'.'.join(map(str, item.get('path', [])))}: {item.get('message', '')}"
                    for item in detail if isinstance(item, dict)]
        return "VALIDATION_ERROR", "; ".join(messages)[:_DETAIL_LIMIT] or None
    return None, None


class CloudClient:
    """Thin HTTP client for the Autograder Cloud REST API.

    Args:
        cloud_url: Base URL; trailing slashes are stripped.
        cloud_token: Bearer token. Never logged or included in exception messages.
        connect_timeout: Seconds allowed to establish each TCP/TLS connection.
        read_timeout: Seconds allowed for each socket read after connecting.
        total_timeout: Seconds allowed for the whole operation, including retries.
        max_retries: Additional attempts after the first for retryable failures.
    """

    def __init__(
        self,
        cloud_url: str,
        cloud_token: str,
        *,
        connect_timeout: float = _DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = _DEFAULT_READ_TIMEOUT,
        total_timeout: float = _DEFAULT_TOTAL_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        if min(connect_timeout, read_timeout, total_timeout) <= 0 or max_retries < 0:
            raise ValueError("Timeouts must be positive and max_retries nonnegative")
        self._base_url = cloud_url.rstrip("/")
        self._cloud_token = cloud_token
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.total_timeout = total_timeout
        self.max_retries = max_retries

    def get_grading_config(self, config_id) -> dict:
        """Fetch a grading configuration by canonical ID (needs the integration scope)."""
        url = f"{self._base_url}/api/v1/configs/id/{config_id}"
        logger.debug("Fetching grading config '%s' from %s", config_id, url)
        req = urllib.request.Request(url, method="GET", headers=self._auth_headers())
        return self._request(req, context_label=f"grading config '{config_id}'", retry=True)

    def submit_external_result(self, payload: dict, *, idempotency_key: str | None = None) -> dict:
        """Publish a finalized outcome attestation.

        With an ``idempotency_key`` the POST is retried on transient failures and a
        retry after a lost response returns the original receipt. Without a key the
        POST is sent once.
        """
        url = f"{self._base_url}/api/v1/submissions/external-results"
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST", headers=headers)
        logger.debug("Submitting external result to %s", url)
        return self._request(req, context_label="result submission", retry=idempotency_key is not None)

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._cloud_token}", "Accept": "application/json"}

    def _delay(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(retry_after, _RETRY_MAX_DELAY)
        ceiling = min(_RETRY_BASE_DELAY * (2 ** (attempt - 1)), _RETRY_MAX_DELAY)
        return ceiling / 2 + random.random() * ceiling / 2  # equal jitter

    def _request(self, req: urllib.request.Request, *, context_label: str, retry: bool) -> dict:
        deadline = time.monotonic() + self.total_timeout
        attempts = self.max_retries + 1 if retry else 1
        sends_body = req.data is not None
        last_error: Exception | None = None
        last_status: int | None = None
        uncertain = False
        attempt = 0
        for attempt in range(1, attempts + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            retry_after = None
            try:
                with _urlopen(req, connect_timeout=min(self.connect_timeout, remaining),
                              read_timeout=min(self.read_timeout, remaining)) as response:
                    body = response.read().decode("utf-8")
                return self._parse_json(body, context_label)
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRYABLE_STATUS:
                    code, detail = _problem(exc)
                    raise CloudClientError(
                        f"Autograder Cloud returned HTTP {exc.code} for {context_label}"
                        + (f" ({code})" if code else "") + (f": {detail}" if detail else ".")
                        + " Check the configuration ID, cloud URL, token and its scope.",
                        status_code=exc.code, code=code, detail=detail) from exc
                last_error, last_status = exc, exc.code
                # A 5xx after the body was sent may still have committed server side.
                uncertain = uncertain or (sends_body and exc.code >= 500)
                retry_after = _retry_after(exc.headers)
                logger.warning("Autograder Cloud returned HTTP %d for %s (attempt %d/%d).",
                               exc.code, context_label, attempt, attempts)
            except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                last_error, last_status = exc, None
                # Refused/unresolvable connections never delivered the body.
                connect_failure = isinstance(exc, urllib.error.URLError) and isinstance(
                    exc.reason, (ConnectionRefusedError, socket.gaierror))
                uncertain = uncertain or (sends_body and not connect_failure)
                reason = getattr(exc, "reason", None) or type(exc).__name__
                logger.warning("Network error reaching Autograder Cloud for %s (attempt %d/%d): %s",
                               context_label, attempt, attempts, reason)
            if attempt == attempts:
                break
            delay = self._delay(attempt, retry_after)
            if time.monotonic() + delay >= deadline:
                logger.warning("Not retrying %s: the %.0fs total deadline would be exceeded.",
                               context_label, self.total_timeout)
                break
            logger.warning("Retrying %s after %.1fs back-off...", context_label, delay)
            time.sleep(delay)
        guidance = ("The server may have accepted it; retry with the saved delivery.json, which reuses "
                    "the same Idempotency-Key and cannot create a duplicate." if uncertain else
                    "Check that autograder-cloud-url is reachable and the service is healthy.")
        raise CloudConnectionError(
            f"Could not complete {context_label} within {attempt} attempt(s). {guidance}",
            uncertain=uncertain, status_code=last_status) from last_error

    @staticmethod
    def _parse_json(body: str, context_label: str) -> dict[str, Any]:
        if not body.strip():
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise CloudConnectionError(
                f"Autograder Cloud returned an invalid JSON response for {context_label}.") from exc
