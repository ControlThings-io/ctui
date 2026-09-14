"""
Control Things User Interface, aka ctui.py

# Copyright (C) 2019  Justin Searle
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details at <http://www.gnu.org/licenses/>.
"""

from importlib.metadata import PackageNotFoundError, version

from ctui.application import CtuiApp
from ctui.commands import (
    Argument,
    CommandError,
    CommandNotFound,
    CommandResult,
    CommandValidationError,
    CompletionContext,
    CompletionItem,
    ConfirmationRequired,
    command,
)
from ctui.projects import ProjectInfo, RecordEntry, SqliteProjectBackend
from ctui.services import (
    ConfigStore,
    HistoryEntry,
    HistoryStore,
    MemoryHistory,
    MemoryStorage,
    NullHistory,
    NullStorage,
    RecordStore,
    Storage,
    StorageKeyError,
)
from ctui.types import (
    FuzzyHexPattern,
    FuzzyStringPattern,
    HexBytes,
    IntegerRanges,
    IntegerSpan,
)

try:
    __version__ = version("ctui")
except PackageNotFoundError:  # Support importing directly from an unpacked tree.
    __version__ = "0+unknown"


__all__ = [
    "Argument",
    "CommandError",
    "CommandNotFound",
    "CommandResult",
    "CommandValidationError",
    "CompletionContext",
    "CompletionItem",
    "ConfigStore",
    "ConfirmationRequired",
    "CtuiApp",
    "FuzzyHexPattern",
    "FuzzyStringPattern",
    "HexBytes",
    "HistoryEntry",
    "HistoryStore",
    "IntegerRanges",
    "IntegerSpan",
    "MemoryHistory",
    "MemoryStorage",
    "NullHistory",
    "NullStorage",
    "ProjectInfo",
    "RecordEntry",
    "RecordStore",
    "SqliteProjectBackend",
    "Storage",
    "StorageKeyError",
    "__version__",
    "command",
]
