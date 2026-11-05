"""Create the development fixture bucket and upload a directory into it.

Used by the development Compose stack (its ``storage-init`` service): every file
under DIRECTORY becomes the object whose key is its relative POSIX path, which is
the ``reference`` a definition's fixture names. Re-running is harmless. It reads
the fixture-store variables the hosts read (docs/operate/configuration.md):
EXTERNAL_ASSETS_BUCKET_NAME, S3_ENDPOINT_URL, AWS_REGION and the AWS credentials.

    python scripts/seed_fixture_store.py examples/fixtures
"""
import argparse
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, ConnectionClosedError, EndpointConnectionError

READY_SECONDS = 60.0


def seed(client, bucket, directory):
    """Create ``bucket`` unless it exists, then upload every file under ``directory``."""
    try:
        client.create_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise
    keys = []
    for path in sorted(item for item in Path(directory).rglob("*") if item.is_file()):
        key = path.relative_to(directory).as_posix()
        client.put_object(Bucket=bucket, Key=key, Body=path.read_bytes())
        keys.append(key)
    return keys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    bucket = os.environ.get("EXTERNAL_ASSETS_BUCKET_NAME")
    if not bucket:
        parser.error("set EXTERNAL_ASSETS_BUCKET_NAME")
    client = boto3.session.Session().client(
        "s3", endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
        region_name=os.environ.get("AWS_REGION") or "us-east-1")
    deadline = time.monotonic() + READY_SECONDS
    while True:  # The emulator starts with the stack; wait until it answers.
        try:
            keys = seed(client, bucket, args.directory)
            break
        except (EndpointConnectionError, ConnectionClosedError):
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)
    print(f"Seeded s3://{bucket} with {len(keys)} object(s): {', '.join(keys)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
