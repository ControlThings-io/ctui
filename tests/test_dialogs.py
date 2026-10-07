"""Rendered dialog regressions for focus, scrolling, and text width.

Use a real prompt-toolkit renderer with dummy terminal output to check button
focus, one-line scrolling, Enter activation, and wide-character sizing. These
checks exercise layout behavior without claiming visual acceptance on terminals.
"""

import unittest
from types import SimpleNamespace

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import set_app
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import DummyInput
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.output import DummyOutput

from ctui.dialogs import MessageDialog, YesNoDialog


class TerminalOutput(DummyOutput):
    def get_size(self):
        return Size(rows=15, columns=140)


class DialogTests(unittest.IsolatedAsyncioTestCase):
    """Render read-only dialogs to verify keyboard behavior and wrapping bounds."""

    async def test_buttons_keep_focus_during_scrolling(self):
        for dialog_type in (MessageDialog, YesNoDialog):
            with self.subTest(dialog=dialog_type.__name__):
                dialog = dialog_type(
                    text="\n".join(f"Line {i}" for i in range(80)), scrollbar=True
                )
                app = Application(
                    layout=Layout(dialog),
                    input=DummyInput(),
                    output=TerminalOutput(),
                    full_screen=True,
                )
                with set_app(app):
                    app.renderer.render(app, app.layout)
                    button = app.layout.current_control
                    self.assertIsNot(button, dialog.text_area.control)
                    start = dialog.text_area.window.render_info.first_visible_line()
                    for key, expected in ((Keys.Down, start + 1), (Keys.Up, start)):
                        button.key_bindings.get_bindings_for_keys((key,))[-1].handler(
                            SimpleNamespace(app=app)
                        )
                        app.renderer.render(app, app.layout)
                        self.assertIs(app.layout.current_control, button)
                        self.assertEqual(
                            dialog.text_area.window.render_info.first_visible_line(),
                            expected,
                        )
                    button.key_bindings.get_bindings_for_keys((Keys.ControlM,))[
                        -1
                    ].handler(SimpleNamespace(app=app))
                    self.assertTrue(dialog.future.done())

    async def test_longest_line_fits_with_scrollbar(self):
        for dialog_type in (MessageDialog, YesNoDialog):
            for line in ("help " + "x" * 75 + ".", "界" * 40 + "."):
                with self.subTest(dialog=dialog_type.__name__, line=line):
                    dialog = dialog_type(text=line + "\nshort", scrollbar=True)
                    app = Application(
                        layout=Layout(dialog),
                        input=DummyInput(),
                        output=TerminalOutput(),
                        full_screen=True,
                    )
                    with set_app(app):
                        app.renderer.render(app, app.layout)
                        info = dialog.text_area.window.render_info
                        self.assertEqual(info.get_height_for_line(0), 1)


class ValueDialogTests(unittest.IsolatedAsyncioTestCase):
    """Check typed dialog results and a real modal application's queue/cleanup."""

    async def test_dictionary_conversion_validation_and_input_copy(self):
        from ctui.dialogs import DialogValidationError, DictField, DictInputDialog

        values = {"host": "localhost", "port": 502, "ratio": 1.5, "enabled": True}
        dialog = DictInputDialog(
            values=values,
            fields={
                "port": DictField(
                    validator=lambda value: 0 < value < 65536 or "Port out of range"
                )
            },
            validator=lambda value: value["host"] != "forbidden" or "Host forbidden",
        )
        raw = {"host": "example", "port": "1234", "ratio": "2.5", "enabled": False}
        expected = {"host": "example", "port": 1234, "ratio": 2.5, "enabled": False}
        self.assertEqual(dialog._web_result({"button": 0, "values": raw}), expected)
        self.assertEqual(values["port"], 502)
        self.assertIsNone(dialog._web_result({"button": 1}))
        for key, value, message in (
            ("port", "bad", "int"),
            ("port", "70000", "range"),
            ("ratio", "nan", "float"),
            ("enabled", "false", "checkbox"),
            ("host", "forbidden", "forbidden"),
        ):
            with self.subTest(key=key, value=value):
                with self.assertRaisesRegex(DialogValidationError, message):
                    dialog._web_result({"button": 0, "values": {**raw, key: value}})

    async def test_dictionary_limits_and_none_override(self):
        from ctui.dialogs import DictField, DictInputDialog

        for values, fields in (
            ({"x": []}, None),
            ({1: "x"}, None),
            ({"x": None}, None),
            ({"x": "hi"}, {"missing": DictField()}),
        ):
            with self.assertRaises((TypeError, ValueError)):
                DictInputDialog(values=values, fields=fields)
        dialog = DictInputDialog(
            values={"port": None}, fields={"port": DictField(value_type=int)}
        )
        self.assertEqual(
            dialog._web_result({"button": 0, "values": {"port": "502"}}), {"port": 502}
        )
        self.assertEqual(DictInputDialog()._web_result({"button": 0, "values": {}}), {})

    async def test_selection_defaults_and_cancellation(self):
        from ctui.dialogs import ButtonDialog, CheckboxListDialog, RadioListDialog

        value = object()
        buttons = ButtonDialog(buttons=[("One", 1), ("Object", value), ("Three", 3)])
        self.assertIs(buttons._web_result({"button": 1}), value)
        self.assertIsNone(buttons._web_result({"button": -1}))
        radio = RadioListDialog(values=[(1, "One"), (2, "Two")], default=2)
        self.assertEqual(radio.list.current_value, 2)
        self.assertEqual(radio._web_result({"button": 0, "selected": [1]}), 2)
        check = CheckboxListDialog(values=[(1, "One"), (2, "Two")], default_values=[2])
        self.assertEqual(check.list.current_values, [2])
        self.assertEqual(check._web_result({"button": 0, "selected": [1, 0]}), [1, 2])
        self.assertEqual(check._web_result({"button": 0, "selected": []}), [])
        self.assertIsNone(check._web_result({"button": 1}))
        self.assertEqual(
            CheckboxListDialog()._web_result({"button": 0, "selected": []}), []
        )
        for construct in (
            lambda: ButtonDialog(),
            lambda: ButtonDialog(buttons=[("X", None)]),
            lambda: RadioListDialog(values=[(1, "One"), (1, "Again")]),
            lambda: CheckboxListDialog(values=[(1, "One")], default_values=[3]),
        ):
            with self.assertRaises(ValueError):
                construct()

    async def test_selection_and_text_validators(self):
        from ctui.dialogs import (
            CheckboxListDialog,
            DialogValidationError,
            RadioListDialog,
            TextInputDialog,
        )

        check = CheckboxListDialog(
            values=[(1, "One")], validator=lambda items: bool(items)
        )
        with self.assertRaises(DialogValidationError):
            check._web_result({"button": 0, "selected": []})
        radio = RadioListDialog(values=[(1, "One")])
        for indices in ([], [5], [True], [0, 0], "0"):
            with self.assertRaises(DialogValidationError):
                radio._web_result({"button": 0, "selected": indices})
        text = TextInputDialog(
            default="start",
            validator=lambda value: value.strip() != "" or "Name required",
        )
        self.assertEqual(text.text_area.text, "start")
        with self.assertRaisesRegex(DialogValidationError, "Name required"):
            text._web_result({"button": 0, "text": " "})
        self.assertIsNone(text._web_result({"button": 1}))

    async def test_keyboard_queue_validation_output_and_cleanup(self):
        import asyncio

        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.layout import FloatContainer
        from prompt_toolkit.widgets import TextArea

        from ctui.dialogs import DictInputDialog, MessageDialog, show_dialog

        async def until(predicate):
            async with asyncio.timeout(3):
                while not predicate():
                    await asyncio.sleep(0.01)

        with create_pipe_input() as pipe:
            draft = TextArea(text="unfinished")
            root = FloatContainer(content=draft, floats=[])
            app = Application(
                layout=Layout(root),
                input=pipe,
                output=TerminalOutput(),
                full_screen=True,
            )
            running = asyncio.create_task(app.run_async())
            await until(lambda: app.is_running)
            with set_app(app):
                form = DictInputDialog(values={"port": 502, "host": "localhost"})
                first = asyncio.create_task(show_dialog(form))
                second_dialog = MessageDialog(text="Queued")
                second = asyncio.create_task(show_dialog(second_dialog))
                await until(lambda: len(root.floats) == 1)
                form.inputs["port"].text = "bad"
                form.inputs["host"].text = "edited"
                # Exercise the actual upstream Tab path to the confirmation button.
                pipe.send_text("\t\t\r")
                await until(lambda: bool(form.error.text))
                self.assertIs(app.layout.current_control, form.inputs["port"].control)
                self.assertEqual(form.inputs["host"].text, "edited")
                draft.text = "background update"
                form.inputs["port"].text = "1234"
                pipe.send_text("\t\t\r")
                self.assertEqual(
                    await asyncio.wait_for(first, 3), {"port": 1234, "host": "edited"}
                )
                await until(
                    lambda: bool(root.floats) and app.layout.has_focus(second_dialog)
                )
                self.assertEqual(len(root.floats), 1)
                pipe.send_text("\x1b")
                await asyncio.wait_for(second, 3)
                self.assertFalse(root.floats)
                self.assertIs(app.layout.current_control, draft.control)
                self.assertEqual(draft.text, "background update")
                third_dialog = MessageDialog(text="Cancel task")
                third = asyncio.create_task(show_dialog(third_dialog))
                await until(lambda: bool(root.floats))
                third.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await third
                self.assertFalse(root.floats)
                self.assertIs(app.layout.current_control, draft.control)
            app.exit()
            await running

    async def test_focus_failure_removes_float(self):
        from unittest.mock import patch

        from prompt_toolkit.layout import FloatContainer
        from prompt_toolkit.widgets import TextArea

        from ctui.dialogs import MessageDialog, show_dialog

        root = FloatContainer(content=TextArea(), floats=[])
        app = Application(
            layout=Layout(root), input=DummyInput(), output=TerminalOutput()
        )
        with (
            set_app(app),
            patch.object(app.layout, "focus", side_effect=ValueError("focus failed")),
        ):
            with self.assertRaises(ValueError):
                await show_dialog(MessageDialog(text="Test"))
        self.assertFalse(root.floats)

    async def test_all_dialogs_escape_and_selection_keyboard(self):
        import asyncio

        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.layout import FloatContainer
        from prompt_toolkit.widgets import TextArea

        from ctui.dialogs import (
            ButtonDialog,
            CheckboxListDialog,
            RadioListDialog,
            TextInputDialog,
            show_dialog,
        )

        with create_pipe_input() as pipe:
            draft = TextArea(text="kept")
            root = FloatContainer(content=draft, floats=[])
            app = Application(layout=Layout(root), input=pipe, output=TerminalOutput())
            running = asyncio.create_task(app.run_async())
            try:
                async with asyncio.timeout(3):
                    while not app.is_running:
                        await asyncio.sleep(0.01)
                with set_app(app):
                    for dialog, expected in (
                        (YesNoDialog(), False),
                        (TextInputDialog(), None),
                        (ButtonDialog(buttons=[("One", 1)]), None),
                        (RadioListDialog(values=[(1, "One")]), None),
                        (CheckboxListDialog(values=[(1, "One")]), None),
                    ):
                        task = asyncio.create_task(show_dialog(dialog))
                        async with asyncio.timeout(3):
                            while not root.floats:
                                await asyncio.sleep(0.01)
                        pipe.send_text("\x1b")
                        self.assertEqual(await asyncio.wait_for(task, 3), expected)
                        self.assertFalse(root.floats)
                        self.assertIs(app.layout.current_control, draft.control)
                    for dialog, expected in (
                        (RadioListDialog(values=[(1, "One"), (2, "Two")]), 2),
                        (CheckboxListDialog(values=[(1, "One"), (2, "Two")]), [2]),
                    ):
                        task = asyncio.create_task(show_dialog(dialog))
                        async with asyncio.timeout(3):
                            while not root.floats:
                                await asyncio.sleep(0.01)
                        pipe.send_text("\x1b[B \t\r")
                        self.assertEqual(await asyncio.wait_for(task, 3), expected)
            finally:
                app.exit()
                await running

    async def test_upstream_button_wide_caption_and_no_mouse_handler(self):
        from prompt_toolkit.data_structures import Point
        from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType
        from prompt_toolkit.widgets import Button as ToolkitButton

        from ctui.base import Button

        button = Button("界" * 9, width=1)
        self.assertIsInstance(button, ToolkitButton)
        self.assertEqual(button.width, 20)
        fragments = button.control.text()
        fragments[0][2](
            MouseEvent(
                Point(0, 0), MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset()
            )
        )

    async def test_old_conditional_container_without_alternative(self):
        from prompt_toolkit.layout import ConditionalContainer, Window

        from ctui.web_layout import WebLayout

        hidden = ConditionalContainer(Window(), filter=False)
        if hasattr(hidden, "alternative_content"):
            del hidden.alternative_content
        self.assertEqual(WebLayout(None, hidden).snapshot()["kind"], "empty")

    async def test_validator_bug_propagates_and_removes_popup(self):
        import asyncio

        from prompt_toolkit.layout import FloatContainer
        from prompt_toolkit.widgets import TextArea

        from ctui.dialogs import RadioListDialog, show_dialog

        def broken(value):
            raise RuntimeError("validator bug")

        root = FloatContainer(content=TextArea(), floats=[])
        app = Application(
            layout=Layout(root), input=DummyInput(), output=TerminalOutput()
        )
        with set_app(app):
            dialog = RadioListDialog(values=[(1, "One")], validator=broken)
            task = asyncio.create_task(show_dialog(dialog))
            await asyncio.sleep(0)
            dialog._accept({"button": 0, "selected": [0]})
            with self.assertRaisesRegex(RuntimeError, "validator bug"):
                await task
        self.assertFalse(root.floats)

    async def test_convenience_dialog_cancels_on_terminal_shutdown(self):
        import asyncio

        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.layout import FloatContainer
        from prompt_toolkit.widgets import TextArea

        from ctui.dialogs import message_dialog

        with create_pipe_input() as pipe:
            root = FloatContainer(content=TextArea(), floats=[])
            app = Application(layout=Layout(root), input=pipe, output=TerminalOutput())
            running = asyncio.create_task(app.run_async())
            try:
                async with asyncio.timeout(3):
                    while not app.is_running:
                        await asyncio.sleep(0.01)
                with set_app(app):
                    task = message_dialog(text="Await dismissal")
                async with asyncio.timeout(3):
                    while not root.floats:
                        await asyncio.sleep(0.01)
                app.exit()
                await running
                self.assertTrue(task.cancelled())
                self.assertFalse(root.floats)
            finally:
                if app.is_running:
                    app.exit()
                await running

    async def test_dictionary_labels_and_values_share_aligned_rows(self):
        from ctui.dialogs import DictField, DictInputDialog
        from ctui.style import CtuiStyle

        for columns in (56, 140):
            with self.subTest(columns=columns):

                class SizedOutput(DummyOutput):
                    def get_size(self):
                        return Size(rows=20, columns=columns)

                dialog = DictInputDialog(
                    values={
                        "host": "localhost",
                        "port": 502,
                        "地址": "server",
                        "enabled": True,
                    },
                    fields={
                        "port": DictField(
                            label="TCP port", help="Allowed range: 1–65535"
                        )
                    },
                )
                app = Application(
                    layout=Layout(dialog),
                    input=DummyInput(),
                    output=SizedOutput(),
                    style=CtuiStyle.dark_theme,
                    full_screen=True,
                )
                with set_app(app):
                    app.renderer.render(app, app.layout)
                    screen = app.renderer.last_rendered_screen
                    lines = [
                        "".join(
                            (screen.data_buffer[y][x].char or " ")
                            for x in range(columns)
                        )
                        for y in range(20)
                    ]
                    starts = []
                    for label, value in (
                        ("host", "localhost"),
                        ("TCP port", "502"),
                        ("地址", "server"),
                    ):
                        line = next(
                            line
                            for line in lines
                            if label.replace(" ", "") in line.replace(" ", "")
                        )
                        self.assertIn(value, line)
                        self.assertIn("│", line)
                        self.assertIn("[", line)
                        starts.append(line.index("["))
                    self.assertEqual(len(set(starts)), 1)
                    enabled = next(line for line in lines if "enabled" in line)
                    self.assertIn("[*]", enabled)
                    help_line = next(line for line in lines if "Allowed range" in line)
                    self.assertGreater(help_line.index("Allowed range"), starts[0])
                    app.layout.focus(dialog.inputs["port"])
                    app.renderer.render(app, app.layout)
                    focused = app.renderer.last_rendered_screen
                    self.assertTrue(
                        any(
                            "dict-value.focused" in cell.style
                            for row in focused.data_buffer.values()
                            for cell in row.values()
                        )
                    )

    async def test_long_dictionary_labels_keep_editor_columns_aligned(self):
        from ctui.dialogs import DictField, DictInputDialog

        dialog = DictInputDialog(
            width=40,
            values={"host": "localhost", "port": 502},
            fields={"host": DictField(label="Long connection hostname")},
        )
        app = Application(
            layout=Layout(dialog),
            input=DummyInput(),
            output=TerminalOutput(),
            full_screen=True,
        )
        with set_app(app):
            app.renderer.render(app, app.layout)
            positions = (
                app.renderer.last_rendered_screen.visible_windows_to_write_positions
            )
            host = positions[dialog.inputs["host"].window]
            port = positions[dialog.inputs["port"].window]
            self.assertEqual(host.xpos, port.xpos)
            self.assertGreaterEqual(host.width, 10)
