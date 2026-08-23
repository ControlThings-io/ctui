"""Optional storage and command-history services."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class HistoryEntry:
    command: str
    timestamp: datetime


class HistoryStore(Protocol):
    def append(self, command: str) -> None: ...
    def all(self) -> list[HistoryEntry]: ...
    def clear(self) -> None: ...


class MemoryHistory:
    def __init__(self):
        self.entries: list[HistoryEntry] = []

    def append(self, command):
        self.entries.append(HistoryEntry(command, datetime.now()))

    def all(self):
        return list(self.entries)

    def clear(self):
        self.entries.clear()


class NullHistory:
    def append(self, command):
        pass

    def all(self):
        return []

    def clear(self):
        pass


class Storage(Protocol):
    def get(self, key: str, default=None): ...
    def set(self, key: str, value) -> None: ...
    def close(self) -> None: ...


class MemoryStorage:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def close(self):
        pass


class NullStorage:
    def get(self, key, default=None):
        return default

    def set(self, key, value):
        pass

    def close(self):
        pass
