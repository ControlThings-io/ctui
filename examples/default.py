"""The smallest ctui application.

Run: uv run examples/default.py
Try: help
"""

from ctui import Ctui

app = Ctui(name="Hello Tool", prompt="hello> ")
app.run()
