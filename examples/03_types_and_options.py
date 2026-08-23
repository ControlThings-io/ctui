"""Use type annotations, defaults, choices, and named options.

Run: uv run examples/03_types_and_options.py
Try: greet Justin
Try: greet "Justin Searle"
Try: greet Justin excited
Try: greet Justin --style excited --uppercase
"""

from typing import Literal

from ctui import CtuiApp, command


class Greeter(CtuiApp):
    """Demonstrate automatic parsing from function annotations."""

    @command
    def greet(
        self,  # Note: self is required when creating a command on a CtuiApp subclass
        name: str,
        style: Literal["friendly", "excited"] = "friendly",
        uppercase: bool = False,
    ) -> str:
        """Greet a person using the selected style."""
        message = f"Hello, {name}." if style == "friendly" else f"Hello, {name}!"
        return message.upper() if uppercase else message


if __name__ == "__main__":
    Greeter().run()
