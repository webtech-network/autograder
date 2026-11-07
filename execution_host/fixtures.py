"""Host-owned fixture retrieval: one logical reference in, its exact bytes out.

There is deliberately no cache. Every call asks the configured object store for
the current object, so distinct references cannot share content, replacing an
object is visible to the next grading run, and an empty object is ordinary
content. Placement, destination paths and read-only modes belong to the
execution session, not to retrieval.

Failures are classified by whether they can pass without an operator: a missing
key is ``FixtureNotFound`` (the assignment is wrong); a missing or refused bucket
or credentials is the non-retryable ``FIXTURE_PROVIDER_UNAVAILABLE`` (the host is
misconfigured); anything else, such as transport errors, throttling or a 5xx, is a
``FixtureProviderError`` that preparation reports as retryable.
"""
import logging
import os
from threading import Lock

from botocore.exceptions import NoCredentialsError, PartialCredentialsError

from autograder.models.capabilities import FixtureNotFound
from autograder.models.evaluation_error import EvaluationError

logger = logging.getLogger(__name__)

_MISSING_CODES = frozenset({"NoSuchKey", "404", "NotFound"})
#: Store answers that stay the same until an operator changes the bucket, its
#: policy or the credentials: retrying them would only delay the failure.
_MISCONFIGURED_CODES = frozenset({
    "NoSuchBucket", "InvalidBucketName", "AccessDenied", "AllAccessDisabled", "403",
    "InvalidAccessKeyId", "SignatureDoesNotMatch", "AuthorizationHeaderMalformed",
    "PermanentRedirect", "301",
})


def _store_unusable():
    return EvaluationError("FIXTURE_PROVIDER_UNAVAILABLE", "The fixture provider is unavailable.", "capability")


class FixtureProviderError(RuntimeError):
    """The store could not be asked or did not answer; the reference may exist (transient)."""


class S3FixtureProvider:
    """Read one object per logical reference from one bucket.

    Configuration is captured at construction; the SDK client is created on the
    first selected fixture and then reused for the provider's lifetime.
    ``client_factory`` lets a host (or a test) supply its own client.
    """

    def __init__(self, *, bucket, endpoint_url=None, region="us-east-1",
                 access_key=None, secret_key=None, client_factory=None):
        if not bucket:
            raise ValueError("A fixture provider needs a bucket")
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.region = region
        self._credentials = (access_key, secret_key)
        self._client_factory = client_factory or self._boto3_client
        self._client = None
        self._lock = Lock()

    @classmethod
    def from_environment(cls, environ=None, **overrides):
        """Read the store settings once; ``None`` when no bucket is named.

        Without ``EXTERNAL_ASSETS_BUCKET_NAME`` the host supplies no fixture store,
        so a fixture assignment fails with the non-retryable
        ``FIXTURE_PROVIDER_UNAVAILABLE``. An endpoint without a bucket is a
        misconfigured store, not an absent one, so it stops the host at startup.
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
        if not bucket:
            return None
        return cls(bucket=bucket, endpoint_url=endpoint_url, region=config.get("AWS_REGION") or "us-east-1",
                   access_key=access_key, secret_key=secret_key, **overrides)

    def _boto3_client(self):
        import boto3
        from botocore.config import Config
        access_key, secret_key = self._credentials
        return boto3.session.Session().client(
            "s3", endpoint_url=self.endpoint_url, region_name=self.region,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key,
            # One request per fixture: the HTTP host's job retry is the only retry layer.
            config=Config(signature_version="s3v4", retries={"total_max_attempts": 1}))

    def _get_client(self):
        with self._lock:
            if self._client is None:
                self._client = self._client_factory()
            return self._client

    def __call__(self, reference: str) -> bytes:
        """Return the object's bytes (possibly empty).

        Raises ``FixtureNotFound`` when the bucket has no such key, the
        non-retryable ``FIXTURE_PROVIDER_UNAVAILABLE`` ``EvaluationError`` when
        the store refuses the bucket or the credentials, and
        ``FixtureProviderError`` for transport or other service failures.
        """
        try:
            response = self._get_client().get_object(Bucket=self.bucket, Key=reference)
            body = response["Body"]
            try:
                content = body.read()
            finally:
                body.close()
        except (NoCredentialsError, PartialCredentialsError) as exc:
            logger.error("Fixture bucket %r cannot be read: no usable credentials (%s)", self.bucket, exc)
            raise _store_unusable() from exc
        except Exception as exc:
            error = getattr(exc, "response", None)  # botocore ClientError carries the service code
            code = error.get("Error", {}).get("Code") if isinstance(error, dict) else None
            if code in _MISSING_CODES:
                logger.warning("Fixture %r is missing from bucket %r", reference, self.bucket)
                raise FixtureNotFound(reference) from exc
            if code in _MISCONFIGURED_CODES:
                logger.error("Fixture bucket %r refuses this host (%s); fix the bucket, its policy or the "
                             "credentials", self.bucket, code)
                raise _store_unusable() from exc
            logger.error("Fixture %r could not be read from bucket %r: %s", reference, self.bucket, exc)
            raise FixtureProviderError(f"Fixture {reference!r} could not be read") from exc
        if not isinstance(content, bytes):
            raise FixtureProviderError(f"Fixture {reference!r} did not produce bytes")
        return content
