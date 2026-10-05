"""Translate the supported compose() widgets into browser layout snapshots.

The existing prompt-toolkit tree remains the source of truth. No terminal is
started: buffer text, formatted labels, dimensions, visibility, and callable
status text are read on invalidation. Arbitrary third-party controls are rejected
explicitly rather than silently dropping application UI.
"""

from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.formatted_text.utils import fragment_list_to_text
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    DynamicContainer,
    FloatContainer,
    HSplit,
    VSplit,
    Window,
    to_container,
)
from prompt_toolkit.layout.controls import (
    BufferControl,
    DummyControl,
    FormattedTextControl,
)
from prompt_toolkit.layout.dimension import to_dimension
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.widgets import Button, Frame, ProgressBar


def plain(value):
    """Resolve callable/formatted text without interpreting browser markup."""
    return fragment_list_to_text(to_formatted_text(value))


class WebLayout:
    """Snapshot shared widgets and retain IDs for interactive controls.

    Sizes are expressed in character cells; CSS handles flexible space. Native
    browser selection, focus, and scroll position belong to each view. Custom
    floats and arbitrary UIControl implementations are outside this adapter's
    supported surface; use ctui's reusable dialogs for modal interactions.
    """

    def __init__(self, ctui, root):
        self.ctui, self.root = ctui, root
        self.controls = {}
        self._ids = {}
        self._buffers = set()

    def _changed(self, buffer):
        self.ctui.app.invalidate()

    def close(self):
        """Detach redraw listeners when the session ends."""
        for buffer in self._buffers:
            buffer.on_text_changed -= self._changed
        self._buffers.clear()

    def _id(self, obj):
        key = id(obj)
        if key not in self._ids:
            self._ids[key] = str(len(self._ids))
        return self._ids[key]

    def snapshot(self):
        """Resolve a fresh tree, including dynamic visibility and content."""
        self.controls = {}
        return self._node(self.root)

    def _node(self, value):
        container = to_container(value)
        widget = getattr(container, "_ctui_widget", value)
        node = {"id": self._id(container)}
        if isinstance(widget, Frame):
            node.update(kind="frame", title=plain(widget.title))
            node["children"] = [self._node(widget.body)]
        elif isinstance(widget, ProgressBar):
            node.update(kind="progress", value=widget.percentage)
        elif isinstance(widget, Button):
            node.update(kind="button", text=plain(widget.text))
            self.controls[node["id"]] = widget
        elif isinstance(container, FloatContainer):
            if any(
                not isinstance(float_.content, CompletionsMenu)
                for float_ in container.floats
            ):
                raise TypeError(
                    "Web mode does not support custom floats; use CTUI dialogs"
                )
            return self._node(container.content)
        elif isinstance(container, ConditionalContainer):
            selected = (
                container.content
                if container.filter()
                else container.alternative_content
            )
            return self._node(selected) if selected else dict(node, kind="empty")
        elif isinstance(container, DynamicContainer):
            return self._node(container.get_container())
        elif isinstance(container, (HSplit, VSplit)):
            node.update(
                kind="vertical" if isinstance(container, HSplit) else "horizontal",
                children=[self._node(child) for child in container.children],
            )
        elif isinstance(container, Window):
            if container is self.ctui.layout.input_field.window:
                node.update(kind="input", prompt=plain(self.ctui.prompt))
            elif container is self.ctui.layout.header_field:
                node.update(kind="separator")
            elif isinstance(container.content, BufferControl):
                buffer = container.content.buffer
                if buffer not in self._buffers:
                    buffer.on_text_changed += self._changed
                    self._buffers.add(buffer)
                node.update(
                    kind="text" if buffer.read_only() else "editor",
                    text=buffer.text,
                    wrap=container.wrap_lines(),
                )
                if node["kind"] == "editor":
                    self.controls[node["id"]] = buffer
            elif isinstance(container.content, FormattedTextControl):
                node.update(
                    kind="label",
                    fragments=[
                        [fragment[0], fragment[1]]
                        for fragment in to_formatted_text(container.content.text)
                        if not fragment[0].startswith("[ZeroWidthEscape]")
                    ],
                )
            elif isinstance(container.content, DummyControl):
                node.update(kind="label", fragments=[["", container.char or ""]])
            else:
                raise TypeError(
                    f"Web mode does not support {type(container.content).__name__}"
                )
        else:
            raise TypeError(f"Web mode does not support {type(container).__name__}")
        for axis in ("width", "height"):
            size = getattr(container, axis, None)
            size = size() if callable(size) else size
            if size is not None:
                dimension = to_dimension(size)
                node[axis] = {
                    name: getattr(dimension, name)
                    for name in ("min", "max", "preferred", "weight")
                }
        if node["kind"] == "label" and container.dont_extend_height():
            current = node.get("height", {})
            if current.get("max", 10**30) > 10**9:
                lines = (
                    max(1, plain(container.content.text).count("\n") + 1)
                    if isinstance(container.content, FormattedTextControl)
                    else 1
                )
                node["height"] = dict(min=lines, max=lines, preferred=lines, weight=1)
        elif node["kind"] == "progress" and "height" not in node:
            node["height"] = dict(min=1, max=1, preferred=1, weight=1)
        elif node["kind"] in ("horizontal", "vertical") and "height" not in node:
            heights = [child.get("height", {}) for child in node["children"]]
            if heights and all(
                size.get("max", 10**30) == size.get("min", 0) for size in heights
            ):
                combine = max if node["kind"] == "horizontal" else sum
                height = combine(size["min"] for size in heights)
                node["height"] = dict(
                    min=height, max=height, preferred=height, weight=1
                )
        style = getattr(container, "style", "")
        node["style"] = style() if callable(style) else style
        return node
