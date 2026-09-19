r"""Convert common hexadecimal notation into immutable bytes.

Run: uv run examples/05_hex_bytes.py
Try: inspect deadbeef
Try: inspect "de ad be ef"
Try: inspect de:ad:be:ef
Try: inspect 0xdeadbeef
Try: inspect '0xde 0xad 0xbe 0xef'
Try: inspect '\xde\xad\xbe\xef'

Values containing spaces or backslashes are quoted so the shell-like command
parser passes the entire representation to ``HexBytes`` as one argument.

The result is a bytes subclass, ready for a socket or serial write without
parsing again. This example only inspects the value. HexBytes validates complete
byte pairs and never pads ambiguous odd-length input.
"""

from ctui import CtuiApp, HexBytes, command


class HexTool(CtuiApp):
    """Inspect binary data entered using familiar hexadecimal notation."""

    @command
    def inspect(self, payload: HexBytes) -> str:
        """Show normalized hexadecimal and the number of parsed bytes."""
        return f"{payload.hex(' ')} ({len(payload)} bytes)"


if __name__ == "__main__":
    HexTool().run()
