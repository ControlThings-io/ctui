"""Sequential event delivery for command lifecycle and application notifications.

Applications emit custom events through self.events rather than injecting a
hidden context argument into command methods. Emitting awaits listeners, making
ordering and failures visible to the command that triggered the event.
"""

from __future__ import annotations

import inspect
from collections import defaultdict


class EventBus:
    """Publish named events to synchronous and asynchronous listeners.

    Listeners receive the keyword payload supplied to emit(). They run in
    registration order, not as detached tasks; synchronous work can block the
    caller. Exceptions propagate and stop delivery to subsequent listeners.
    """

    def __init__(self):
        """Create an event bus with no listeners."""
        self._listeners = defaultdict(list)

    def on(self, event_name, handler=None):
        """Register a listener directly or with @bus.on(event_name).

        Return the original handler. Duplicate registrations are retained and cause
        multiple calls; off() removes one registration at a time.
        """

        def register(target):
            """Attach a decorated listener and return it unchanged."""
            self._listeners[event_name].append(target)
            return target

        return register(handler) if handler else register

    def off(self, event_name, handler):
        """Remove one registration of handler, raising ValueError if absent."""
        self._listeners[event_name].remove(handler)

    async def emit(self, event_name, **data):
        """Invoke a snapshot of listeners and return their resolved results.

        Await each awaitable result before invoking the next listener. Changes to
        registrations during delivery affect later emissions, not this snapshot.
        Return an empty list when no listeners exist; propagate listener exceptions.
        """
        results = []
        for handler in tuple(self._listeners[event_name]):
            result = handler(**data)
            results.append(await result if inspect.isawaitable(result) else result)
        return results
