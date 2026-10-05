"""Run one application as terminal UI, CLI commands, or a browser session.

Run: uv run examples/15_web_frontend.py --web --web-port 0
Open the credential URL printed in the terminal. Open another tab at the same
address to share output; draft input and scrolling remain local to each tab.
Try: echo hello, help echo, and progress 50. Click Increment to update the footer.

Without --web the same app opens its terminal UI; -c "echo hello" runs the CLI.
A custom frame, side-by-side panes, button and progress bar reuse compose().
"""

from ctui import Argument, CommandResult, CtuiApp, command
from ctui.widgets import Button, Frame, Horizontal, ProgressBar, Vertical


class WebTool(CtuiApp):
    """Demonstrate an unchanged app definition across three frontends."""

    name = "CTUI browser demonstration"

    def __init__(self):
        super().__init__()
        self.clicks = 0
        self.progress_bar = ProgressBar()
        self.statusbar = lambda: f"Button clicks: {self.clicks}"

    def compose(self):
        return Vertical(
            [
                Frame(self.layout.body, title="Commands and output"),
                Horizontal(
                    [
                        self.progress_bar,
                        Button("Increment", handler=self.increment),
                    ],
                    height=1,
                ),
            ]
        )

    def increment(self):
        self.clicks += 1
        self.app.invalidate()

    @command(arguments={"text": Argument(help="Text to append to shared output")})
    def echo(self, text: str) -> CommandResult:
        """Append text to the output window."""
        return CommandResult.append(text)

    @command(arguments={"percent": Argument(help="Progress percentage, from 0 to 100")})
    def progress(self, percent: int) -> CommandResult:
        """Set the progress bar percentage."""
        self.progress_bar.percentage = max(0, min(100, percent))
        if hasattr(self, "app"):
            self.app.invalidate()
        return CommandResult.success()


if __name__ == "__main__":
    WebTool().run()
