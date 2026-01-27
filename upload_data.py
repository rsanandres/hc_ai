#!/usr/bin/env python
"""
Upload local data directory to S3 bucket `hc-ai.bucket` in `us-east-2`.

Usage (from project root):

    python upload_data.py

Defaults:
- Source directory: ./data
- Bucket: hc-ai.bucket
- Region: us-east-2

You can override via CLI:

    python upload_data.py --source ./data/fhir --bucket hc-ai.bucket --prefix fhir/

AWS credentials are resolved via the standard AWS mechanisms:
- Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
- Shared credentials file (~/.aws/credentials)
- IAM role (if running on AWS)
"""

from __future__ import annotations

import argparse
import mimetypes
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

import boto3
from botocore.exceptions import BotoCoreError, ClientError

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

DEFAULT_BUCKET = "hc-ai.bucket"
DEFAULT_SOURCE = "data"


def _guess_content_type(path: Path) -> str:
    ctype, _ = mimetypes.guess_type(str(path))
    return ctype or "application/octet-stream"


def upload_directory(
    source_dir: Path,
    bucket: str,
    prefix: str = "",
    region: str = AWS_REGION,
) -> None:
    """Upload all files under source_dir to S3."""
    if not source_dir.exists() or not source_dir.is_dir():
        raise ValueError(f"Source directory does not exist or is not a directory: {source_dir}")

    session = boto3.Session(region_name=region)
    s3 = session.client("s3")

    total = 0
    for root, _, files in os.walk(source_dir):
        root_path = Path(root)
        for name in files:
            local_path = root_path / name
            rel_path = local_path.relative_to(source_dir)
            key = f"{prefix.rstrip('/')}/{rel_path.as_posix()}" if prefix else rel_path.as_posix()

            extra_args = {"ContentType": _guess_content_type(local_path)}

            print(f"Uploading {local_path} -> s3://{bucket}/{key} ({extra_args['ContentType']})")
            try:
                s3.upload_file(str(local_path), bucket, key, ExtraArgs=extra_args)
            except (BotoCoreError, ClientError) as e:
                print(f"FAILED to upload {local_path}: {e}")
            else:
                total += 1

    print(f"Completed upload. Total files uploaded: {total}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload local data directory to S3.")
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"Source directory to upload (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"S3 bucket name (default: {DEFAULT_BUCKET})",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Optional S3 key prefix to prepend to all uploaded objects",
    )
    parser.add_argument(
        "--region",
        default=AWS_REGION,
        help=f"AWS region for S3 client (default: {AWS_REGION})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = Path(args.source).resolve()

    try:
        upload_directory(source_dir=source_dir, bucket=args.bucket, prefix=args.prefix, region=args.region)
    except Exception as e:  # noqa: BLE001
        print(f"Error during upload: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

