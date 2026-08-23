"""Use any CtuiApp automatically as a traditional command-line program.

Try these from the repository root:

    uv run examples/07_headless_testing.py --help
    uv run examples/07_headless_testing.py -c "greet Ada --enthusiastic"
    uv run examples/07_headless_testing.py -c "add 12 30" -c "count-words 'hello world'"
    uv run examples/07_headless_testing.py --file examples/commands.txt

Run without arguments to open the same application's full-screen interface.
"""

from ctui import CtuiApp, command


class CommandLineTool(CtuiApp):
    """Offer commands in both the full-screen UI and ordinary shell mode."""

    name = "Command Line Example"
    description = "One application that automatically supports two interfaces."

    @command
    def greet(self, name: str, enthusiastic: bool = False) -> str:
        """Greet a person by name."""
        punctuation = "!" if enthusiastic else "."
        return f"Hello, {name}{punctuation}"

    @command
    def add(self, first: float, second: float) -> str:
        """Add two numbers."""
        return f"{first} + {second} = {first + second}"

    @command(name="count-words")
    def count_words(self, text: str) -> str:
        """Count words in quoted text."""
        count = len(text.split())
        return f"{count} word{'s' if count != 1 else ''}"


if __name__ == "__main__":
    CommandLineTool().run()
