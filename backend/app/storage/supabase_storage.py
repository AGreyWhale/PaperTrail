from storage3.exceptions import StorageApiError
from supabase import Client, create_client

from app.storage.base import FileNotFoundInStorageError, FileStorage

#Supabase returns "not found" as a 404-ish API error rather than a distinct
#exception type, so it has to be recognised from the message/status.
_NOT_FOUND_MARKERS = ("not_found", "not found", "does not exist", "404")


class StorageNotConfiguredError(RuntimeError):
    """Raised when the Supabase backend is selected but its settings are blank.
    Names the missing variables, rather than the SDK's bare 'supabase_url is
    required'."""


def _is_not_found(error: StorageApiError) -> bool:
    haystack = f"{getattr(error, 'code', '')} {getattr(error, 'status', '')} {error}".lower()
    return any(marker in haystack for marker in _NOT_FOUND_MARKERS)


class SupabaseFileStorage(FileStorage):
    """Stores paper files in a Supabase Storage bucket.

    The bucket is private and stays that way: every read goes through the
    backend using the service role key, so ownership is still checked in
    PaperService before any bytes are touched. Handing out signed or public
    URLs would move that boundary outside the app."""

    def __init__(self, *, url: str, service_role_key: str, bucket: str, client: Client | None = None):
        #Accepts a pre-built client so tests can inject a fake
        self._url = url
        self._service_role_key = service_role_key
        self._bucket_name = bucket
        self._client = client

    def _ensure_client(self) -> Client:
        #Built on first real use, not in __init__. PaperService takes a
        #FileStorage for every endpoint it serves, so constructing eagerly made
        #"create a paper" — which touches no files — die on missing storage
        #credentials with an unreadable SDK error.
        if self._client is None:
            missing = [
                name
                for name, value in (
                    ("SUPABASE_URL", self._url),
                    ("SUPABASE_SERVICE_ROLE_KEY", self._service_role_key),
                    ("SUPABASE_STORAGE_BUCKET", self._bucket_name),
                )
                if not value
            ]
            if missing:
                raise StorageNotConfiguredError(
                    "STORAGE_BACKEND is 'supabase' but "
                    f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not set"
                )
            self._client = create_client(self._url, self._service_role_key)
        return self._client

    @property
    def _bucket(self):
        return self._ensure_client().storage.from_(self._bucket_name)

    def save(self, *, key: str, content: bytes) -> None:
        #upsert, because re-uploading a PDF reuses the same key per paper and
        #must overwrite rather than fail on a duplicate
        self._bucket.upload(
            key, content, {"content-type": "application/pdf", "upsert": "true"}
        )

    def read(self, *, key: str) -> bytes:
        try:
            return self._bucket.download(key)
        except StorageApiError as error:
            #Same signal local disk gives, so callers don't branch on backend
            if _is_not_found(error):
                raise FileNotFoundInStorageError(key) from error
            raise

    def delete(self, *, key: str) -> None:
        try:
            self._bucket.remove([key])
        except StorageApiError as error:
            #The interface promises delete is idempotent
            if not _is_not_found(error):
                raise
