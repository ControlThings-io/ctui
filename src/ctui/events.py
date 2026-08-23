"""Small async event bus used by applications and commands."""

from __future__ import annotations
import inspect
from collections import defaultdict


class EventBus:
    def __init__(self):
        self._listeners = defaultdict(list)

    def on(self, event_name, handler=None):
        def register(target):
            self._listeners[event_name].append(target)
            return target

        return register(handler) if handler else register

    def off(self, event_name, handler):
        self._listeners[event_name].remove(handler)

    async def emit(self, event_name, **data):
        results = []
        for handler in tuple(self._listeners[event_name]):
            result = handler(**data)
            results.append(await result if inspect.isawaitable(result) else result)
        return results
