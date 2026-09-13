import unittest
from enum import Enum
from pathlib import Path
from typing import Literal

from ctui.commands import (
    Argument,
    Command,
    CommandNotFound,
    Commands,
    CommandValidationError,
)


class Color(Enum):
    red = 1
    blue = 2


class CommandTests(unittest.IsolatedAsyncioTestCase):
    def test_names_signatures_aliases_and_longest_match(self):
        commands = Commands()

        @commands.register(aliases=("cp",))
        def copy_file(source: Path, force: bool = False):
            return source, force

        self.assertEqual(commands["copy file"].name, "copy file")
        item, args = commands.resolve("cp one.txt --force")
        self.assertEqual(args, "one.txt --force")
        self.assertIs(item, commands["copy file"])

    def test_partial_subcommand_prefers_longest_command_depth(self):
        commands = Commands()

        @commands.register(name="configs")
        def configs():
            pass

        @commands.register(name="configs list")
        def configs_list():
            pass

        @commands.register(name="project")
        def project():
            pass

        @commands.register(name="project list")
        def project_list():
            pass

        @commands.register(name="project load")
        def project_load():
            pass

        item, arguments = commands.resolve("conf l")
        self.assertIs(item, commands["configs list"])
        self.assertEqual(arguments, "")

        item, arguments = commands.resolve("proj li")
        self.assertIs(item, commands["project list"])
        self.assertEqual(arguments, "")

        with self.assertRaisesRegex(CommandNotFound, "Ambiguous command"):
            commands.resolve("proj l")

    def test_typed_parsing(self):
        def build(
            count: int,
            ratio: float,
            enabled: bool,
            color: Color,
            mode: Literal["fast", "safe"],
        ):
            pass

        item = Command(build)
        result = item.parse_args("3 1.5 yes red fast")
        self.assertEqual(
            result,
            {
                "count": 3,
                "ratio": 1.5,
                "enabled": True,
                "color": Color.red,
                "mode": "fast",
            },
        )

    def test_named_options_defaults_and_quoted_strings(self):
        def greet(name: str, loud: bool = False):
            return name

        item = Command(
            greet, arguments={"loud": Argument(flags=("-l", "--loud"))}
        )
        values = item.parse_args('--loud "Ada Lovelace"')
        self.assertEqual(values, {"loud": True, "name": "Ada Lovelace"})
        self.assertEqual(
            item.parse_args('"Grace Hopper" -l'),
            {"name": "Grace Hopper", "loud": True},
        )

    def test_arguments_are_positional_unless_flags_are_configured(self):
        def search(keyword: str, limit: int = 0, since: str | None = None):
            pass

        item = Command(search)
        self.assertEqual(
            item.parse_args("timeout 50 7d"),
            {"keyword": "timeout", "limit": 50, "since": "7d"},
        )
        with self.assertRaisesRegex(CommandValidationError, "Unknown option"):
            item.parse_args("timeout --limit 50")

    def test_named_arguments_support_short_long_equals_and_separator(self):
        def search(keyword: str, limit: int = 0, since: str | None = None):
            pass

        item = Command(
            search,
            arguments={
                "limit": Argument(flags=("-n", "--limit")),
                "since": Argument(flags=("-s", "--since")),
            },
        )
        self.assertEqual(
            item.parse_args("timeout -n 50 --since=7d"),
            {"keyword": "timeout", "limit": 50, "since": "7d"},
        )
        self.assertEqual(item.parse_args("-- -literal"), {"keyword": "-literal"})

    def test_required_named_argument_cannot_be_passed_positionally(self):
        def deploy(target: str, environment: str):
            pass

        item = Command(
            deploy,
            arguments={"environment": Argument(flags=("-e", "--environment"))},
        )
        with self.assertRaisesRegex(CommandValidationError, "Too many arguments"):
            item.parse_args("api production")
        self.assertEqual(
            item.parse_args("api -e production"),
            {"target": "api", "environment": "production"},
        )

    def test_command_behavior_metadata_is_preserved(self):
        item = Command(
            lambda name: None,
            record_history=False,
            confirmation="Delete {name}?",
        )
        self.assertFalse(item.record_history)
        self.assertEqual(item.confirmation, "Delete {name}?")

    def test_missing_bad_and_extra_arguments(self):
        item = Command(lambda count: None)
        with self.assertRaises(CommandValidationError):
            item.parse_args("")
        item = Command(
            lambda count: None,
            arguments={
                "count": Argument(
                    validator=lambda x: "too short" if len(x) < 3 else True
                )
            },
        )
        with self.assertRaisesRegex(CommandValidationError, "too short"):
            item.parse_args("x")
        with self.assertRaises(CommandValidationError):
            item.parse_args("good extra")

    async def test_sync_and_async_execution(self):
        self.assertEqual(
            await Command(lambda value: value).execute(value="sync"), "sync"
        )

        async def async_command(value):
            return value

        self.assertEqual(await Command(async_command).execute(value="async"), "async")

    async def test_static_dynamic_and_async_completions(self):
        async def regions(ctx):
            return ["us-east", "eu-west"]

        def deploy(environment: str, region: str):
            pass

        item = Command(
            deploy,
            arguments={
                "environment": Argument(
                    choices={"dev": "Development", "prod": "Production"}
                ),
                "region": Argument(completer=regions),
            },
        )
        first = await item.complete("", "d")
        self.assertEqual(first[0].value, "dev")
        self.assertEqual(first[0].help, "Development")
        second = await item.complete("dev ", "us")
        self.assertEqual([x.value for x in second], ["us-east"])

    async def test_completion_filters_values_rejected_by_validator(self):
        def choose(value: int):
            pass

        item = Command(
            choose,
            arguments={
                "value": Argument(
                    completer=lambda ctx: ["1", "bad", "12"],
                    validator=lambda value: value >= 10,
                )
            },
        )
        self.assertEqual([x.value for x in await item.complete("", "")], ["12"])

    async def test_named_option_completion_has_help(self):
        def deploy(environment: str = "dev"):
            pass

        item = Command(
            deploy,
            arguments={
                "environment": Argument(
                    flags=("-e", "--environment"), help="Target environment"
                )
            },
        )
        results = await item.complete("", "--e")
        self.assertEqual(
            (results[0].value, results[0].help), ("--environment", "Target environment")
        )
        short_results = await item.complete("", "-e")
        self.assertEqual(short_results[0].value, "-e")

    def test_argument_configuration_is_checked(self):
        with self.assertRaises(ValueError):
            Command(lambda value: None, arguments={"missing": Argument()})
        with self.assertRaisesRegex(ValueError, "Invalid flag"):
            Command(lambda value: None, arguments={"value": Argument(flags=("value",))})
        with self.assertRaisesRegex(ValueError, "Duplicate argument flag"):
            Command(
                lambda first, second: None,
                arguments={
                    "first": Argument(flags=("-x",)),
                    "second": Argument(flags=("-x",)),
                },
            )
