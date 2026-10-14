import boto3
from botocore.exceptions import ClientError
from botocore.client import Config

import os

endpoint_url = os.getenv('S3_ENDPOINT_URL', 'https://s3.ir-thr-at1.arvanstorage.ir')
access_key = os.getenv('S3_ACCESS_KEY', 'your-access-key')
secret_key = os.getenv('S3_SECRET_KEY', 'your-secret-key')
bucket_name = os.getenv('S3_BUCKET_NAME', 'content-repurposing-crp')

s3 = boto3.client(
    's3',
    endpoint_url=endpoint_url,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    config=Config(signature_version='s3')
)

try:
    s3.list_buckets()
    print("List buckets successful!")
except Exception as e:
    print("List buckets failed:", e)

