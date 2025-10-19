# If you need more information about configurations
# or implementing the sample code, visit the AWS docs:
# https://aws.amazon.com/developer/language/python/

import boto3
import os
import json
from botocore.exceptions import ClientError

def get_secret(secret_key : str, secret_name : str = None, region : str = "us-east-1"):
    """
    Fetches a secret value, adapting to the environment.
    In 'development', it reads from local environment variables using `secret_key`.
    In 'production', it fetches from AWS Secrets Manager using all parameters.

    Meant to be used for sensitive info, such as passwords and API keys.

    :param secret_key: str - The key for the secret value. Used as the environment variable
                         name in development and the key in the JSON secret in production.
    :param secret_name: str (optional) - The name of the secret in AWS Secrets Manager.
                          Required for production environment.
    :param region: str (optional) - The AWS region where the secret is stored.
                     Defaults to 'us-east-1'.
    :return: Str - The value of the secret.
    """
    # Default to 'development' if the variable isn't set
    app_environment = os.environ.get('ENVIRONMENT', 'development')

    if app_environment == 'production':
        if not secret_name:
            raise ValueError("The 'secret_name' argument is required for the 'production' environment when fetching a secret")
        # In production, get the key from Secrets Manager
        return _get_secret_from_manager(secret_name, secret_key, region)
    else:
        # In development, get the key from a local environment variable
        print("Fetching secret from local environment variable...")
        api_key = os.environ.get(secret_key)
        if not api_key:
            raise ValueError("Environment variable not set for development.")
        return api_key

def _get_secret_from_manager(secret_name : str, secret_key : str, region : str):
    """
    Fetches a specific key from a secret stored in AWS Secrets Manager.

    This function connects to AWS, retrieves a secret's value, which is
    expected to be a JSON string. It then parses the JSON and returns the
    value associated with the provided secret_key.

    :param secret_name: str - The name or ARN of the secret in AWS Secrets Manager.
    :param secret_key: str - The key within the JSON secret string whose value is to be returned.
    :param region: str - The AWS region where the secret is stored.
    :return: str - The value of the requested secret key.
    :raises: botocore.exceptions.ClientError - If the AWS API call fails for reasons
                                             like permissions or secret not found.
    :raises: KeyError - If the secret_key is not found in the secret's JSON content.
    """

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret_str = get_secret_value_response['SecretString']
    secret_json = json.loads(secret_str)
    api_key = secret_json[secret_key]
    return api_key
