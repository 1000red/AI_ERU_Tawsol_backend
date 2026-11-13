"""Neon Object Storage Service.

S3-compatible object storage that branches with the database.
Uses boto3 with path-style addressing as required by Neon Object Storage.
"""

import os
import logging
from typing import BinaryIO, Optional, Tuple
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class NeonStorageService:
    def __init__(self):
        self.endpoint_url = settings.AWS_ENDPOINT_URL_S3
        self.access_key_id = settings.AWS_ACCESS_KEY_ID
        self.secret_access_key = settings.AWS_SECRET_ACCESS_KEY
        self.region_name = settings.AWS_REGION or "us-east-2"
        self.bucket_name = settings.NEON_STORAGE_BUCKET or "assets"
        self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint_url and self.access_key_id and self.secret_access_key)

    @property
    def client(self):
        if self._client is None and self.is_configured:
            # Neon requires path-style addressing
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region_name,
                verify=False,
                config=Config(
                    s3={"addressing_style": "path"},
                    signature_version="s3v4",
                    connect_timeout=10,
                    read_timeout=30,
                    retries={"max_attempts": 3},
                ),
            )
        return self._client

    def upload_file(
        self,
        file_obj: BinaryIO,
        object_key: str,
        content_type: str = "application/octet-stream",
    ) -> Tuple[bool, str]:
        """Upload a file stream to the Neon bucket. Returns (success, url_or_error)."""
        if not self.is_configured:
            return False, "Neon Object Storage is not configured"

        try:
            self.client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_key,
                ExtraArgs={"ContentType": content_type},
            )
            file_url = f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{object_key}"
            return True, file_url
        except Exception as e:
            logger.error(f"Failed to upload to Neon Object Storage: {e}")
            return False, str(e)

    def download_file(self, object_key: str) -> Optional[bytes]:
        """Download an object from the Neon bucket."""
        if not self.is_configured:
            return None

        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to download object {object_key}: {e}")
            return None

    def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> Optional[str]:
        """Generate a presigned GET URL for private objects."""
        if not self.is_configured:
            return None

        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {object_key}: {e}")
            return None

    def list_objects(self, prefix: str = "") -> list[str]:
        """List object keys under the prefix."""
        if not self.is_configured:
            return []

        try:
            response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            contents = response.get("Contents", [])
            return [obj["Key"] for obj in contents]
        except Exception as e:
            logger.error(f"Failed to list objects: {e}")
            return []


neon_storage = NeonStorageService()
