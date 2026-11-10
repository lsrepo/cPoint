#!/usr/bin/env python3
"""Upload podcast enclosure files to Cloudflare R2 via the S3 API.
boto3 is imported lazily so check scripts that never upload don't need it."""


def upload_file(local_path, key, content_type, *, account_id, access_key, secret_key, bucket):
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )
    client.upload_file(
        local_path,
        bucket,
        key,
        ExtraArgs={
            "ContentType": content_type,
            "CacheControl": "public, max-age=31536000, immutable",
        },
    )
