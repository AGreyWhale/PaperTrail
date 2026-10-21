from pathlib import Path

from app.core.config import Settings
from app.storage.base import FileStorage
from app.storage.local import LocalFileStorage
from app.storage.r2_storage import R2FileStorage
from app.storage.supabase_storage import SupabaseFileStorage


def build_file_storage(settings: Settings) -> FileStorage:
    #Shared by the FastAPI dependency and the background pipeline, which runs
    #outside a request and so can't use Depends
    if settings.storage_backend == "r2":
        return R2FileStorage(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=settings.r2_bucket,
        )
    if settings.storage_backend == "supabase":
        return SupabaseFileStorage(
            url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket=settings.supabase_storage_bucket,
        )
    return LocalFileStorage(root=Path(settings.local_storage_root))
