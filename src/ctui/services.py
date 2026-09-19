"""Replaceable service contracts and in-memory or null implementations.

Keep transient runtime objects on CtuiApp attributes, named persistent profiles
in ConfigStore, and protocol interactions in RecordStore. Storage remains a
generic injectable key-value service; it is not the default project database.
CtuiApp selects project history when a backend exists, otherwise MemoryHistory,
and uses NullStorage unless an alternative is supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .commands import CommandError

_MISSING = object()


class StorageKeyError(CommandError, KeyError):
    """Report a missing required storage key as both KeyError and CommandError.

    This permits ordinary mapping-style handling while UI dispatch displays a
    concise popup. Supplying an explicit default to get(), including None,
    requests fallback behavior instead of this error.
    """

    def __init__(self, key: str):
        """Create a concise error suitable for terminal and popup display."""
        self.key = key
        CommandError.__init__(self, f"No stored value exists for {key!r}.")


@dataclass(frozen=True)
class HistoryEntry:
    """Immutable command text and its acceptance timestamp.

    Entries represent accepted dispatches, not every input edit or failed parse.
    Memory history uses local naive timestamps; project history reads stored
    timezone-aware timestamps. Consumers should respect the backend's timezone.
    """

    command: str
    timestamp: datetime


class HistoryStore(Protocol):
    """Structural interface for accepted-command history.

    Memory and null implementations are synchronous. CtuiApp and built-in
    history commands also await service results when needed, allowing project
    history to perform asynchronous I/O. This history is distinct from the
    prompt-toolkit input buffer's in-session editing history.
    """

    def append(self, command: str) -> None:
        """Store an accepted command."""
        ...

    def all(self) -> list[HistoryEntry]:
        """Return history entries in insertion order."""
        ...

    def clear(self) -> None:
        """Remove every stored history entry."""
        ...


class MemoryHistory:
    """Keep command history in process memory."""

    def __init__(self):
        """Create an empty history store."""
        self.entries: list[HistoryEntry] = []

    def append(self, command):
        """Append *command* with the current local time."""
        self.entries.append(HistoryEntry(command, datetime.now()))

    def all(self):
        """Return a shallow copy of all history entries."""
        return list(self.entries)

    def clear(self):
        """Remove all in-memory entries."""
        self.entries.clear()


class NullHistory:
    """Discard history for applications that disable command tracking."""

    def append(self, command):
        """Discard *command*."""
        pass

    def all(self):
        """Return an empty history list."""
        return []

    def clear(self):
        """Do nothing because no history is retained."""
        pass


class Storage(Protocol):
    """Structural interface for optional application key-value storage.

    get returns the stored value or an explicit default, including None; absent
    keys without a default raise StorageKeyError. CtuiApp closes the configured
    service at runtime shutdown and awaits close() if it returns an awaitable.
    Application code is responsible for any backend-specific async get/set use.
    """

    def get(self, key: str, default=_MISSING):
        """Return *key*, use an explicit default, or raise StorageKeyError."""
        ...

    def set(self, key: str, value) -> None:
        """Associate *value* with *key*."""
        ...

    def close(self) -> None:
        """Release resources owned by the backend."""
        ...


class ConfigStore(Protocol):
    """Structural interface for named persistent configuration profiles.

    Register templates synchronously before backend startup; read, save, and
    reset asynchronously. The built-in SQLite implementation stores JSON values
    and restores templates on reset. It additionally provides import/export and
    delete methods used by project commands; this minimal protocol does not
    promise those extensions for every injected store.
    """

    def register_template(self, name: str, values: dict[str, Any]) -> None:
        """Register an application-provided default profile.

        The built-in backend snapshots JSON-compatible values so later mutations
        of the caller's dictionary do not change the registered template.
        """
        ...

    async def list(self) -> dict[str, Any]:
        """Return all named configurations."""
        ...

    async def get(self, name: str) -> Any:
        """Return one named configuration."""
        ...

    async def save(self, name: str, values: Any) -> None:
        """Create or replace one named configuration."""
        ...

    async def reset(self) -> None:
        """Restore registered application templates."""
        ...


class RecordStore(Protocol):
    """Structural interface for append-oriented protocol records.

    Keep raw payload bytes alongside optional decoded data and metadata, grouped
    by optional recording sessions. The built-in backend uses JSON for decoded
    values and metadata and provides end_session as an additional operation.
    Protocol-specific interpretation and presentation belong to the application.
    """

    async def start_session(self, protocol: str, metadata: Any = None) -> int:
        """Create a protocol-recording session and return its identifier."""
        ...

    async def append(
        self,
        *,
        direction: str,
        protocol: str,
        payload: bytes = b"",
        session: int | None = None,
        decoded: Any = None,
        metadata: Any = None,
    ) -> int:
        """Append one protocol interaction and return its identifier."""
        ...

    async def query(
        self,
        *,
        session: int | None = None,
        direction: str | None = None,
        protocol: str | None = None,
        limit: int = 0,
    ) -> list[Any]:
        """Query records using generic protocol fields."""
        ...


class MemoryStorage:
    """Ephemeral dictionary-backed storage retaining supplied object references.

    No serialization or copying occurs. Missing keys require an explicit default
    or raise StorageKeyError; close() is a no-op and does not clear the dictionary.
    """

    def __init__(self):
        """Create an empty storage backend."""
        self.data = {}

    def get(self, key, default=_MISSING):
        """Return *key*, use an explicit default, or raise StorageKeyError."""
        if key in self.data:
            return self.data[key]
        if default is not _MISSING:
            return default
        raise StorageKeyError(key)

    def set(self, key, value):
        """Store *value* under *key*."""
        self.data[key] = value

    def close(self):
        """Do nothing because memory storage owns no external resources."""
        pass


class NullStorage:
    """Discard writes while preserving the missing-key contract.

    Every get requires an explicit default or raises StorageKeyError, even after
    a set. This is CtuiApp's default generic storage service.
    """

    def get(self, key, default=_MISSING):
        """Use an explicit default or raise because this store has no keys."""
        if default is not _MISSING:
            return default
        raise StorageKeyError(key)

    def set(self, key, value):
        """Discard a key-value pair."""
        pass

    def close(self):
        """Do nothing because this backend owns no resources."""
        pass
