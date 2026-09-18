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
