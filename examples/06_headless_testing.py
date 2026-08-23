"""Call commands from Python without opening the terminal interface.

Run: uv run examples/06_headless_testing.py
This pattern is useful in tests, scripts, and other frontends.
"""

import asyncio

from ctui import CtuiApp


async def main() -> None:
    """Register a command, dispatch it, and inspect its result."""
    app = CtuiApp(register_defaults=False)

    @app.command
    async def double(number: int) -> int:
        """Double a whole number."""
        return number * 2

    result = await app.dispatch("double 21")
    print(result.output)
    print("History:", app.history.all()[0].command)


if __name__ == "__main__":
    asyncio.run(main())
