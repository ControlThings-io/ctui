import unittest
from collections.abc import Iterator

from ctui import FuzzyHexPattern, FuzzyStringPattern, HexBytes
from ctui.commands import Command


class HexBytesTests(unittest.TestCase):
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


class FuzzyHexPatternTests(unittest.TestCase):
    def test_literals_wildcards_classes_ranges_negation_and_repetition(self):
        pattern = FuzzyHexPattern("56:ff:ff:07:f[0-2]0{2}")
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
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                FuzzyHexPattern(value)


class FuzzyStringPatternTests(unittest.TestCase):
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
