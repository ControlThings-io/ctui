"""Create a small application with one command.

Run: uv run examples/01_first_command.py
Try in the UI: hello Ada
Try in the shell: uv run examples/01_first_command.py -c "hello Ada"
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
