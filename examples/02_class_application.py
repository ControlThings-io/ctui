"""Organize related commands in an application class.

Run: uv run examples/02_class_application.py
Try: add 2 3
Try: multiply 4 5

Both methods return CommandResult.append so earlier calculations stay visible.
The UI applies each append when that command completes; do not build an output
string from a snapshot of previous results. Integer annotations perform input
conversion before the method runs.
"""

from ctui import CommandResult, CtuiApp, command


class Calculator(CtuiApp):
    """Multiple commands and appending output."""

    name = "Calculator"
    prompt = "calc> "

    @command
    def add(self, first: int, second: int) -> str:
        """Add two whole numbers."""
        answer = str(first + second)
        return CommandResult.append(f"{first} + {second} = {answer}")

    @command
    def multiply(self, first: int, second: int) -> str:
        """Multiply two whole numbers."""
        answer = str(first * second)
        return CommandResult.append(f"{first} * {second} = {answer}")


if __name__ == "__main__":
    Calculator().run()
