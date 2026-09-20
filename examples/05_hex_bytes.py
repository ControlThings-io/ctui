r"""Convert common hexadecimal notation into immutable bytes.

Run: uv run examples/05_hex_bytes.py
Try: inspect deadbeef
Try: inspect "de ad be ef"
Try: inspect "dead   b e      ef"
Try: inspect "0xbe 0b10101100 0xef 0d10 0o377"
Try: inspect '0xbe   0xef   0b1010_001_1'
Try: inspect de:ad:be:ef
Try: inspect 0xdeadbeef
Try: inspect '0xde 0xad 0xbe 0xef'
Try: inspect '\xde\xad\xbe\xef'

Values containing spaces or backslashes are quoted so the shell-like command
parser passes the entire representation to ``HexBytes`` as one argument.

Plain hex ignores whitespace, even between nibbles. If any component has a
0x, 0b, 0o, or 0d prefix, every component needs a prefix and is one byte.
Thus "10 20" is hex, but "0xbe 0d10 0d20" contains explicitly decimal 10 and 20. Standalone
0xdeadbeef still represents multiple bytes. Binary underscores follow Python
placement rules; mixed components must each fit in 0..255.

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
