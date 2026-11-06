"""Host-owned fixture retrieval: one logical reference in, its exact bytes out.

There is deliberately no cache. Every call asks the configured object store for
the current object, so distinct references cannot share content, replacing an
object is visible to the next grading run, and an empty object is ordinary
content. Placement, destination paths and read-only modes belong to the
execution session, not to retrieval.
"""
import logging
import os
from threading import Lock

from autograder.models.capabilities import FixtureNotFound

logger = logging.getLogger(__name__)

_MISSING_CODES = frozenset({"NoSuchKey", "404", "NotFound"})


class FixtureProviderError(RuntimeError):
    """The store could not be asked or did not answer; the reference may exist."""


class S3FixtureProvider:
    """Read one object per logical reference from one bucket.

    Configuration is captured at construction; the SDK client is created on the
    first selected fixture and then reused for the provider's lifetime.
    ``client_factory`` lets a host (or a test) supply its own client.
    """

    def __init__(self, *, bucket=None, endpoint_url=None, region="us-east-1",
                 access_key=None, secret_key=None, client_factory=None):
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.region = region
        self._credentials = (access_key, secret_key)
        self._client_factory = client_factory or self._boto3_client
        self._client = None
        self._lock = Lock()

    @classmethod
    def from_environment(cls, environ=None, **overrides):
        """Read the store settings once; reject a store that names no bucket.

        Without ``EXTERNAL_ASSETS_BUCKET_NAME`` the host has no fixture store and a
        fixture assignment fails its preparation. An endpoint without a bucket is
        a misconfigured store, not an absent one, so it stops the host at startup.
        """
        config = os.environ if environ is None else environ
        bucket = config.get("EXTERNAL_ASSETS_BUCKET_NAME") or None
        endpoint_url = config.get("S3_ENDPOINT_URL") or None
        access_key = config.get("AWS_ACCESS_KEY_ID") or None
        secret_key = config.get("AWS_SECRET_ACCESS_KEY") or None
        if endpoint_url and not bucket:
            raise ValueError("S3_ENDPOINT_URL is set but EXTERNAL_ASSETS_BUCKET_NAME is not: "
                             "name the fixture bucket, or unset S3_ENDPOINT_URL")
        if bool(access_key) != bool(secret_key):
            raise ValueError("Set both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, or neither")
        return cls(bucket=bucket, endpoint_url=endpoint_url, region=config.get("AWS_REGION") or "us-east-1",
                   access_key=access_key, secret_key=secret_key, **overrides)

    def _boto3_client(self):
        import boto3
        from botocore.config import Config
        access_key, secret_key = self._credentials
        return boto3.session.Session().client(
            "s3", endpoint_url=self.endpoint_url, region_name=self.region,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"))

    def _get_client(self):
        with self._lock:
            if self._client is None:
                self._client = self._client_factory()
            return self._client

    def __call__(self, reference: str) -> bytes:
        """Return the object's bytes (possibly empty).

        Raises ``FixtureNotFound`` when the bucket has no such key and
        ``FixtureProviderError`` for configuration, transport or service failures.
        """
        if not self.bucket:
            raise FixtureProviderError("No fixture bucket is configured")
        try:
            response = self._get_client().get_object(Bucket=self.bucket, Key=reference)
            body = response["Body"]
            try:
                content = body.read()
            finally:
                body.close()
        except Exception as exc:
            error = getattr(exc, "response", None)  # botocore ClientError carries the service code
            code = error.get("Error", {}).get("Code") if isinstance(error, dict) else None
            if code in _MISSING_CODES:
                logger.warning("Fixture %r is missing from bucket %r", reference, self.bucket)
                raise FixtureNotFound(reference) from exc
            logger.error("Fixture %r could not be read from bucket %r: %s", reference, self.bucket, exc)
            raise FixtureProviderError(f"Fixture {reference!r} could not be read") from exc
        if not isinstance(content, bytes):
            raise FixtureProviderError(f"Fixture {reference!r} did not produce bytes")
        return content
