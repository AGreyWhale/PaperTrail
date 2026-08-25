from storage3.exceptions import StorageApiError
from supabase import Client, create_client

from app.storage.base import FileStorage

#Supabase returns "not found" as a 404-ish API error rather than a distinct
#exception type, so it has to be recognised from the message/status.
_NOT_FOUND_MARKERS = ("not_found", "not found", "does not exist", "404")


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
        self._bucket_name = bucket
        self._client = client or create_client(url, service_role_key)

    @property
    def _bucket(self):
        return self._client.storage.from_(self._bucket_name)

    def save(self, *, key: str, content: bytes) -> None:
        #upsert, because re-uploading a PDF reuses the same key per paper and
        #must overwrite rather than fail on a duplicate
        self._bucket.upload(
            key, content, {"content-type": "application/pdf", "upsert": "true"}
        )

    def read(self, *, key: str) -> bytes:
        return self._bucket.download(key)

    def delete(self, *, key: str) -> None:
        try:
            self._bucket.remove([key])
        except StorageApiError as error:
            #The interface promises delete is idempotent
            if not _is_not_found(error):
                raise
