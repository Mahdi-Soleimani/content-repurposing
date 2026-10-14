"""S3/MinIO storage service.

Handles:
- Presigned URL generation (upload & download)
- Object existence verification
- Object metadata retrieval
- Bucket management (create, set public policy)
- Public URL generation
"""

import json
import logging

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Handles S3-compatible object storage operations."""

    def __init__(self):
        self._client = None

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

    @property
    def presigned_client(self):
        """A dedicated client for generating presigned URLs with the correct public host header."""
        return boto3.client(
            "s3",
            endpoint_url=settings.S3_PUBLIC_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=BotoConfig(signature_version="s3v4"),
        )

    # ──── Bucket Management ────

    def ensure_bucket_exists(self) -> bool:
        """Create the S3 bucket if it doesn't exist and set CORS."""
        try:
            self.client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                self.client.create_bucket(Bucket=settings.S3_BUCKET_NAME)
                logger.info(f"Created S3 bucket: {settings.S3_BUCKET_NAME}")
            else:
                raise e

        # Always ensure CORS is set correctly
        cors_configuration = {
            "CORSRules": [{
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["GET", "PUT", "POST", "HEAD"],
                "AllowedOrigins": ["*"],
                "ExposeHeaders": ["ETag"]
            }]
        }
        self.client.put_bucket_cors(
            Bucket=settings.S3_BUCKET_NAME,
            CORSConfiguration=cors_configuration
        )

    def set_bucket_public_read(self):
        """Set bucket policy to allow public read access.

        This is necessary so uploaded files can be accessed publicly
        for processing by other services and n8n.
        """
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [
                        f"arn:aws:s3:::{settings.S3_BUCKET_NAME}/*"
                    ],
                }
            ],
        }
        self.client.put_bucket_policy(
            Bucket=settings.S3_BUCKET_NAME,
            Policy=json.dumps(policy),
        )
        logger.info(f"Public read policy set on bucket '{settings.S3_BUCKET_NAME}'")

    # ──── Presigned URLs ────

    def generate_presigned_upload_url(
        self,
        object_key: str,
        content_type: str = "application/octet-stream",
        expires_in: int = 900,
    ) -> str:
        """Generate a presigned URL for direct upload from browser."""
        return self.presigned_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned URL for downloading an object."""
        return self.presigned_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": object_key,
            },
            ExpiresIn=expires_in,
        )

    # ──── Object Verification ────

    def verify_object_exists(self, object_key: str) -> bool:
        """Check if an object exists in the bucket."""
        try:
            self.client.head_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_key,
            )
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                return False
            logger.error(f"S3 ClientError verifying object {object_key}: {e}")
            raise

    def get_object_metadata(self, object_key: str) -> dict | None:
        """Get metadata (size, content_type, etc.) of an object.

        Returns None if the object doesn't exist.
        """
        try:
            response = self.client.head_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_key,
            )
            return {
                "content_length": response.get("ContentLength", 0),
                "content_type": response.get("ContentType", ""),
                "last_modified": str(response.get("LastModified", "")),
                "etag": response.get("ETag", "").strip('"'),
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                return None
            logger.error(f"S3 ClientError getting metadata for {object_key}: {e}")
            raise

    # ──── Public URL ────

    def get_public_url(self, object_key: str) -> str:
        """Generate the public URL for an object.

        Uses S3_PUBLIC_URL (localhost:9000 for dev, Arvan domain for prod).
        """
        return f"{settings.S3_PUBLIC_URL}/{settings.S3_BUCKET_NAME}/{object_key}"

    # ──── Deletion ────

    def delete_object(self, object_key: str):
        """Delete a single object from the bucket."""
        try:
            self.client.delete_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_key,
            )
            logger.info(f"Deleted object from S3: {object_key}")
        except ClientError as e:
            logger.error(f"Failed to delete object {object_key}: {e}")
            raise

    def delete_objects_by_prefix(self, prefix: str):
        """Delete all objects with a specific prefix (e.g. projects/uuid/)."""
        try:
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=settings.S3_BUCKET_NAME, Prefix=prefix)

            objects_to_delete = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        objects_to_delete.append({"Key": obj["Key"]})

            if not objects_to_delete:
                logger.info(f"No objects found with prefix: {prefix}")
                return

            # Delete in batches of 1000 (S3 API limit)
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i:i + 1000]
                self.client.delete_objects(
                    Bucket=settings.S3_BUCKET_NAME,
                    Delete={"Objects": batch, "Quiet": True}
                )
                logger.info(f"Deleted {len(batch)} objects with prefix: {prefix}")
        except ClientError as e:
            logger.error(f"Failed to delete objects by prefix {prefix}: {e}")
            raise

    # ──── File Uploads ────
    
    def upload_fileobj(self, file_obj, object_key: str, content_type: str = "application/octet-stream"):
        """Upload a file-like object directly to S3."""
        try:
            self.client.upload_fileobj(
                file_obj,
                settings.S3_BUCKET_NAME,
                object_key,
                ExtraArgs={"ContentType": content_type}
            )
            logger.info(f"Uploaded object to S3: {object_key}")
        except ClientError as e:
            logger.error(f"Failed to upload object {object_key}: {e}")
            raise



storage_service = StorageService()
