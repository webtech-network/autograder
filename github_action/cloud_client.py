

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public exception types
# ---------------------------------------------------------------------------

class CloudClientError(Exception):
    """
    Raised when the Autograder Cloud API returns a 4xx response.

    This indicates a *client-side* mistake (wrong config ID, bad token, etc.)
    that will not be resolved by retrying.

    Attributes:
        status_code: The HTTP status code returned by the server.
        message: Human-readable description without secrets.
    """

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code

class CloudConnectionError(Exception):
    """
    Raised when the Autograder Cloud API cannot be reached or consistently
    returns 5xx responses after all retry attempts are exhausted.
    """

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_DEFAULT_CONNECT_TIMEOUT: float = 10.0
_DEFAULT_READ_TIMEOUT: float = 30.0
_DEFAULT_MAX_RETRIES: int = 3
_RETRY_BASE_DELAY: float = 1.0  # seconds; doubled on each subsequent attempt

class CloudClient:
    """
    Thin HTTP client for the Autograder Cloud REST API.

    Args:
        cloud_url: Base URL of the Autograder Cloud instance
            (e.g. ``"https://cloud.example.com"``).  Trailing slashes are
            stripped automatically.
        cloud_token: Bearer token used for ``Authorization`` headers. Never
            logged or included in exception messages.
        connect_timeout: Seconds to wait while establishing a TCP connection.
            Stored as metadata; the underlying socket timeout uses
            ``read_timeout`` (the dominant concern in CI pipelines).
        read_timeout: Seconds to wait for the server to send data after a
            connection is established.  Used as the ``urllib`` socket timeout.
        max_retries: Maximum number of *additional* attempts after the first
            failure for transient errors (5xx / network).  Set to ``0`` to
            disable retries.
    """

    def __init__(
        self,
        cloud_url: str,
        cloud_token: str,
        *,
        connect_timeout: float = _DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = _DEFAULT_READ_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self._base_url = cloud_url.rstrip("/")
        self._cloud_token = cloud_token
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_retries = max_retries

    # ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

    def get_grading_config(self, config_id: str) -> dict:
        """
        Fetch a grading configuration from the cloud by its ID.

        Args:
            config_id: The unique identifier of the grading configuration.

        Returns:
            Parsed JSON payload as a ``dict``.

        Raises:
            CloudClientError: The server returned a 4xx status.
            CloudConnectionError: The server returned persistent 5xx responses
                or could not be reached after all retries.
        """
        url = f"{self._base_url}/api/v1/configs/id/{config_id}"
        logger.debug("Fetching grading config '%s' from %s", config_id, url)
        return self._get(url, context_label=f"grading config '{config_id}'")

    def submit_external_result(self, payload: dict) -> dict:
        """
        Publish a grading result to the Autograder Cloud.

        Args:
            payload: Serialisable dict containing score, feedback, tree, and
                GitHub context metadata.  See :class:`CloudExporter` for the
                canonical schema.

        Returns:
            Parsed JSON response from the server (may be an empty ``{}``).

        Raises:
            CloudClientError: The server returned a 4xx status.
            CloudConnectionError: The server returned persistent 5xx responses
                or could not be reached after all retries.
        """
        url = f"{self._base_url}/api/v1/submissions/external-results"
        logger.debug("Submitting external result to %s", url)
        return self._post(url, payload, context_label="result submission")

    # ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

    def _get(self, url: str, *, context_label: str) -> dict:
        req = urllib.request.Request(
            url,
            method="GET",
            headers=self._auth_headers(),
        )
        return self._request_with_retry(req, context_label=context_label)

    def _post(self, url: str, payload: dict, *, context_label: str) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={**self._auth_headers(), "Content-Type": "application/json"},
        )
        return self._request_with_retry(req, context_label=context_label)

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._cloud_token}",
            "Accept": "application/json",
        }

    def _request_with_retry(self, req: urllib.request.Request, *, context_label: str) -> dict:
        """
        Execute *req* with retry logic for transient failures.

        4xx responses raise :class:`CloudClientError` immediately (no retry).
        5xx and network errors are retried up to ``self.max_retries`` times
        with exponential back-off.

        Args:
            req: Prepared :class:`urllib.request.Request` to send.
            context_label: Human-readable label for the operation used in
                error messages (must not contain secret values).

        Returns:
            Parsed JSON response body as a ``dict``.

        Raises:
            CloudClientError: Non-retryable 4xx response.
            CloudConnectionError: Retries exhausted or persistent server error.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Retrying %s (attempt %d/%d) after %.1fs back-off…",
                    context_label,
                    attempt,
                    self.max_retries,
                    delay,
                )
                time.sleep(delay)

            try:
                with urllib.request.urlopen(req, timeout=self.read_timeout) as response:  # noqa: S310
                    body = response.read().decode("utf-8")
                return self._parse_json(body, context_label)

            except urllib.error.HTTPError as exc:
                if 400 <= exc.code < 500:
                    # Client error — do NOT retry
                    raise CloudClientError(
                        f"Autograder Cloud returned HTTP {exc.code} for {context_label}. "
                        "Check your configuration ID, cloud URL, and token.",
                        status_code=exc.code,
                    ) from exc

                # 5xx — transient; record and retry
                logger.warning(
                    "Autograder Cloud returned HTTP %d for %s (attempt %d/%d).",
                    exc.code,
                    context_label,
                    attempt + 1,
                    self.max_retries + 1,
                )
                last_error = exc

            except urllib.error.URLError as exc:
                logger.warning(
                    "Network error reaching Autograder Cloud for %s (attempt %d/%d): %s",
                    context_label,
                    attempt + 1,
                    self.max_retries + 1,
                    exc.reason,
                )
                last_error = exc

        raise CloudConnectionError(
            f"Could not complete {context_label} after {self.max_retries + 1} attempt(s). "
            "Check that autograder-cloud-url is reachable and the service is healthy."
        ) from last_error

    @staticmethod
    def _parse_json(body: str, context_label: str) -> dict[str, Any]:
        if not body.strip():
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise CloudConnectionError(
                f"Autograder Cloud returned an invalid JSON response for {context_label}."
            ) from exc
