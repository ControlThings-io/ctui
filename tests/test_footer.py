import unittest

from ctui.application import Ctui
from ctui.layout import CtuiLayout


class FooterTests(unittest.TestCase):
    def test_string_footer_is_in_statusbar(self):
        app = Ctui()
        app.footer = "Ready"

        self.assertEqual(app._statusbar, "Project: default  Ready")

    def test_callable_footer_is_evaluated_each_time(self):
        app = Ctui()
        current_directory = ["/first"]
        app.footer = lambda: f"CWD: {current_directory[0]}"

        self.assertEqual(app._statusbar, "Project: default  CWD: /first")
        current_directory[0] = "/second"
        self.assertEqual(app._statusbar, "Project: default  CWD: /second")

    def test_layout_uses_dynamic_statusbar_callback(self):
        app = Ctui()
        footer = ["first"]
        app.footer = lambda: footer[0]
        layout = CtuiLayout(app)

        self.assertTrue(callable(layout.statusbar.content.text))
        self.assertEqual(layout.statusbar.content.text(), "Project: default  first")
        footer[0] = "second"
        self.assertEqual(layout.statusbar.content.text(), "Project: default  second")


if __name__ == "__main__":
    unittest.main()
