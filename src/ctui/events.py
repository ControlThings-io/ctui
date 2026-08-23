"""Small async event bus used by applications and commands."""

from __future__ import annotations
import inspect
from collections import defaultdict


class EventBus:
    """Publish named events to synchronous and asynchronous listeners."""
    def __init__(self):
        """Create an event bus with no listeners."""
        self._listeners = defaultdict(list)

    def on(self, event_name, handler=None):
        """Register *handler* for an event, directly or as a decorator."""
        def register(target):
            """Attach a decorated listener and return it unchanged."""
            self._listeners[event_name].append(target)
            return target

        return register(handler) if handler else register

    def off(self, event_name, handler):
        """Remove a previously registered event listener."""
        self._listeners[event_name].remove(handler)

    async def emit(self, event_name, **data):
        """Invoke listeners sequentially and return their resolved results."""
        results = []
        for handler in tuple(self._listeners[event_name]):
            result = handler(**data)
            results.append(await result if inspect.isawaitable(result) else result)
        return results
