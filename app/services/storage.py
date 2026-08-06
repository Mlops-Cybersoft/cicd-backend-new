from functools import lru_cache
from io import BytesIO

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.config import settings


class S3Storage:
    def __init__(self) -> None:
        client_options: dict = {
            "service_name": "s3",
            "region_name": settings.s3_region,
            "use_ssl": settings.s3_use_ssl,
        }

        if settings.s3_endpoint_url:
            client_options["endpoint_url"] = settings.s3_endpoint_url

        # Prefer the normal AWS credential chain (IAM role, ECS task role,
        # EC2 instance profile, ~/.aws/credentials). Explicit credentials are
        # only supplied when the application settings contain a complete pair.
        if settings.s3_access_key_id and settings.s3_secret_access_key:
            client_options["aws_access_key_id"] = settings.s3_access_key_id
            client_options["aws_secret_access_key"] = settings.s3_secret_access_key
            if settings.s3_session_token:
                client_options["aws_session_token"] = settings.s3_session_token

        self.client: BaseClient = boto3.client(**client_options)
        self.bucket = settings.s3_bucket
        self._bucket_verified = False

    def verify_bucket_access(self) -> None:
        if self._bucket_verified:
            return

        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(
                f"Không thể truy cập AWS S3 bucket '{self.bucket}' "
                f"(AWS error: {error_code}). Hãy kiểm tra bucket, region và IAM policy."
            ) from exc

        self._bucket_verified = True

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.verify_bucket_access()
        self.client.upload_fileobj(
            BytesIO(data),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    def download_bytes(self, key: str) -> bytes:
        result = self.client.get_object(Bucket=self.bucket, Key=key)
        return result["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def create_download_url(self, key: str, filename: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=settings.s3_presigned_expiry_seconds,
        )


@lru_cache
def get_storage() -> S3Storage:
    return S3Storage()
