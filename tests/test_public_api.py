"""Protect the documented ctui 1.x top-level import surface.

The expected export set is deliberate: adding or removing a supported name should
update the public contract and this test together. Compare runtime version with
installed distribution metadata; this does not assert every internal submodule
is stable or that widgets are covered by the top-level export assertion.
"""

import unittest
from importlib.metadata import version

import ctui


class PublicApiTests(unittest.TestCase):
    """Verify supported top-level imports and runtime version metadata."""

    EXPECTED_EXPORTS = {
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
    }

    def test_documented_top_level_exports_are_available(self):
        self.assertEqual(set(ctui.__all__), self.EXPECTED_EXPORTS)
        for name in ctui.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(ctui, name))

    def test_runtime_version_matches_installed_package_metadata(self):
        self.assertEqual(ctui.__version__, version("ctui"))


if __name__ == "__main__":
    unittest.main()
