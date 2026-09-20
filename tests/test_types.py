"""Contracts for hex bytes, finite patterns, and compact integer ranges.

Compare concrete/fuzzy hex syntax, require complete byte pairs, and exercise
Unicode literals with ASCII generation. Expansion tests check laziness and limits;
sampling tests use huge domains to guard against accidental enumeration. Range
transformations must preserve the original collection and distinguish exact-span
deduplication from merging the represented union.
"""

import unittest
from collections.abc import Iterator

from ctui import (
    FuzzyHexPattern,
    FuzzyStringPattern,
    HexBytes,
    IntegerRanges,
    IntegerSpan,
)
from ctui.commands import Command


class HexBytesTests(unittest.TestCase):
    """Protect accepted byte notation and rejection of ambiguous text."""

    def test_common_hexadecimal_representations(self):
        expected = b"\xde\xad\xbe\xef"
        values = (
            "deadbeef",
            "DEADBEEF",
            "de ad be ef",
            "de  ad\tbe ef",
            "de:ad:be:ef",
            "de-ad-be-ef",
            "de_ad_be_ef",
            "0xdeadbeef",
            "0XDEADBEEF",
            "0xde 0xad 0xbe 0xef",
            "0XDE 0XAD 0XBE 0XEF",
            r"\xde\xad\xbe\xef",
        )
        for value in values:
            with self.subTest(value=value):
                result = HexBytes(value)
                self.assertEqual(result, expected)
                self.assertIsInstance(result, bytes)

    def test_whitespace_and_mixed_radix_bytes(self):
        for value in ("dead beef", "deadbe ef", "dead b e ef", "dead   b e      ef"):
            self.assertEqual(HexBytes(value), bytes.fromhex("deadbeef"))
        for value, expected in (
            ("0xbe 0b10101100 0xef 10 0o377", "beacef0aff"),
            ("0xbe   0xef   0b1010_001_1", "beefa3"),
            ("0b_10100011", "a3"),
            ("0B10100011 0O377 0XBE 00010", "a3ffbe0a"),
            ("10 20", "1020"),
            ("0xbe 10 20", "be0a14"),
        ):
            self.assertEqual(HexBytes(value), bytes.fromhex(expected))

        def send(payload: HexBytes):
            return payload

        for quote in ("'", '"'):
            for value in ("dead b e ef", "0xbe 0b10101100 10 0o377"):
                parsed = Command(send).parse_args(quote + value + quote)
                self.assertEqual(parsed["payload"], HexBytes(value))

    def test_invalid_radix_components(self):
        for value in (
            "0b1010__0011",
            "0b101_",
            "0b__101",
            "0b102",
            "0o378",
            "0xbe 256",
            "0xbe -1",
            "0xbe +1",
            "0b100000000",
            "0o400",
            "0xbe 0xdead",
            "0xbe ef",
            "0xbe de:ad",
            "0xbe 1_0",
            r"0xbe \xad",
            "de: ad",
            "0xdead beef",
            "dead b",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                HexBytes(value)

    def test_bytes_like_values_can_be_wrapped_without_text_conversion(self):
        self.assertEqual(HexBytes(b"\x01\x02"), b"\x01\x02")
        self.assertEqual(HexBytes(bytearray((1, 2))), b"\x01\x02")
        self.assertEqual(HexBytes(memoryview(b"\x01\x02")), b"\x01\x02")

    def test_empty_odd_mixed_and_unsupported_inputs_are_rejected(self):
        for value in (
            "",
            "abc",
            "0x123",
            "0xde 0x123",
            "de0xad",
            "de:ad-be",
            "de,ad,be,ef",
            r'b"\xde\xad\xbe\xef"',
            "[0xde, 0xad]",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                HexBytes(value)
        with self.assertRaises(TypeError):
            HexBytes(123)

    def test_command_annotation_performs_conversion(self):
        def send(payload: HexBytes):
            return payload

        result = Command(send).parse_args(r"'\xde\xad\xbe\xef'")
        self.assertEqual(result, {"payload": b"\xde\xad\xbe\xef"})
        self.assertIsInstance(result["payload"], HexBytes)


class IntegerRangesTests(unittest.TestCase):
    """Protect inclusive span parsing, explicit normalization, and union sampling."""

    def test_parsing_preserves_order_and_represents_inclusive_ranges(self):
        ranges = IntegerRanges("0-5,9,15-20,75,10-12")
        self.assertEqual(
            list(ranges),
            [
                IntegerSpan(0, 6),
                IntegerSpan(9, 1),
                IntegerSpan(15, 6),
                IntegerSpan(75, 1),
                IntegerSpan(10, 3),
            ],
        )
        self.assertEqual(ranges.count, 17)
        self.assertEqual(str(ranges), "0-5,9,15-20,75,10-12")
        self.assertEqual(ranges[0].stop, 6)
        self.assertEqual(list(ranges[0].values()), list(range(6)))

    def test_sorted_unique_and_merged_return_new_collections(self):
        ranges = IntegerRanges("0-5,9,15-20,75,10-12,3-7,9")
        self.assertEqual(str(ranges.sorted()), "0-5,3-7,9,9,10-12,15-20,75")
        self.assertEqual(str(ranges.unique()), "0-5,9,15-20,75,10-12,3-7")
        self.assertEqual(str(ranges.merged()), "0-7,9-12,15-20,75")
        self.assertEqual(str(ranges.merged(adjacent=False)), "0-7,9,10-12,15-20,75")
        self.assertEqual(str(ranges), "0-5,9,15-20,75,10-12,3-7,9")

    def test_expansion_is_lazy_bounded_and_preserves_duplicate_values(self):
        ranges = IntegerRanges("1-3,2-4")
        expanded = ranges.expand()
        self.assertIsInstance(expanded, Iterator)
        self.assertEqual(list(expanded), [1, 2, 3, 2, 3, 4])
        self.assertEqual(ranges.count, 6)
        self.assertEqual(ranges.unique_count, 4)
        with self.assertRaisesRegex(ValueError, "expansion limit"):
            ranges.expand(limit=5)

    def test_sampling_uses_unique_union_without_full_expansion(self):
        ranges = IntegerRanges("0-5,3-7")
        sample = ranges.sample(8, seed=42)
        self.assertEqual(set(sample), set(range(8)))
        self.assertEqual(sample, ranges.sample(8, seed=42))
        with self.assertRaisesRegex(ValueError, "8 possibilities"):
            ranges.sample(9)
        huge = IntegerRanges("0-999999999999999999999")
        self.assertEqual(len(huge.sample(5, seed=42)), 5)

    def test_invalid_ranges_and_spans_are_rejected(self):
        for value in ("", "1,", ",1", "1,,2", "5-3", "-1", "one", "1-2-3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                IntegerRanges(value)
        with self.assertRaises(ValueError):
            IntegerSpan(0, 0)
        with self.assertRaises(ValueError):
            IntegerSpan(-1, 1)
        with self.assertRaises(TypeError):
            IntegerRanges([range(3)])

    def test_command_annotation_performs_conversion(self):
        def scan(ranges: IntegerRanges):
            return ranges

        result = Command(scan).parse_args("0-5,9,15-20")["ranges"]
        self.assertIsInstance(result, IntegerRanges)
        self.assertEqual(result.count, 13)


class FuzzyHexPatternTests(unittest.TestCase):
    """Protect nibble semantics and formatting compatibility with HexBytes."""

    def test_flexible_plain_pattern_whitespace(self):
        expected = list(FuzzyHexPattern("dead[0-3]?{2}0").expand())
        for text in (
            "de ad [0-3] ?{2} 0",
            "d e a d [0-3] ? {2} 0",
            "de\tad  [0-3]\n?{2} 0",
        ):
            self.assertEqual(list(FuzzyHexPattern(text).expand()), expected)
        for text in (
            "[0 -3]?",
            "[0-3 ]?",
            "?{ 2}",
            "?{2 }",
            "d e a",
            "0xde a d",
            "de: ad",
            r"\xde \xad",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                FuzzyHexPattern(text)

        def expand(pattern: FuzzyHexPattern):
            return pattern

        for quote in ("'", '"'):
            parsed = Command(expand).parse_args(quote + "d e a d" + quote)
            self.assertEqual(list(parsed["pattern"].expand()), [bytes.fromhex("dead")])
        self.assertEqual(list(FuzzyStringPattern("a b").expand()), ["a b"])

    def test_literals_wildcards_classes_ranges_negation_and_repetition(self):
        pattern = FuzzyHexPattern("56:ff:ff:07:f[0-2]:0{2}")
        self.assertEqual(pattern.count, 3)
        self.assertEqual(
            list(pattern.expand()),
            [
                bytes.fromhex("56ffff07f000"),
                bytes.fromhex("56ffff07f100"),
                bytes.fromhex("56ffff07f200"),
            ],
        )
        self.assertEqual(FuzzyHexPattern("f?").count, 16)
        self.assertEqual(FuzzyHexPattern("[!0]0").count, 15)
        self.assertEqual(FuzzyHexPattern("[0-3a-c]0").count, 7)

    def test_hexbytes_formatting_conventions_are_shared(self):
        expected = b"\xde\xad\xbe\xef"
        values = (
            "deadbeef",
            "DEADBEEF",
            "de ad be ef",
            "de:ad:be:ef",
            "de-ad-be-ef",
            "de_ad_be_ef",
            "0xdeadbeef",
            "0xde 0xad 0xbe 0xef",
            r"\xde\xad\xbe\xef",
        )
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(HexBytes(value), expected)
                self.assertEqual(list(FuzzyHexPattern(value).expand()), [expected])

    def test_prefix_and_escape_notation_can_contain_fuzzy_nibbles(self):
        self.assertEqual(FuzzyHexPattern("0xdeadbe??").count, 256)
        self.assertEqual(FuzzyHexPattern("0xde 0xad 0x??").count, 256)
        self.assertEqual(FuzzyHexPattern(r"\xde\xad\x??").count, 256)

    def test_expansion_is_lazy_bounded_and_requires_complete_bytes(self):
        pattern = FuzzyHexPattern("????")
        expanded = pattern.expand()
        self.assertIsInstance(expanded, Iterator)
        self.assertEqual(next(expanded), b"\x00\x00")
        with self.assertRaisesRegex(ValueError, "expansion limit"):
            pattern.expand(limit=255)
        with self.assertRaisesRegex(ValueError, "complete byte pairs"):
            FuzzyHexPattern("?")

    def test_sampling_is_unique_deterministic_and_does_not_expand(self):
        pattern = FuzzyHexPattern("?{20}")
        first = pattern.sample(20, seed=42)
        self.assertEqual(first, pattern.sample(20, seed=42))
        self.assertEqual(len(first), len(set(first)))
        with self.assertRaisesRegex(ValueError, "sample size"):
            pattern.sample(2, limit=1)

    def test_invalid_hex_patterns_are_rejected(self):
        for value in (
            "",
            "[",
            "[]0",
            "[f-0]0",
            "[!0123456789abcdef]0",
            "gg",
            "d:e:a:d",
            "f-f",
            "de:ad-be:ef",
            "de ad-be_ef",
            "0xde ad",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                FuzzyHexPattern(value)


class FuzzyStringPatternTests(unittest.TestCase):
    """Protect finite Unicode text generation and bounded ASCII classes."""

    def test_literals_ascii_features_unicode_and_fixed_repetition(self):
        pattern = FuzzyStringPattern("{admin,user}-[1-2]é")
        self.assertEqual(pattern.count, 4)
        self.assertEqual(
            list(pattern.expand()),
            ["admin-1é", "admin-2é", "user-1é", "user-2é"],
        )
        self.assertEqual(
            list(FuzzyStringPattern(r"A\d{2}").expand(limit=100)),
            [f"A{value:02d}" for value in range(100)],
        )
        self.assertEqual(list(FuzzyStringPattern("caf[éè]").expand()), ["café", "cafè"])
        self.assertEqual(list(FuzzyStringPattern(r"\?\[\\").expand()), ["?[\\"])

    def test_predefined_classes_and_unicode_escapes(self):
        self.assertEqual(FuzzyStringPattern(r"\h").count, 22)
        self.assertEqual(FuzzyStringPattern(r"\l").count, 26)
        self.assertEqual(FuzzyStringPattern(r"\u").count, 26)
        self.assertEqual(FuzzyStringPattern(r"\w").count, 63)
        self.assertEqual(FuzzyStringPattern(r"\s").count, 4)
        self.assertEqual(list(FuzzyStringPattern(r"\x41\u00e9").expand()), ["Aé"])
        self.assertEqual(FuzzyStringPattern("?").count, 62)

    def test_negation_sampling_and_size_metadata(self):
        pattern = FuzzyStringPattern("ID-[!0]{2}")
        self.assertEqual(pattern.count, 61**2)
        self.assertEqual(pattern.max_length, 5)
        self.assertEqual(pattern.max_utf8_bytes, 5)
        sample = pattern.sample(25, seed=7)
        self.assertEqual(sample, pattern.sample(25, seed=7))
        self.assertEqual(len(sample), len(set(sample)))

    def test_invalid_string_patterns_and_protections_are_rejected(self):
        for value in (
            "",
            "[abc",
            "{one,}",
            "{a,ab}",
            "[z-a]",
            "[α-ω]",
            "\\q",
            r"\u12",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                FuzzyStringPattern(value)
        with self.assertRaisesRegex(ValueError, "repetition"):
            FuzzyStringPattern("a{1025}")
        with self.assertRaisesRegex(ValueError, "expansion limit"):
            FuzzyStringPattern("?{4}").expand(limit=100)

    def test_command_annotations_perform_pattern_conversion(self):
        def fuzz_hex(pattern: FuzzyHexPattern):
            return pattern

        def fuzz_text(pattern: FuzzyStringPattern):
            return pattern

        hexadecimal = Command(fuzz_hex).parse_args("f?")["pattern"]
        text = Command(fuzz_text).parse_args("user[0-2]")["pattern"]
        self.assertIsInstance(hexadecimal, FuzzyHexPattern)
        self.assertIsInstance(text, FuzzyStringPattern)
        self.assertEqual(hexadecimal.count, 16)
        self.assertEqual(text.count, 3)


if __name__ == "__main__":
    unittest.main()
