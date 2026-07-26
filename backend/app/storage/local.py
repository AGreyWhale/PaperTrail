from pathlib import Path

from app.storage.base import FileStorage

class LocalFileStorage(FileStorage):
    #Stores files localy until we set up production that'll use a S3-compatible backend
    
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
    
    def _path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ValueError(f"Invalid storage key: {key!r}")
        return path
    
    def save(self, *, key: str, content: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    
    def delete(self, *, key: str) -> None:
        path = self._path_for(key)
        path.unlink(missing_ok=True)
    
    def read(self, *, key: str) -> bytes:
        return self._path_for(key).read_bytes()