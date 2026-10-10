"""Explicit host secret lookup; configuration is captured by the host."""
import json
import boto3


def fetch_secret(name: str, key: str, region: str):
    client = boto3.session.Session().client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=name)
    return json.loads(response["SecretString"])[key]
