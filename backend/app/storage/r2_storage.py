import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.base import (
    FileNotFoundInStorageError,
    FileStorage,
    StorageNotConfiguredError,
    StorageUnavailableError,
)

#S3 reports a missing object as a ClientError, not a distinct exception type:
#"NoSuchKey" from get_object, a bare "404" from head-style calls.
_NOT_FOUND_CODES = {"NoSuchKey", "404", "NotFound"}


def _is_not_found(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") in _NOT_FOUND_CODES


def _unavailable(error: Exception) -> StorageUnavailableError:
    #ClientError carries R2's own code (InvalidAccessKeyId, NoSuchBucket, ...),
    #which is what actually tells you which setting is wrong
    if isinstance(error, ClientError):
        detail = error.response.get("Error", {})
        return StorageUnavailableError(
            f"R2 refused the request: {detail.get('Code')} {detail.get('Message', '')}".strip()
        )
    return StorageUnavailableError(f"Could not reach R2: {error}")


class R2FileStorage(FileStorage):
    """Stores paper files in a Cloudflare R2 bucket over its S3-compatible API.

    The bucket is private and stays that way: every read goes through the
    backend, so ownership is still checked in PaperService before any bytes
    are touched. Presigned or public URLs would move that boundary outside
    the app."""

    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        client=None,
    ):
        #Accepts a pre-built client so tests can inject a fake
        self._account_id = account_id
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._bucket = bucket
        self._client = client

    def _ensure_client(self):
        #Built on first real use, not in __init__, so endpoints that touch no
        #files don't die on missing storage credentials
        if self._client is None:
            missing = [
                name
                for name, value in (
                    ("R2_ACCOUNT_ID", self._account_id),
                    ("R2_ACCESS_KEY_ID", self._access_key_id),
                    ("R2_SECRET_ACCESS_KEY", self._secret_access_key),
                    ("R2_BUCKET", self._bucket),
                )
                if not value
            ]
            if missing:
                raise StorageNotConfiguredError(
                    "STORAGE_BACKEND is 'r2' but "
                    f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not set"
                )
            self._client = boto3.client(
                "s3",
                endpoint_url=f"https://{self._account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name="auto",
                #boto3 1.36+ sends CRC checksums on every upload by default,
                #which R2 has rejected in the past. Only send them when the
                #operation actually requires one.
                config=Config(
                    request_checksum_calculation="when_required",
                    response_checksum_validation="when_required",
                ),
            )
        return self._client

    def save(self, *, key: str, content: bytes) -> None:
        #put_object overwrites by default, which re-uploading a PDF relies on
        try:
            self._ensure_client().put_object(
                Bucket=self._bucket, Key=key, Body=content, ContentType="application/pdf"
            )
        except (ClientError, BotoCoreError) as error:
            raise _unavailable(error) from error

    def read(self, *, key: str) -> bytes:
        try:
            response = self._ensure_client().get_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            #Same signal local disk gives, so callers don't branch on backend
            if _is_not_found(error):
                raise FileNotFoundInStorageError(key) from error
            raise _unavailable(error) from error
        except BotoCoreError as error:
            raise _unavailable(error) from error
        return response["Body"].read()

    def delete(self, *, key: str) -> None:
        #S3's DeleteObject already succeeds for a missing key; the guard is for
        #S3-compatible stores that answer 404 instead
        try:
            self._ensure_client().delete_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if not _is_not_found(error):
                raise _unavailable(error) from error
        except BotoCoreError as error:
            raise _unavailable(error) from error
