"""Storage service for media-worker — downloads/uploads files from MinIO."""

import logging
import os
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Handles downloading files from and uploading files to MinIO/S3."""

    def __init__(self):
        self._client = None
        Path(settings.TEMP_DIR).mkdir(parents=True, exist_ok=True)

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION,
                config=BotoConfig(signature_version="s3v4"),
            )
        return self._client

    def download_to_local(self, object_key: str, local_filename: str | None = None) -> str:
        """Download a file from MinIO to /tmp/media/.

        Returns the local file path.
        """
        if local_filename is None:
            local_filename = os.path.basename(object_key)

        local_path = os.path.join(settings.TEMP_DIR, local_filename)

        logger.info(f"Downloading {object_key} → {local_path}")
        self.client.download_file(
            Bucket=settings.S3_BUCKET_NAME,
            Key=object_key,
            Filename=local_path,
        )
        file_size = os.path.getsize(local_path)
        logger.info(f"Downloaded {object_key} ({file_size} bytes)")
        return local_path

    def upload_from_local(self, local_path: str, object_key: str):
        """Upload a local file to MinIO."""
        logger.info(f"Uploading {local_path} → {object_key}")
        self.client.upload_file(
            Filename=local_path,
            Bucket=settings.S3_BUCKET_NAME,
            Key=object_key,
        )
        logger.info(f"Uploaded {local_path} → {object_key}")

    def get_object_size(self, object_key: str) -> int:
        """Get the size of an object in bytes."""
        try:
            response = self.client.head_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_key,
            )
            return response.get("ContentLength", 0)
        except ClientError:
            return 0


storage_service = StorageService()
