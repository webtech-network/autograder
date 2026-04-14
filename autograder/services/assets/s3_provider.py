import os
import logging
import boto3
from botocore.config import Config
from typing import Optional
from autograder.services.assets.provider import AssetProvider
from autograder.services.assets.cache_manager import AssetCacheManager

logger = logging.getLogger("S3AssetProvider")

class S3AssetProvider(AssetProvider):
    def __init__(self, cache_manager: AssetCacheManager):
        self.cache_manager = cache_manager
        
        # Environment variables
        self.bucket_name = os.getenv("CRITERIA_ASSETS_BUCKET_NAME")
        self.access_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_ID")
        self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.endpoint_url = os.getenv("S3_ENDPOINT_URL")
        
        # Initialize boto3 client
        self.s3 = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(signature_version='s3v4')
        )
        
    def get_asset(self, source: str, target: str, read_only: bool = True) -> Optional[bytes]:
        """
        Fetch asset from S3 and return raw content (cached).
        """
        # Create a unique cache key based on source
        # (target and read_only no longer affect the content itself)
        cache_key = f"{source}.raw".replace('/', '_')
        
        # Check cache
        cached_content = self.cache_manager.get(cache_key)
        if cached_content:
            logger.debug("Cache hit for %s", cache_key)
            return cached_content
            
        # Fetch from S3
        logger.info("Fetching asset from S3: %s", source)
        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=source)
            raw_content = response['Body'].read()
            
            # Store in cache
            self.cache_manager.put(cache_key, raw_content)
            
            return raw_content
        except Exception as e:
            logger.error("Failed to fetch asset from S3 (%s): %s", source, str(e))
            return None
