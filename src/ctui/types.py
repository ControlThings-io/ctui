"""Reusable command parameter types and their parsing contracts.

Use these types directly as command parameter annotations. Conversion validates
syntax before calling the command; application-specific constraints belong in
argument validators or the command itself. Patterns and integer ranges retain
compact representations so parsing does not allocate every possible result.
"""

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
_BYTE_COMPONENT = re.compile(
    r"(?:0x[0-9a-f]+|0b_?[01](?:_?[01])*|0o[0-7]+|[0-9]+)", re.IGNORECASE
)
_SEPARATED_BYTES = re.compile(
    r"[0-9a-fA-F]{2}(?P<separator>[:_-])[0-9a-fA-F]{2}"
    r"(?:(?P=separator)[0-9a-fA-F]{2})*"
)


class HexBytes(bytes):
    r"""Immutable bytes parsed from common hexadecimal text representations.

    Plain hex ignores whitespace even within byte pairs: ``dead b e ef``
    becomes ``deadbeef``. The total digit count must be even. Standalone
    ``0xdeadbeef`` retains this contiguous multi-byte meaning.

    If any whitespace-separated component has a ``0x``, ``0b``, or ``0o``
    prefix, each component is one byte (0..255); unprefixed components are
    decimal. For example, ``0xbe 0b10101100 10 0o377`` becomes ``be ac 0a ff``.
    Binary underscores follow Python placement rules. Prefixes and hex digits
    are case-insensitive. Bare ``10 20`` remains hexadecimal, not decimal.

    Colon, hyphen, and underscore-separated hex byte pairs and adjacent
    ``\xde\xad`` escapes remain separate formats; do not mix them with radix
    components. No padding or byte-order inference occurs. Quote command input
    containing spaces or backslashes using single or double quotes.

    Existing bytes, bytearray, and memoryview values are also accepted, including
    empty values; the no-argument constructor produces empty bytes. The immutable
    bytes subclass works directly with byte-oriented APIs. For mutation, callers
    can explicitly construct a bytearray from it.
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
        components = text.split()
        if len(components) == 1 and text.lower().startswith("0x"):
            digits = text[2:]
            if not _CONTIGUOUS.fullmatch(digits) or len(digits) % 2:
                raise ValueError("0x must be followed by an even number of hex digits")
            return bytes.fromhex(digits)
        if any(part.lower().startswith(("0x", "0b", "0o")) for part in components):
            result = []
            for part in components:
                if not _BYTE_COMPONENT.fullmatch(part):
                    raise ValueError(f"Invalid byte component: {part!r}")
                base = {"0x": 16, "0b": 2, "0o": 8}.get(part[:2].lower(), 10)
                number = int(part, base)
                if not 0 <= number <= 255:
                    raise ValueError(
                        f"Byte component must be between 0 and 255: {part!r}"
                    )
                result.append(number)
            return bytes(result)
        compact = "".join(components)
        if _CONTIGUOUS.fullmatch(compact):
            if len(compact) % 2:
                raise ValueError("hexadecimal input must contain complete byte pairs")
            return bytes.fromhex(compact)
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
    """One inclusive input range represented by its start and value count.

    Store a non-negative integer start and a positive integer count; booleans
    are rejected. Instances are frozen and ordered by start, then count.
    Start/count matches protocol requests without allocating individual values.
    The derived stop is exclusive, matching Python's range convention:
    textual ``15-20`` corresponds to ``IntegerSpan(15, 6)`` with stop 21.
    """

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
        """Return a compact Python range from start up to, but excluding, stop."""
        return range(self.start, self.stop)

    def __str__(self):
        return str(self.start) if self.count == 1 else f"{self.start}-{self.stop - 1}"


_INTEGER_RANGE_ITEM = re.compile(r"(?P<start>\d+)(?:\s*-\s*(?P<end>\d+))?")


class IntegerRanges:
    """Ordered collection of compact, non-negative inclusive integer ranges.

    Accept comma-separated text or a nonempty sequence of IntegerSpan objects.
    For example, ``0-5,9,15-20`` stores spans (0, 6), (9, 1), and (15, 6).
    Text endpoints are inclusive; singletons have count 1. Whitespace around
    commas and hyphens is accepted. Empty entries, negative integers, descending
    ranges, and other notation are rejected.

    Iteration, indexing, and len operate on spans, not expanded integers.
    Preserve input order, overlaps, and duplicates because callers may intend
    repeated operations. The stored spans are immutable; sorted(), unique(),
    and merged() return new collections without modifying the original.
    Use ordinary list[int] annotations for comma-separated integers alone.

    count includes repeated values; unique_count counts their union. expand()
    is lazy and bounded, while sample() selects from the union without expanding
    it. Both default to a 65,536-result limit. Input is limited to 4,096
    characters after stripping outer whitespace and at most 4,096 spans.
    source retains the original text, or canonical text for supplied spans.
    """

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
        """Lazily yield values in span order, preserving overlaps and duplicates.

        Raise ValueError before returning an iterator if the complete count
        exceeds limit; this is a guard, not truncation. The positive integer
        limit defaults to 65,536 and may be explicitly overridden.
        """
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
        """Return a list of unique integers sampled uniformly from the union.

        Overlaps and duplicate spans do not give values extra weight. Sampling
        uses compact merged spans without expanding the domain. An optional
        seed makes repeated calls reproducible; count zero returns an empty list.
        Raise ValueError for a negative count, a non-positive limit, or a count
        exceeding unique_count or limit (default 65,536).
        """
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
        """Return a new collection ordered by start, then count.

        Preserve duplicates and overlaps; do not merge spans.
        """
        return IntegerRanges(tuple(sorted(self._spans)))

    def unique(self) -> IntegerRanges:
        """Return a new collection keeping only the first of each exact span.

        Preserve order and leave overlaps intact. For example, ``0-5,0-5,3-7``
        becomes ``0-5,3-7``; use merged() to combine overlapping values.
        """
        return IntegerRanges(tuple(dict.fromkeys(self._spans)))

    def merged(self, *, adjacent: bool = True) -> IntegerRanges:
        """Return a new collection with sorted, combined spans.

        Merge overlaps and, by default, adjacent spans: ``0-5,3-7,8`` becomes
        ``0-8``. With adjacent=False it becomes ``0-7,8``.
        """
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
        """Return a lazy iterator after checking the complete result count.

        Raise ValueError immediately if count exceeds the positive integer
        limit (default 65,536); never silently truncate. Choices expand in
        their stored order, with the rightmost position varying fastest.
        Results are bytes for FuzzyHexPattern and str for FuzzyStringPattern.
        """
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
        """Return a list of unique uniformly sampled results without expansion.

        Sample combination indices so even a huge domain need not be enumerated.
        An optional seed makes repeated calls reproducible. count may be zero,
        but must not exceed the available combinations or the positive integer
        limit (default 65,536); invalid counts or limits raise ValueError.
        Results are bytes for FuzzyHexPattern and str for FuzzyStringPattern.
        """
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
    r"""Finite hexadecimal pattern producing bytes through expansion or sampling.

    Each atom denotes one nibble: a literal hex digit, ``?`` for 0-f, a class
    such as ``[015a]``, inclusive ranges such as ``[0-5a-f]``, or a negated
    class such as ``[!0f]``. Hex digits are case-insensitive; duplicate class
    choices are removed. Fixed ``{n}`` repetition repeats the preceding nibble
    atom, not a byte: ``?{4}`` produces two bytes, and ``0{2}`` produces one.
    Zero repetitions remove the atom, but the whole pattern must remain nonempty.

    Concrete text formats match HexBytes, including prefixes and escapes.
    Fuzzy forms include ``0xf?``, ``0xde 0x??``, and ``\xde\x??``. Separators
    must consistently divide complete bytes; mixed separators and nibble-level
    groups such as ``f-f`` are rejected. A hyphen denotes a range only inside
    a class. All results must contain complete byte pairs.

    This finite language excludes general regex groups, alternation, and
    unbounded repetition. Parsing retains source and computes exact count
    without expanding results. expand() is lazy and sample() draws unique
    values without full enumeration; randomness is an operation, not syntax.
    Both operations default to a 65,536-result limit.

    Source length and output length are each limited to 4,096 units; output
    units and max_length count nibbles, not bytes. A fixed repetition is limited
    to 1,024. Quote command input containing spaces or backslashes.
    """

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
    r"""Finite Unicode string pattern with ASCII-bounded generated classes.

    Produce str values; callers choose the encoding. Preserve literal Unicode
    code points without normalization, including explicit classes such as
    ``[éè]``. Separators, spaces, and punctuation remain literal text outside
    pattern syntax. Generated ranges such as ``[a-z]`` are inclusive and
    restricted to ASCII; ``?`` selects from ASCII a-z, A-Z, and 0-9.
    Negated classes such as ``[!abc]`` exclude from that same default alphabet.

    Shorthand classes are ``\d`` (0-9), ``\h`` (0-9, a-f, A-F), ``\l`` (a-z),
    ``\u`` (A-Z), ``\w`` (ASCII letters, digits, underscore), and ``\s`` (space,
    tab, carriage return, newline). Escapes include ``\n``, ``\r``, ``\t``,
    ``\xNN``, ``\uNNNN``, ``\UNNNNNNNN``, and escaped syntax characters.
    A complete four-digit Unicode escape takes precedence over the uppercase
    shorthand; an incomplete \u escape starting with a hex digit is rejected.
    Quote command input containing spaces or backslashes.

    Literal alternatives such as ``{admin,user}`` may have different lengths.
    They cannot be empty, nest patterns, or prefix one another; the prefix
    restriction keeps combination counts and unique sampling unambiguous.
    Classes and alternatives deduplicate choices. Shorthand classes are not
    expanded inside classes or alternatives; literal escapes are supported.
    Fixed ``{n}`` repeats the preceding atom, including an alternative group.
    Zero removes that atom, but the whole pattern must remain nonempty.
    General regex operators do not enable unbounded generation.

    Parsing retains source and computes exact count without expansion. expand()
    lazily yields strings and sample() returns unique strings without enumerating
    the domain; both default to a 65,536-result limit. Source and maximum output
    length are each limited to 4,096 code points; repetitions are limited to
    1,024. max_length reports code points, and max_utf8_bytes reports the largest
    encoded result size, not an additional enforced byte limit. Surrogate code
    points are not supported.
    """

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
