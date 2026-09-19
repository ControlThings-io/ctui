"""Create a small application with one command.

Run: uv run examples/01_first_command.py
Try in the UI: hello Ada
Try in the shell: uv run examples/01_first_command.py -c "hello Ada"

The annotation converts the entered name before hello runs. self is the bound
application, not a prompted argument. Returning a string replaces output in the
UI; run() provides both interfaces without a separate CLI parser.
"""

from ctui import CtuiApp, command


class Greeter(CtuiApp):
    """Demonstrate the smallest recommended class-based application."""

    name = "Greeter"
    prompt = "greet> "

    @command
    def hello(self, name: str) -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"


if __name__ == "__main__":
    Greeter().run()
