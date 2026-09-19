"""Event ordering and the interchangeable memory/null service contracts.

Await mixed sync/async listeners in order. Missing storage keys must remain
user-facing errors unless an explicit default, including None, was supplied;
null services discard writes without changing that contract.
"""

import unittest

from ctui.commands import CommandError
from ctui.events import EventBus
from ctui.services import (
    MemoryHistory,
    MemoryStorage,
    NullHistory,
    NullStorage,
    StorageKeyError,
)


class EventTests(unittest.IsolatedAsyncioTestCase):
    """Verify one emission awaits listeners in registration order."""

    async def test_sync_and_async_listeners(self):
        bus, seen = EventBus(), []
        bus.on("work", lambda value: seen.append(value))

        @bus.on("work")
        async def listener(value):
            seen.append(value * 2)

        await bus.emit("work", value=3)
        self.assertEqual(seen, [3, 6])


class ServiceTests(unittest.TestCase):
    """Verify ephemeral history and explicit-default storage behavior."""

    def test_memory_and_null_services(self):
        history = MemoryHistory()
        history.append("help")
        self.assertEqual(history.all()[0].command, "help")
        history.clear()
        self.assertEqual(history.all(), [])
        null = NullHistory()
        null.append("ignored")
        self.assertEqual(null.all(), [])
        storage = MemoryStorage()
        storage.set("x", 1)
        self.assertEqual(storage.get("x"), 1)
        self.assertEqual(storage.get("missing", "fallback"), "fallback")
        self.assertIsNone(storage.get("missing", None))
        with self.assertRaisesRegex(StorageKeyError, "No stored value"):
            storage.get("missing")
        empty = NullStorage()
        empty.set("x", 1)
        self.assertIsNone(empty.get("x", None))
        with self.assertRaises(StorageKeyError) as raised:
            empty.get("x")
        self.assertIsInstance(raised.exception, CommandError)
