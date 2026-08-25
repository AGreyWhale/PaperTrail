"""
Exercises a real Supabase Storage bucket.

Skipped by default, like the pgvector tests: the rest of the suite runs with
no network and no credentials, and that property is worth keeping. Run with
`make test-supabase` once the SUPABASE_* values are set and the bucket exists
(create it as PRIVATE in the dashboard — this suite will not create it).

Credentials are read through Settings rather than os.environ, so putting them
in backend/.env is enough — the same place every other setting lives.
"""
import uuid

import pytest

from app.core.config import get_settings
from app.storage.supabase_storage import SupabaseFileStorage

_settings = get_settings()
SUPABASE_URL = _settings.supabase_url
SERVICE_ROLE_KEY = _settings.supabase_service_role_key
BUCKET = _settings.supabase_storage_bucket

# skipif rather than a module-level skip: the tests still get collected, so a
# run without credentials reports "skipped" and exits 0 instead of pytest's
# "no tests collected" exit code 5, which read as a build failure.
pytestmark = [
    pytest.mark.supabase,
    pytest.mark.skipif(
        not (SUPABASE_URL and SERVICE_ROLE_KEY and BUCKET),
        reason="set SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_STORAGE_BUCKET in backend/.env",
    ),
]

_PDF = b"%PDF-1.4\n%%EOF"


@pytest.fixture()
def storage():
    return SupabaseFileStorage(
        url=SUPABASE_URL, service_role_key=SERVICE_ROLE_KEY, bucket=BUCKET
    )


@pytest.fixture()
def key(storage):
    #Namespaced per run so a failed test can't collide with the next one
    path = f"pytest/{uuid.uuid4()}/original.pdf"
    yield path
    storage.delete(key=path)


def test_save_then_read_round_trips_real_bytes(storage, key):
    storage.save(key=key, content=_PDF)

    assert storage.read(key=key) == _PDF


def test_save_overwrites_an_existing_object(storage, key):
    storage.save(key=key, content=b"%PDF-1.4 first")
    storage.save(key=key, content=b"%PDF-1.4 second")

    assert storage.read(key=key) == b"%PDF-1.4 second"


def test_delete_removes_the_object(storage, key):
    storage.save(key=key, content=_PDF)

    storage.delete(key=key)

    with pytest.raises(Exception):
        storage.read(key=key)


def test_delete_is_idempotent_against_the_real_api(storage):
    #The contract says delete must not raise for a key that isn't there
    storage.delete(key=f"pytest/{uuid.uuid4()}/never-existed.pdf")
