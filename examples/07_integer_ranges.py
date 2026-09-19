"""Parse, inspect, transform, expand, and sample inclusive integer ranges.

Run: uv run examples/07_integer_ranges.py
Try: inspect 0-5,9,15-20,75,10-12
Try: transform 0-5,9,15-20,75,10-12,3-7,9
Try: expand 0-5,9
Try: sample 0-1000000000 --count 5 --seed 42

The command annotation performs conversion before each function runs. Range
objects preserve entered order and avoid allocating every represented integer.

Iteration yields spans, with inclusive textual endpoints and an exclusive stop.
Sorting, exact-span deduplication, and merging return new collections. Sampling
uses the union of values so overlaps do not bias selection; a seed makes repeated
calls reproducible. Expansion has a guard, not a truncation count.
"""

from ctui import Argument, CtuiApp, IntegerRanges, command


class RangeTool(CtuiApp):
    """Demonstrate compact integer ranges and their safe operations."""

    @command
    def inspect(self, ranges: IntegerRanges) -> str:
        """Show each inclusive range as start, count, and exclusive stop."""
        lines = ["range   start  count  stop (exclusive)"]
        lines.extend(
            f"{str(span):<7} {span.start:<6} {span.count:<6} {span.stop}"
            for span in ranges
        )
        lines.append(f"{ranges.count:,} entered values")
        lines.append(f"{ranges.unique_count:,} unique values")
        return "\n".join(lines)

    @command
    def transform(self, ranges: IntegerRanges) -> str:
        """Compare non-mutating sorting, deduplication, and merging."""
        return "\n".join(
            (
                f"original: {ranges}",
                f"sorted:   {ranges.sorted()}",
                f"unique:   {ranges.unique()}",
                f"merged:   {ranges.merged()}",
                f"overlap:  {ranges.merged(adjacent=False)}",
            )
        )

    @command(
        arguments={"limit": Argument(flags=("-n", "--limit"))},
    )
    def expand(self, ranges: IntegerRanges, limit: int = 1_000) -> str:
        """Lazily expand ranges while enforcing a complete-result limit."""
        return ", ".join(str(value) for value in ranges.expand(limit=limit))

    @command(
        arguments={
            "count": Argument(flags=("-n", "--count")),
            "seed": Argument(flags=("-s", "--seed")),
        },
    )
    def sample(
        self, ranges: IntegerRanges, count: int = 10, seed: int | None = None
    ) -> str:
        """Select unique integers without expanding the complete range set."""
        return ", ".join(str(value) for value in ranges.sample(count, seed=seed))


if __name__ == "__main__":
    RangeTool().run()
