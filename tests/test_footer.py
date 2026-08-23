import unittest

from ctui.application import CtuiApp
from ctui.layout import CtuiLayout


class StatusbarTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
