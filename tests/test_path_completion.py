"""Filesystem providers and completion insertion must preserve usable paths."""

import os
import shlex
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from ctui import Argument, CtuiApp, PathCompleter
from ctui.commands import Commands
from ctui.completion import CommandCompleter


class PathCompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_filters_prefixes_and_missing_directories(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "nested dir").mkdir()
            (root / "snapshot.ctui-project").touch()
            (root / "other.json").touch()

            async def matches(provider, word):
                return await provider(SimpleNamespace(word=word))

            prefix = str(root) + os.sep
            all_paths = await matches(PathCompleter(), prefix)
            self.assertIn(prefix + "nested dir" + os.sep, all_paths)
            self.assertIn(prefix + "snapshot.ctui-project", all_paths)
            self.assertEqual(
                await matches(PathCompleter(directories_only=True), prefix),
                [prefix + "nested dir" + os.sep],
            )
            filtered = await matches(
                PathCompleter(file_filter=lambda p: p.suffix == ".json"), prefix
            )
            self.assertEqual(
                filtered, [prefix + "nested dir" + os.sep, prefix + "other.json"]
            )
            self.assertEqual(await matches(PathCompleter(), prefix + "absent/"), [])
            previous = Path.cwd()
            try:
                os.chdir(root)
                self.assertIn("other.json", await matches(PathCompleter(), ""))
            finally:
                os.chdir(previous)
            with patch.dict(os.environ, {"HOME": str(root), "USERPROFILE": str(root)}):
                self.assertIn(
                    os.path.join("~", "other.json"),
                    await matches(PathCompleter(), "~/"),
                )
            with patch(
                "ctui.path_completion.Path.iterdir", side_effect=PermissionError
            ):
                self.assertEqual(await matches(PathCompleter(), prefix), [])

    async def test_selected_paths_round_trip_through_parser(self):
        commands = Commands()

        @commands.register(arguments={"path": Argument(completer=PathCompleter())})
        def read(path: Path):
            return path

        @commands.register(
            arguments={"path": Argument(flags=("--path",), completer=PathCompleter())}
        )
        def named(path: Path):
            return path

        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "a file's name.json"
            destination.touch()
            partial = (Path(root) / "a f").as_posix()
            for prefix, token in (
                ("read ", shlex.quote(partial)),
                ("read ", '"' + partial),
                ("read ", partial.replace(" ", "\\ ")),
                ("named --path=", '"' + partial),
                ("named --path ", shlex.quote(partial)),
            ):
                text = prefix + token
                with self.subTest(text=text):
                    completions = [
                        c
                        async for c in CommandCompleter(commands).get_completions_async(
                            Document(text), CompleteEvent()
                        )
                    ]
                    chosen = next(
                        c for c in completions if Path(c.display_text) == destination
                    )
                    buffer = Buffer(document=Document(text))
                    buffer.apply_completion(chosen)
                    item, arguments = commands.resolve(buffer.text)
                    values = item.parse_args(arguments)
                    self.assertEqual(values["path"], destination)

    async def test_builtin_file_arguments_use_shared_provider(self):
        with tempfile.TemporaryDirectory() as root:
            app = CtuiApp(app_id="io.example.paths", data_dir=Path(root))
            for name in (
                "project import",
                "project export",
                "config import",
                "config export",
                "history export",
            ):
                item, _ = app.commands.resolve(name)
                self.assertIsInstance(item.arguments["path"].completer, PathCompleter)
