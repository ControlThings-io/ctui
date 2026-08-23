"""Optional storage and command-history services."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .commands import CommandError


_MISSING = object()


class StorageKeyError(CommandError, KeyError):
    """Indicate that a required application-storage key does not exist."""

    def __init__(self, key: str):
        """Create a concise error suitable for terminal and popup display."""
        self.key = key
        CommandError.__init__(self, f"No stored value exists for {key!r}.")


@dataclass(frozen=True)
class HistoryEntry:
    """Record a submitted command and the time it was accepted."""
    command: str
    timestamp: datetime


class HistoryStore(Protocol):
    """Structural interface implemented by command-history backends."""
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
    """Structural interface implemented by key-value storage backends."""
    def get(self, key: str, default=_MISSING):
        """Return *key*, use an explicit default, or raise StorageKeyError."""
        ...
    def set(self, key: str, value) -> None:
        """Associate *value* with *key*."""
        ...
    def close(self) -> None:
        """Release resources owned by the backend."""
        ...


class MemoryStorage:
    """Provide ephemeral dictionary-backed application storage."""
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
    """Discard writes for applications that do not need persistence."""
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
