"""Which backend the factory builds, and that the Supabase implementation
honours the FileStorage contract. Uses a fake Supabase client — no network,
no credentials. The real bucket is exercised in test_supabase_storage.py."""
from pathlib import Path

import pytest
from storage3.exceptions import StorageApiError

from app.api.papers import get_file_storage
from app.core.config import get_settings
from app.storage.local import LocalFileStorage
from app.storage.supabase_storage import SupabaseFileStorage


class FakeBucket:
    def __init__(self, fail_remove_with: Exception | None = None):
        self.files: dict[str, bytes] = {}
        self.uploads: list[tuple[str, bytes, dict]] = []
        self._fail_remove_with = fail_remove_with

    def upload(self, path, file, file_options=None):
        self.uploads.append((path, file, file_options or {}))
        self.files[path] = file

    def download(self, path):
        return self.files[path]

    def remove(self, paths):
        if self._fail_remove_with:
            raise self._fail_remove_with
        for p in paths:
            self.files.pop(p, None)


class FakeSupabaseClient:
    def __init__(self, bucket: FakeBucket):
        self._bucket = bucket
        self.requested_buckets: list[str] = []

    @property
    def storage(self):
        return self

    def from_(self, name):
        self.requested_buckets.append(name)
        return self._bucket


def _storage(bucket: FakeBucket) -> SupabaseFileStorage:
    return SupabaseFileStorage(
        url="https://example.supabase.co",
        service_role_key="service-role-key",
        bucket="papers",
        client=FakeSupabaseClient(bucket),
    )


def _api_error(message: str, status: int) -> StorageApiError:
    return StorageApiError(message=message, code=str(status), status=status)


# --- the factory flag ---

def test_factory_builds_local_storage_by_default(monkeypatch):
    monkeypatch.setattr(get_settings(), "storage_backend", "local")
    assert isinstance(get_file_storage(), LocalFileStorage)


def test_factory_builds_supabase_storage_when_flagged(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_backend", "supabase")
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", "service-role-key")

    assert isinstance(get_file_storage(), SupabaseFileStorage)


def test_local_storage_still_honours_its_configured_root(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "storage_backend", "local")
    monkeypatch.setattr(get_settings(), "local_storage_root", str(tmp_path))

    storage = get_file_storage()
    assert isinstance(storage, LocalFileStorage)
    assert storage.root == Path(str(tmp_path))


# --- the FileStorage contract, against a fake client ---

def test_save_then_read_round_trips():
    bucket = FakeBucket()
    storage = _storage(bucket)

    storage.save(key="papers/abc/original.pdf", content=b"%PDF-1.4 hello")

    assert storage.read(key="papers/abc/original.pdf") == b"%PDF-1.4 hello"


def test_save_uploads_to_the_configured_bucket():
    bucket = FakeBucket()
    client = FakeSupabaseClient(bucket)
    SupabaseFileStorage(
        url="u", service_role_key="k", bucket="my-bucket", client=client
    ).save(key="a.pdf", content=b"x")

    assert client.requested_buckets == ["my-bucket"]


def test_save_overwrites_rather_than_failing_on_a_repeat_upload():
    #Re-uploading a PDF reuses the same key per paper, so upsert is required
    bucket = FakeBucket()
    storage = _storage(bucket)

    storage.save(key="papers/abc/original.pdf", content=b"first")
    storage.save(key="papers/abc/original.pdf", content=b"second")

    assert storage.read(key="papers/abc/original.pdf") == b"second"
    assert bucket.uploads[-1][2].get("upsert") == "true"


def test_delete_removes_the_object():
    bucket = FakeBucket()
    storage = _storage(bucket)
    storage.save(key="a.pdf", content=b"x")

    storage.delete(key="a.pdf")

    assert bucket.files == {}


def test_delete_is_silent_when_the_object_is_already_gone():
    #The interface promises delete never raises for a missing key
    bucket = FakeBucket(fail_remove_with=_api_error("Object not found", 404))

    _storage(bucket).delete(key="never-existed.pdf")


@pytest.mark.parametrize("message,status", [("Object not_found", 400), ("does not exist", 404)])
def test_delete_tolerates_the_various_not_found_shapes(message, status):
    _storage(FakeBucket(fail_remove_with=_api_error(message, status))).delete(key="gone.pdf")


def test_delete_still_raises_on_a_real_failure():
    #A permissions or network problem must not be swallowed as "already gone"
    bucket = FakeBucket(fail_remove_with=_api_error("Unauthorized", 401))

    with pytest.raises(StorageApiError):
        _storage(bucket).delete(key="a.pdf")
