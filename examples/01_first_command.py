"""Register and run a command on an application instance.

Run: uv run examples/01_first_command.py
Try: hello Ada
"""

from ctui import CtuiApp

app = CtuiApp(name="Greeter", prompt="greet> ")


@app.command
def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"


if __name__ == "__main__":
    app.run()
