from abc import ABC, abstractmethod


class FileStorage(ABC):
    """
    Storage backend for uploaded paper files. Services depend on this
    rather than a concrete backend, so swapping local disk for S3 later
    is a change to the dependency wiring and nothing else.
    """

    @abstractmethod
    def save(self, *, key: str, content: bytes) -> None:
        """Write `content` at `key`, overwriting anything already there."""

    @abstractmethod
    def delete(self, *, key: str) -> None:
        """Remove `key`. Must not raise if it's already gone."""
