import unittest
from enum import Enum
from pathlib import Path
from typing import Literal

from ctui.commands import Argument, Command, CommandValidationError, Commands


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

        values = Command(greet).parse_args('--loud "Ada Lovelace"')
        self.assertEqual(values, {"loud": True, "name": "Ada Lovelace"})

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
            deploy, arguments={"environment": Argument(help="Target environment")}
        )
        results = await item.complete("", "--e")
        self.assertEqual(
            (results[0].value, results[0].help), ("--environment", "Target environment")
        )

    def test_argument_configuration_is_checked(self):
        with self.assertRaises(ValueError):
            Command(lambda value: None, arguments={"missing": Argument()})
