"""Reusable command parameter types."""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from itertools import product
from math import prod
from random import Random
from string import ascii_letters, digits
from typing import Generic, Iterator, Sequence, TypeVar

_BYTE_ESCAPE = re.compile(r"(?:\\x[0-9a-fA-F]{2})+")
_CONTIGUOUS = re.compile(r"[0-9a-fA-F]+")
_PREFIXED_BYTES = re.compile(r"0x[0-9a-f]{2}(?:\s+0x[0-9a-f]{2})*", re.IGNORECASE)
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


@dataclass(frozen=True, order=True)
class IntegerSpan:
    """One inclusive input range represented by its start and value count."""

    start: int
    count: int

    def __post_init__(self):
        if isinstance(self.start, bool) or not isinstance(self.start, int):
            raise TypeError("integer span start must be an integer")
        if self.start < 0:
            raise ValueError("integer span start cannot be negative")
        if isinstance(self.count, bool) or not isinstance(self.count, int):
            raise TypeError("integer span count must be an integer")
        if self.count < 1:
            raise ValueError("integer span count must be positive")

    @property
    def stop(self) -> int:
        """Return the exclusive stop value."""
        return self.start + self.count

    def values(self) -> range:
        """Return the integers represented by this span."""
        return range(self.start, self.stop)

    def __str__(self):
        return str(self.start) if self.count == 1 else f"{self.start}-{self.stop - 1}"


_INTEGER_RANGE_ITEM = re.compile(r"(?P<start>\d+)(?:\s*-\s*(?P<end>\d+))?")


class IntegerRanges:
    """Ordered, immutable collection of non-negative inclusive integer ranges."""

    DEFAULT_EXPANSION_LIMIT = 65_536
    DEFAULT_SAMPLE_LIMIT = 65_536
    MAX_INPUT_LENGTH = 4_096
    MAX_SPANS = 4_096

    def __init__(self, value: str | Sequence[IntegerSpan]):
        if isinstance(value, str):
            spans = self._parse(value)
            self.source = value
        else:
            try:
                spans = tuple(value)
            except TypeError as error:
                raise TypeError(
                    "IntegerRanges requires comma-separated text or integer spans"
                ) from error
            if not all(isinstance(span, IntegerSpan) for span in spans):
                raise TypeError(
                    "IntegerRanges collections must contain IntegerSpan values"
                )
            if not spans:
                raise ValueError("integer ranges cannot be empty")
            if len(spans) > self.MAX_SPANS:
                raise ValueError(
                    f"integer ranges exceed the {self.MAX_SPANS:,} span limit"
                )
            self.source = ",".join(map(str, spans))
        self._spans = tuple(spans)

    @classmethod
    def _parse(cls, value: str) -> tuple[IntegerSpan, ...]:
        text = value.strip()
        if not text:
            raise ValueError("integer ranges cannot be empty")
        if len(text) > cls.MAX_INPUT_LENGTH:
            raise ValueError(
                f"integer ranges exceed the {cls.MAX_INPUT_LENGTH:,} character limit"
            )
        items = text.split(",")
        if len(items) > cls.MAX_SPANS:
            raise ValueError(f"integer ranges exceed the {cls.MAX_SPANS:,} span limit")
        spans = []
        for item in items:
            match = _INTEGER_RANGE_ITEM.fullmatch(item.strip())
            if not match:
                raise ValueError(f"invalid integer range: {item!r}")
            start = int(match.group("start"))
            end = int(match.group("end") or start)
            if end < start:
                raise ValueError(f"descending integer range: {start}-{end}")
            spans.append(IntegerSpan(start, end - start + 1))
        return tuple(spans)

    def __iter__(self):
        return iter(self._spans)

    def __len__(self):
        return len(self._spans)

    def __getitem__(self, index):
        return self._spans[index]

    def __repr__(self):
        return f"IntegerRanges({str(self)!r})"

    def __str__(self):
        return ",".join(map(str, self._spans))

    def __eq__(self, other):
        if isinstance(other, IntegerRanges):
            return self._spans == other._spans
        return NotImplemented

    @property
    def count(self) -> int:
        """Return the number of values across spans, including overlaps."""
        return sum(span.count for span in self._spans)

    @property
    def unique_count(self) -> int:
        """Return the number of distinct represented integers."""
        return self.merged().count

    def expand(self, *, limit: int = DEFAULT_EXPANSION_LIMIT) -> Iterator[int]:
        """Lazily yield values in span order, preserving overlaps and duplicates."""
        _validate_positive_integer(limit, "expansion limit")
        if self.count > limit:
            raise ValueError(
                f"integer ranges produce {self.count:,} values; "
                f"expansion limit is {limit:,}"
            )
        return (value for span in self._spans for value in span.values())

    def sample(
        self,
        count: int,
        *,
        seed: int | None = None,
        limit: int = DEFAULT_SAMPLE_LIMIT,
    ) -> list[int]:
        """Sample unique integers uniformly from the union of all spans."""
        _validate_non_negative_integer(count, "sample size")
        _validate_positive_integer(limit, "sample limit")
        if count > limit:
            raise ValueError(f"sample size {count:,} exceeds the limit of {limit:,}")
        merged = self.merged()
        total = merged.count
        if count > total:
            raise ValueError(
                f"cannot sample {count:,} unique values from {total:,} possibilities"
            )
        cumulative, running = [], 0
        for span in merged:
            running += span.count
            cumulative.append(running)
        results = []
        for index in _sample_indices(total, count, seed):
            span_index = bisect_right(cumulative, index)
            previous = cumulative[span_index - 1] if span_index else 0
            results.append(merged[span_index].start + index - previous)
        return results

    def sorted(self) -> IntegerRanges:
        """Return spans ordered by start and count without other changes."""
        return IntegerRanges(tuple(sorted(self._spans)))

    def unique(self) -> IntegerRanges:
        """Remove exact duplicate spans while preserving their first occurrence."""
        return IntegerRanges(tuple(dict.fromkeys(self._spans)))

    def merged(self, *, adjacent: bool = True) -> IntegerRanges:
        """Sort and combine overlapping, and optionally adjacent, spans."""
        ordered = sorted(self._spans)
        combined = [ordered[0]]
        for span in ordered[1:]:
            previous = combined[-1]
            joins = (
                span.start <= previous.stop if adjacent else span.start < previous.stop
            )
            if joins:
                stop = max(previous.stop, span.stop)
                combined[-1] = IntegerSpan(previous.start, stop - previous.start)
            else:
                combined.append(span)
        return IntegerRanges(tuple(combined))


def _validate_positive_integer(value: int, label: str):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")


def _validate_non_negative_integer(value: int, label: str):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")


def _sample_indices(total: int, count: int, seed: int | None) -> list[int]:
    """Use Floyd's algorithm to sample indices without allocating the domain."""
    generator = Random(seed)
    selected: set[int] = set()
    indices = []
    for upper in range(total - count, total):
        candidate = generator.randrange(upper + 1)
        index = upper if candidate in selected else candidate
        selected.add(index)
        indices.append(index)
    return indices


_Result = TypeVar("_Result")


class _FinitePattern(Generic[_Result]):
    """Shared lazy expansion and index-based sampling for finite patterns."""

    DEFAULT_EXPANSION_LIMIT = 65_536
    DEFAULT_SAMPLE_LIMIT = 65_536
    MAX_PATTERN_LENGTH = 4_096
    MAX_OUTPUT_UNITS = 4_096
    MAX_REPETITION = 1_024

    def __init__(self, source: str, parts: Sequence[Sequence[str]]):
        if not isinstance(source, str):
            raise TypeError(f"{type(self).__name__} requires a string")
        if not source:
            raise ValueError("pattern cannot be empty")
        if len(source) > self.MAX_PATTERN_LENGTH:
            raise ValueError(
                f"pattern exceeds the {self.MAX_PATTERN_LENGTH:,} character limit"
            )
        self.source = source
        self._parts = tuple(tuple(dict.fromkeys(part)) for part in parts)
        if not self._parts or any(not part for part in self._parts):
            raise ValueError("pattern must produce at least one value")
        self.count = prod(len(part) for part in self._parts)
        self.max_length = sum(max(map(len, part)) for part in self._parts)
        if self.max_length > self.MAX_OUTPUT_UNITS:
            raise ValueError(
                f"pattern output exceeds the {self.MAX_OUTPUT_UNITS:,} unit limit"
            )

    def __repr__(self):
        return f"{type(self).__name__}({self.source!r})"

    def expand(self, *, limit: int = DEFAULT_EXPANSION_LIMIT) -> Iterator[_Result]:
        """Return a lazy iterator after checking the complete result count."""
        self._validate_limit(limit, "expansion")
        if self.count > limit:
            raise ValueError(
                f"pattern produces {self.count:,} values; expansion limit is {limit:,}"
            )
        return (self._render(selection) for selection in product(*self._parts))

    def sample(
        self,
        count: int,
        *,
        seed: int | None = None,
        limit: int = DEFAULT_SAMPLE_LIMIT,
    ) -> list[_Result]:
        """Return unique uniformly selected results without full expansion."""
        self._validate_limit(count, "sample size", allow_zero=True)
        self._validate_limit(limit, "sample limit")
        if count > limit:
            raise ValueError(f"sample size {count:,} exceeds the limit of {limit:,}")
        if count > self.count:
            raise ValueError(
                f"cannot sample {count:,} unique values from "
                f"{self.count:,} possibilities"
            )
        generator = Random(seed)
        selected: set[int] = set()
        indices = []
        for upper in range(self.count - count, self.count):
            candidate = generator.randrange(upper + 1)
            index = upper if candidate in selected else candidate
            selected.add(index)
            indices.append(index)
        return [self._render_index(index) for index in indices]

    @staticmethod
    def _validate_limit(value: int, label: str, allow_zero: bool = False):
        minimum = 0 if allow_zero else 1
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            qualifier = "non-negative" if allow_zero else "positive"
            raise ValueError(f"{label} must be a {qualifier} integer")

    def _render_index(self, index: int) -> _Result:
        selection = [""] * len(self._parts)
        for position in range(len(self._parts) - 1, -1, -1):
            choices = self._parts[position]
            index, choice = divmod(index, len(choices))
            selection[position] = choices[choice]
        return self._render(selection)

    def _render(self, selection: Sequence[str]) -> _Result:
        raise NotImplementedError


_HEX_DIGITS = "0123456789abcdef"


def _fuzzy_hex_chunks(source: str) -> tuple[list[str], bool]:
    """Normalize HexBytes-style formatting into pattern chunks.

    The boolean result indicates that every chunk represents exactly one byte.
    """
    text = source.strip()
    if not text:
        raise ValueError("pattern cannot be empty")
    if text.startswith(r"\x"):
        chunks = text.split(r"\x")[1:]
        if not chunks or any(not chunk or r"\x" in chunk for chunk in chunks):
            raise ValueError("invalid \\xNN hexadecimal pattern notation")
        return chunks, True
    if "\\" in text:
        raise ValueError("only \\xNN escapes are valid in hexadecimal patterns")

    separators: list[tuple[int, str]] = []
    in_class = False
    for index, character in enumerate(text):
        if character == "[":
            in_class = True
        elif character == "]":
            in_class = False
        elif not in_class and character.isspace():
            separators.append((index, "space"))
        elif not in_class and character in ":_-":
            separators.append((index, character))
    kinds = {kind for _, kind in separators}
    if len(kinds) > 1:
        raise ValueError("hexadecimal pattern separators must be consistent")
    separator_kind = next(iter(kinds), None)

    if separator_kind is None:
        chunks = [text]
    elif separator_kind == "space":
        chunks = text.split()
    else:
        chunks = text.split(separator_kind)
    if any(not chunk for chunk in chunks):
        raise ValueError("hexadecimal pattern contains an empty byte group")

    prefixed = [chunk.lower().startswith("0x") for chunk in chunks]
    if any(prefixed):
        if len(chunks) == 1:
            chunks[0] = chunks[0][2:]
        elif separator_kind == "space" and all(prefixed):
            chunks = [chunk[2:] for chunk in chunks]
        else:
            raise ValueError(
                "use one leading 0x prefix or prefix every space-separated byte"
            )
    return chunks, len(chunks) > 1


def _repeat_previous(parts: list[tuple[str, ...]], source: str, index: int) -> int:
    """Apply a fixed ``{n}`` repetition at *index*, if present."""
    if index >= len(source) or source[index] != "{":
        return index
    end = source.find("}", index + 1)
    if end < 0 or not source[index + 1 : end].isdigit():
        return index
    count = int(source[index + 1 : end])
    if count > _FinitePattern.MAX_REPETITION:
        raise ValueError(
            f"repetition exceeds the {_FinitePattern.MAX_REPETITION:,} limit"
        )
    atom = parts.pop()
    parts.extend([atom] * count)
    return end + 1


def _hex_class(source: str, start: int) -> tuple[tuple[str, ...], int]:
    """Parse one nibble class and return its choices and next position."""
    end = source.find("]", start + 1)
    if end < 0:
        raise ValueError("unclosed hexadecimal character class")
    body = source[start + 1 : end]
    negated = body.startswith("!")
    body = body[1:] if negated else body
    if not body:
        raise ValueError("hexadecimal character class cannot be empty")
    choices: list[str] = []
    index = 0
    while index < len(body):
        first = body[index].lower()
        if first not in _HEX_DIGITS:
            raise ValueError(f"invalid hexadecimal class character: {body[index]!r}")
        if index + 1 < len(body) and body[index + 1] == "-":
            if index + 2 >= len(body):
                raise ValueError("hexadecimal range is missing its end")
            last = body[index + 2].lower()
            if last not in _HEX_DIGITS:
                raise ValueError(f"invalid hexadecimal range end: {body[index + 2]!r}")
            first_index, last_index = _HEX_DIGITS.index(first), _HEX_DIGITS.index(last)
            if first_index > last_index:
                raise ValueError(f"descending hexadecimal range: {first}-{last}")
            choices.extend(_HEX_DIGITS[first_index : last_index + 1])
            index += 3
        else:
            choices.append(first)
            index += 1
    unique = tuple(dict.fromkeys(choices))
    if negated:
        unique = tuple(
            character for character in _HEX_DIGITS if character not in unique
        )
    if not unique:
        raise ValueError("hexadecimal character class excludes every nibble")
    return unique, end + 1


class FuzzyHexPattern(_FinitePattern[bytes]):
    """Finite hexadecimal pattern with lazy expansion and sampling."""

    def __init__(self, source: str):
        if not isinstance(source, str):
            raise TypeError("FuzzyHexPattern requires a string")
        if len(source) > self.MAX_PATTERN_LENGTH:
            raise ValueError(
                f"pattern exceeds the {self.MAX_PATTERN_LENGTH:,} character limit"
            )
        chunks, byte_chunks = _fuzzy_hex_chunks(source)
        parts: list[tuple[str, ...]] = []
        for chunk in chunks:
            chunk_parts: list[tuple[str, ...]] = []
            index = 0
            while index < len(chunk):
                character = chunk[index]
                if character == "?":
                    chunk_parts.append(tuple(_HEX_DIGITS))
                    index += 1
                elif character == "[":
                    choices, index = _hex_class(chunk, index)
                    chunk_parts.append(choices)
                elif character.lower() in _HEX_DIGITS:
                    chunk_parts.append((character.lower(),))
                    index += 1
                else:
                    raise ValueError(
                        f"unexpected hexadecimal pattern character: {character!r}"
                    )
                index = _repeat_previous(chunk_parts, chunk, index)
            if byte_chunks and len(chunk_parts) != 2:
                raise ValueError(
                    "separated hexadecimal pattern groups must each produce one byte"
                )
            parts.extend(chunk_parts)
        if len(parts) % 2:
            raise ValueError("hexadecimal patterns must produce complete byte pairs")
        super().__init__(source, parts)

    def _render(self, selection: Sequence[str]) -> bytes:
        return bytes.fromhex("".join(selection))


_STRING_ALPHABET = ascii_letters + digits
_STRING_CLASSES = {
    "d": tuple(digits),
    "h": tuple(digits + "abcdefABCDEF"),
    "l": tuple(ascii_letters[:26]),
    "u": tuple(ascii_letters[26:]),
    "w": tuple(ascii_letters + digits + "_"),
    "s": (" ", "\t", "\r", "\n"),
}
_SIMPLE_ESCAPES = {"n": "\n", "r": "\r", "t": "\t"}


def _unicode_escape(source: str, index: int) -> tuple[str, int] | None:
    """Decode an x/u/U escape, returning ``None`` when it is a class shorthand."""
    marker = source[index]
    widths = {"x": 2, "u": 4, "U": 8}
    if marker not in widths:
        return None
    width = widths[marker]
    digits_value = source[index + 1 : index + 1 + width]
    if len(digits_value) != width or not _CONTIGUOUS.fullmatch(digits_value):
        return None
    character = chr(int(digits_value, 16))
    if 0xD800 <= ord(character) <= 0xDFFF:
        raise ValueError("Unicode surrogate code points are not valid string values")
    return character, index + 1 + width


def _string_escape(
    source: str, index: int, *, classes: bool = True
) -> tuple[tuple[str, ...], int]:
    """Parse an escape beginning immediately after its backslash."""
    if index >= len(source):
        raise ValueError("pattern cannot end with a backslash")
    decoded = _unicode_escape(source, index)
    if decoded:
        character, next_index = decoded
        return (character,), next_index
    marker = source[index]
    if (
        marker == "u"
        and classes
        and index + 1 < len(source)
        and source[index + 1].lower() in _HEX_DIGITS
    ):
        raise ValueError("invalid \\u Unicode escape")
    if classes and marker in _STRING_CLASSES:
        return _STRING_CLASSES[marker], index + 1
    if marker in _SIMPLE_ESCAPES:
        return (_SIMPLE_ESCAPES[marker],), index + 1
    if marker in r"?[]{}\,-!":
        return (marker,), index + 1
    if marker in "xU" or marker == "u" and not classes:
        raise ValueError(f"invalid \\{marker} Unicode escape")
    raise ValueError(f"unknown string pattern escape: \\{marker}")


def _string_class(source: str, start: int) -> tuple[tuple[str, ...], int]:
    """Parse an ASCII range or explicit Unicode character class."""
    tokens: list[tuple[str, bool]] = []
    index = start + 1
    negated = index < len(source) and source[index] == "!"
    index += int(negated)
    while index < len(source) and source[index] != "]":
        if source[index] == "\\":
            choices, index = _string_escape(source, index + 1, classes=False)
            tokens.append((choices[0], True))
        else:
            tokens.append((source[index], False))
            index += 1
    if index >= len(source):
        raise ValueError("unclosed string character class")
    if not tokens:
        raise ValueError("string character class cannot be empty")
    choices: list[str] = []
    position = 0
    while position < len(tokens):
        first, _ = tokens[position]
        if position + 2 < len(tokens) and tokens[position + 1] == ("-", False):
            last = tokens[position + 2][0]
            if ord(first) > 127 or ord(last) > 127:
                raise ValueError("string ranges are limited to ASCII characters")
            if ord(first) > ord(last):
                raise ValueError(f"descending string range: {first}-{last}")
            choices.extend(chr(value) for value in range(ord(first), ord(last) + 1))
            position += 3
        else:
            choices.append(first)
            position += 1
    unique = tuple(dict.fromkeys(choices))
    if negated:
        unique = tuple(
            character for character in _STRING_ALPHABET if character not in unique
        )
    if not unique:
        raise ValueError(
            "string character class excludes the complete default alphabet"
        )
    return unique, index + 1


def _string_alternatives(source: str, start: int) -> tuple[tuple[str, ...], int]:
    """Parse a comma-separated group of escaped literal alternatives."""
    alternatives, current = [], []
    index = start + 1
    while index < len(source) and source[index] != "}":
        if source[index] == ",":
            if not current:
                raise ValueError("string alternatives cannot be empty")
            alternatives.append("".join(current))
            current = []
            index += 1
        elif source[index] == "\\":
            choices, index = _string_escape(source, index + 1, classes=False)
            current.append(choices[0])
        elif source[index] in "{[?":
            raise ValueError("patterns inside alternatives must be escaped")
        else:
            current.append(source[index])
            index += 1
    if index >= len(source):
        raise ValueError("unclosed string alternative group")
    if not current:
        raise ValueError("string alternatives cannot be empty")
    alternatives.append("".join(current))
    unique = tuple(dict.fromkeys(alternatives))
    if any(
        first != second and second.startswith(first)
        for first in unique
        for second in unique
    ):
        raise ValueError("string alternatives cannot be prefixes of other alternatives")
    return unique, index + 1


class FuzzyStringPattern(_FinitePattern[str]):
    """Finite Unicode string pattern with ASCII-bounded generated classes."""

    def __init__(self, source: str):
        if not isinstance(source, str):
            raise TypeError("FuzzyStringPattern requires a string")
        if len(source) > self.MAX_PATTERN_LENGTH:
            raise ValueError(
                f"pattern exceeds the {self.MAX_PATTERN_LENGTH:,} character limit"
            )
        parts: list[tuple[str, ...]] = []
        index = 0
        while index < len(source):
            character = source[index]
            if character == "?":
                parts.append(tuple(_STRING_ALPHABET))
                index += 1
            elif character == "[":
                choices, index = _string_class(source, index)
                parts.append(choices)
            elif character == "{":
                choices, index = _string_alternatives(source, index)
                parts.append(choices)
            elif character == "\\":
                choices, index = _string_escape(source, index + 1)
                parts.append(choices)
            elif character in "]}":
                raise ValueError(f"unexpected string pattern character: {character!r}")
            elif 0xD800 <= ord(character) <= 0xDFFF:
                raise ValueError(
                    "Unicode surrogate code points are not valid string values"
                )
            else:
                parts.append((character,))
                index += 1
            index = _repeat_previous(parts, source, index)
        super().__init__(source, parts)
        self.max_utf8_bytes = sum(
            max(len(choice.encode("utf-8")) for choice in part) for part in self._parts
        )

    def _render(self, selection: Sequence[str]) -> str:
        return "".join(selection)


__all__ = [
    "FuzzyHexPattern",
    "FuzzyStringPattern",
    "HexBytes",
    "IntegerRanges",
    "IntegerSpan",
]
