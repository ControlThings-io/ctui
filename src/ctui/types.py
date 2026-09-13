"""Reusable command parameter types."""

from __future__ import annotations

import re


_BYTE_ESCAPE = re.compile(r"(?:\\x[0-9a-fA-F]{2})+")
_CONTIGUOUS = re.compile(r"[0-9a-fA-F]+")
_PREFIXED_BYTES = re.compile(
    r"0x[0-9a-f]{2}(?:\s+0x[0-9a-f]{2})*", re.IGNORECASE
)
_WHITESPACE_BYTES = re.compile(r"[0-9a-fA-F]{2}(?:\s+[0-9a-fA-F]{2})+")
_SEPARATED_BYTES = re.compile(
    r"[0-9a-fA-F]{2}(?P<separator>[:_-])[0-9a-fA-F]{2}"
    r"(?:(?P=separator)[0-9a-fA-F]{2})*"
)


class HexBytes(bytes):
    """Immutable bytes parsed from common hexadecimal text representations.

    Text may be contiguous, prefixed with ``0x``, expressed as ``\\xNN``
    escapes, or separated into bytes by spaces, colons, hyphens, or
    underscores. Hexadecimal digits are case-insensitive.
    """

    def __new__(cls, value: str | bytes | bytearray | memoryview = b""):
        """Parse *value* without guessing at malformed or ambiguous input."""
        if isinstance(value, str):
            raw = cls._parse(value)
        elif isinstance(value, (bytes, bytearray, memoryview)):
            raw = bytes(value)
        else:
            raise TypeError("HexBytes requires hexadecimal text or a bytes-like value")
        return super().__new__(cls, raw)

    @staticmethod
    def _parse(value: str) -> bytes:
        text = value.strip()
        if not text:
            raise ValueError("hexadecimal input cannot be empty")
        if _BYTE_ESCAPE.fullmatch(text):
            return bytes.fromhex(text.replace(r"\x", ""))
        if _PREFIXED_BYTES.fullmatch(text):
            return bytes.fromhex(" ".join(part[2:] for part in text.split()))
        if text.lower().startswith("0x"):
            digits = text[2:]
            if not _CONTIGUOUS.fullmatch(digits) or len(digits) % 2:
                raise ValueError("0x must be followed by an even number of hex digits")
            return bytes.fromhex(digits)
        if _WHITESPACE_BYTES.fullmatch(text):
            return bytes.fromhex(text)
        separated = _SEPARATED_BYTES.fullmatch(text)
        if separated:
            return bytes.fromhex(text.replace(separated.group("separator"), ""))
        if _CONTIGUOUS.fullmatch(text):
            if len(text) % 2:
                raise ValueError("hexadecimal input must contain complete byte pairs")
            return bytes.fromhex(text)
        raise ValueError(
            "expected hex byte pairs using contiguous, 0x, \\xNN, space, colon, "
            "hyphen, or underscore notation"
        )


__all__ = ["HexBytes"]
