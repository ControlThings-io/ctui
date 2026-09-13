"""Use every CtuiApp as a traditional command-line program too.

Try:
    uv run examples/05_automatic_cli.py --help
    uv run examples/05_automatic_cli.py -c "greet Ada enthusiastic true"
    uv run examples/05_automatic_cli.py -c "add 12 30" -c "count-words 'hello world'"
    uv run examples/05_automatic_cli.py --file examples/commands.txt

Run without arguments to open the same application's full-screen interface.
"""

from ctui import CtuiApp, command


class CommandLineTool(CtuiApp):
    """Offer commands through both supported interfaces."""

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
