"""Storage service for MinIO."""

import os
import boto3
from botocore.exceptions import ClientError
from app.config import settings

class StorageService:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        self.bucket = settings.S3_BUCKET_NAME

    def upload_file(self, file_path: str, object_key: str, content_type: str = "application/octet-stream") -> str:
        """Uploads a local file to S3 and returns the object key."""
        try:
            self.s3_client.upload_file(
                file_path, 
                self.bucket, 
                object_key,
                ExtraArgs={'ContentType': content_type}
            )
            return object_key
        except ClientError as e:
            raise RuntimeError(f"Failed to upload to S3: {e}")

    def download_file(self, object_key: str, file_path: str):
        """Downloads a file from S3 to the local filesystem."""
        try:
            self.s3_client.download_file(
                self.bucket,
                object_key,
                file_path
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                raise FileNotFoundError(f"Object {object_key} not found in bucket {self.bucket}")
            raise RuntimeError(f"Failed to download from S3: {e}")

storage_service = StorageService()
