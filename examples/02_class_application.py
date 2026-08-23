"""Organize related commands in an application class.

Run: uv run examples/02_class_application.py
Try: add 2 3
Try: multiply 4 5
"""

from ctui import CtuiApp, command


class Calculator(CtuiApp):
    """Offer a pair of commands that share application configuration."""

    name = "Calculator"
    prompt = "calc> "

    @command
    def add(self, first: int, second: int) -> str:
        """Add two whole numbers."""
        answer = str(first + second)
        return f"{self.output_text}{first} + {second} = {answer}\n"
        

    @command
    def multiply(self, first: int, second: int) -> str:
        """Multiply two whole numbers."""
        answer = str(first * second)
        return f"{self.output_text}{first} * {second} = {answer}\n"


if __name__ == "__main__":
    Calculator().run()
