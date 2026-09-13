import unittest

from ctui import HexBytes
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


if __name__ == "__main__":
    unittest.main()
