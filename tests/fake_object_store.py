"""A deterministic in-memory stand-in for the S3 client used by fixture hosts.

It speaks the subset of the boto3 ``get_object`` contract the host provider
uses, including botocore's real error and streaming-body types, so tests reach
the same code paths as production without network access or AWS credentials.
"""
import io
from threading import Lock

from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.response import StreamingBody


class FakeS3Client:
    def __init__(self, objects=None, *, bucket="fixtures"):
        self.bucket = bucket
        self.objects = dict(objects or {})
        self.unreachable = False
        self.requests = []
        self._lock = Lock()

    def get_object(self, *, Bucket, Key):  # pylint: disable=invalid-name  # boto3 keyword names
        with self._lock:
            self.requests.append((Bucket, Key))
        if self.unreachable:
            raise EndpointConnectionError(endpoint_url="http://fake-s3.invalid")
        if Bucket != self.bucket:
            raise ClientError({"Error": {"Code": "NoSuchBucket", "Message": "no bucket"},
                               "ResponseMetadata": {"HTTPStatusCode": 404}}, "GetObject")
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "no key"},
                               "ResponseMetadata": {"HTTPStatusCode": 404}}, "GetObject")
        content = self.objects[Key]
        return {"Body": StreamingBody(io.BytesIO(content), len(content)), "ContentLength": len(content)}


def fake_s3_provider(objects=None, *, bucket="fixtures"):
    """Return ``(provider, client)`` wired exactly as a host would compose it."""
    from execution_host.fixtures import S3FixtureProvider
    client = FakeS3Client(objects, bucket=bucket)
    return S3FixtureProvider(bucket=bucket, client_factory=lambda: client), client
