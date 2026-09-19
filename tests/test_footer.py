"""Dynamic status text and focus-preserving output navigation regressions.

The historical filename refers to the status bar. Verify evaluation on access,
injected widgets, read-only output writes, and scrolling both the viewport and
hidden cursor so the next render does not jump back to the old position.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from prompt_toolkit.layout.containers import Window
from prompt_toolkit.widgets import TextArea

from ctui.application import CtuiApp
from ctui.functions import (
    scroll_end,
    scroll_home,
    scroll_line_down,
    scroll_line_up,
    scroll_page_down,
    scroll_page_up,
)
from ctui.layout import CtuiLayout


class StatusbarTests(unittest.TestCase):
    """Check widget/state contracts without starting a terminal run loop."""

    def test_string_statusbar_is_displayed(self):
        app = CtuiApp()
        app.statusbar = "Ready"

        self.assertEqual(app._statusbar, "Ready")

    def test_callable_statusbar_is_evaluated_each_time(self):
        app = CtuiApp()
        current_directory = ["/first"]
        app.statusbar = lambda: f"CWD: {current_directory[0]}"

        self.assertEqual(app._statusbar, "CWD: /first")
        current_directory[0] = "/second"
        self.assertEqual(app._statusbar, "CWD: /second")

    def test_layout_uses_dynamic_statusbar_callback(self):
        app = CtuiApp()
        status = ["first"]
        app.statusbar = lambda: status[0]
        layout = CtuiLayout(app)

        self.assertTrue(callable(layout.statusbar.content.text))
        self.assertEqual(layout.statusbar.content.text(), "first")
        status[0] = "second"
        self.assertEqual(layout.statusbar.content.text(), "second")

    def test_layout_honors_injected_widgets_and_root_container(self):
        input_field = TextArea(height=1)
        output_field = TextArea()
        statusbar = Window(height=1)
        root = Window()
        layout = CtuiLayout(
            CtuiApp(),
            input_field=input_field,
            output_field=output_field,
            statusbar=statusbar,
            root_container=root,
        )

        self.assertIs(layout.input_field, input_field)
        self.assertIs(layout.output_field, output_field)
        self.assertIs(layout.statusbar, statusbar)
        self.assertIs(layout.root_container, root)

    def test_output_is_read_only_and_does_not_take_focus(self):
        layout = CtuiLayout(CtuiApp())
        self.assertTrue(layout.output_field.buffer.read_only())
        self.assertFalse(layout.output_field.control.focusable())
        self.assertFalse(layout.output_field.control.focus_on_click())

    def test_framework_can_update_read_only_output(self):
        layout = CtuiLayout(CtuiApp())
        layout.set_output("First result")
        self.assertEqual(layout.output_field.text, "First result")
        layout.set_output("Second result")
        self.assertEqual(layout.output_field.text, "Second result")

    def test_output_scroll_helpers_adjust_viewport_without_focus(self):
        render_info = SimpleNamespace(
            ui_content=SimpleNamespace(line_count=20),
            window_height=5,
            first_visible_line=lambda: 3,
        )
        window = SimpleNamespace(render_info=render_info, vertical_scroll=3)
        document = SimpleNamespace(
            translate_row_col_to_index=lambda row, column: row * 10 + column
        )
        buffer = SimpleNamespace(document=document, cursor_position=0)
        output = SimpleNamespace(window=window, buffer=buffer)
        event = SimpleNamespace(app=SimpleNamespace(invalidate=Mock()))

        scroll_line_down(event, output)
        self.assertEqual(window.vertical_scroll, 4)
        self.assertEqual(buffer.cursor_position, 80)
        scroll_line_up(event, output)
        self.assertEqual(window.vertical_scroll, 2)
        self.assertEqual(buffer.cursor_position, 20)
        scroll_page_down(event, output)
        self.assertEqual(window.vertical_scroll, 8)
        self.assertEqual(buffer.cursor_position, 120)
        scroll_page_up(event, output)
        self.assertEqual(window.vertical_scroll, 0)
        self.assertEqual(buffer.cursor_position, 0)
        scroll_end(event, output)
        self.assertEqual(window.vertical_scroll, 15)
        self.assertEqual(buffer.cursor_position, 190)
        scroll_home(event, output)
        self.assertEqual(window.vertical_scroll, 0)
        self.assertEqual(buffer.cursor_position, 0)
        self.assertEqual(event.app.invalidate.call_count, 6)


if __name__ == "__main__":
    unittest.main()
