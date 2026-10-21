"""The R2 implementation against the FileStorage contract, using a fake S3
client — no network, no credentials."""
import io

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.api.papers import get_file_storage
from app.core.config import get_settings
from app.storage.base import (
    FileNotFoundInStorageError,
    StorageNotConfiguredError,
    StorageUnavailableError,
)
from app.storage.r2_storage import R2FileStorage


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "Operation")


class FakeS3Client:
    def __init__(
        self,
        fail_delete_with: Exception | None = None,
        fail_get_with: Exception | None = None,
        fail_put_with: Exception | None = None,
    ):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.puts: list[dict] = []
        self._fail_delete_with = fail_delete_with
        self._fail_get_with = fail_get_with
        self._fail_put_with = fail_put_with

    def put_object(self, **kwargs):
        if self._fail_put_with:
            raise self._fail_put_with
        self.puts.append(kwargs)
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

    def get_object(self, *, Bucket, Key):
        if self._fail_get_with:
            raise self._fail_get_with
        if (Bucket, Key) not in self.objects:
            raise _client_error("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def delete_object(self, *, Bucket, Key):
        if self._fail_delete_with:
            raise self._fail_delete_with
        self.objects.pop((Bucket, Key), None)


def _storage(client: FakeS3Client, bucket: str = "papers") -> R2FileStorage:
    return R2FileStorage(
        account_id="account",
        access_key_id="key-id",
        secret_access_key="secret",
        bucket=bucket,
        client=client,
    )


# --- the factory flag ---

def test_factory_builds_r2_storage_when_flagged(monkeypatch):
    monkeypatch.setattr(get_settings(), "storage_backend", "r2")
    assert isinstance(get_file_storage(), R2FileStorage)


# --- the FileStorage contract, against a fake client ---

def test_save_then_read_round_trips():
    storage = _storage(FakeS3Client())

    storage.save(key="papers/abc/original.pdf", content=b"%PDF-1.4 hello")

    assert storage.read(key="papers/abc/original.pdf") == b"%PDF-1.4 hello"


def test_save_writes_to_the_configured_bucket_as_a_pdf():
    client = FakeS3Client()
    _storage(client, bucket="my-bucket").save(key="a.pdf", content=b"x")

    assert client.puts[-1]["Bucket"] == "my-bucket"
    assert client.puts[-1]["ContentType"] == "application/pdf"


def test_save_overwrites_an_existing_object():
    storage = _storage(FakeS3Client())

    storage.save(key="papers/abc/original.pdf", content=b"first")
    storage.save(key="papers/abc/original.pdf", content=b"second")

    assert storage.read(key="papers/abc/original.pdf") == b"second"


def test_read_of_a_missing_key_raises_the_shared_not_found_error():
    with pytest.raises(FileNotFoundInStorageError):
        _storage(FakeS3Client()).read(key="never-existed.pdf")


def test_read_failure_names_r2s_error_code():
    storage = _storage(FakeS3Client(fail_get_with=_client_error("AccessDenied")))

    with pytest.raises(StorageUnavailableError, match="AccessDenied"):
        storage.read(key="a.pdf")


def test_save_with_bad_credentials_names_r2s_error_code():
    storage = _storage(FakeS3Client(fail_put_with=_client_error("InvalidAccessKeyId")))

    with pytest.raises(StorageUnavailableError, match="InvalidAccessKeyId"):
        storage.save(key="a.pdf", content=b"x")


def test_save_that_cannot_reach_r2_is_reported_as_unavailable():
    error = EndpointConnectionError(endpoint_url="https://bad.r2.cloudflarestorage.com")
    storage = _storage(FakeS3Client(fail_put_with=error))

    with pytest.raises(StorageUnavailableError, match="Could not reach R2"):
        storage.save(key="a.pdf", content=b"x")


def test_delete_removes_the_object():
    client = FakeS3Client()
    storage = _storage(client)
    storage.save(key="a.pdf", content=b"x")

    storage.delete(key="a.pdf")

    assert client.objects == {}


@pytest.mark.parametrize("code", ["NoSuchKey", "404"])
def test_delete_is_silent_when_the_object_is_already_gone(code):
    #The interface promises delete never raises for a missing key
    _storage(FakeS3Client(fail_delete_with=_client_error(code))).delete(key="gone.pdf")


def test_delete_still_raises_on_a_real_failure():
    storage = _storage(FakeS3Client(fail_delete_with=_client_error("AccessDenied")))

    with pytest.raises(StorageUnavailableError):
        storage.delete(key="a.pdf")


# --- configuration errors ---

def test_missing_settings_are_named_on_first_use_not_construction():
    storage = R2FileStorage(account_id="", access_key_id="k", secret_access_key="", bucket="papers")

    with pytest.raises(StorageNotConfiguredError, match="R2_ACCOUNT_ID, R2_SECRET_ACCESS_KEY are not set"):
        storage.read(key="a.pdf")
