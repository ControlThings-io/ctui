r"""Lazily expand or sample finite hexadecimal and string patterns.

Run: uv run examples/06_fuzzy_patterns.py
Try: hex expand 56ffff07f[0-2]01
Try: hex expand '0x56ffff07f[0-2]01'
Try: hex expand '\x56\xff\xff\x07\xf?\x01'
Try: hex sample ???????? --count 5 --seed 42
Try: text expand {admin,user}-[1-2]
Try: text sample 'device-\d{4}' -n 5

Expansion refuses patterns above its limit before iteration begins. Commands
translate these ValueErrors into CommandErrors for a concise UI error dialog. Sampling
selects unique values without constructing the complete expansion.
Hex separators must divide complete bytes, and ``{n}`` repeats one nibble.

The parsed object retains a finite set, not a precomputed list. count can be
inspected before choosing expand() or sample(); this tutorial limits expansion
to 1,024 results unless overridden. Joining results for display still builds an
output string, so laziness does not make unlimited terminal output inexpensive.
String results preserve explicit Unicode; automatic wildcard alphabets are ASCII.
"""

from ctui import (
    Argument,
    CommandError,
    CtuiApp,
    FuzzyHexPattern,
    FuzzyStringPattern,
    command,
)


class PatternTool(CtuiApp):
    """Demonstrate bounded expansion and efficient random sampling."""

    @command(
        name="hex expand",
        arguments={"limit": Argument(flags=("-n", "--limit"))},
    )
    def hex_expand(self, pattern: FuzzyHexPattern, limit: int = 1_024) -> str:
        """Expand a hexadecimal pattern into immutable bytes."""
        try:
            expanded = pattern.expand(limit=limit)
        except ValueError as error:
            raise CommandError(str(error)) from error
        values = (payload.hex(" ") for payload in expanded)
        return f"{pattern.count:,} possibilities\n" + "\n".join(values)

    @command(
        name="hex sample",
        arguments={
            "count": Argument(flags=("-n", "--count")),
            "seed": Argument(flags=("-s", "--seed")),
        },
    )
    def hex_sample(
        self, pattern: FuzzyHexPattern, count: int = 10, seed: int | None = None
    ) -> str:
        """Sample unique byte values without performing full expansion."""
        try:
            return "\n".join(
                payload.hex(" ") for payload in pattern.sample(count, seed=seed)
            )
        except ValueError as error:
            raise CommandError(str(error)) from error

    @command(
        name="text expand",
        arguments={"limit": Argument(flags=("-n", "--limit"))},
    )
    def text_expand(self, pattern: FuzzyStringPattern, limit: int = 1_024) -> str:
        """Expand a finite Unicode string pattern."""
        try:
            expanded = pattern.expand(limit=limit)
        except ValueError as error:
            raise CommandError(str(error)) from error
        return f"{pattern.count:,} possibilities\n" + "\n".join(expanded)

    @command(
        name="text sample",
        arguments={
            "count": Argument(flags=("-n", "--count")),
            "seed": Argument(flags=("-s", "--seed")),
        },
    )
    def text_sample(
        self, pattern: FuzzyStringPattern, count: int = 10, seed: int | None = None
    ) -> str:
        """Sample unique strings without performing full expansion."""
        try:
            return "\n".join(pattern.sample(count, seed=seed))
        except ValueError as error:
            raise CommandError(str(error)) from error


if __name__ == "__main__":
    PatternTool().run()
