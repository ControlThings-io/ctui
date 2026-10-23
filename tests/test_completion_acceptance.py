"""Accepted completions advance arguments while retaining editable path/list values."""

import asyncio
import shlex
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import CompletionState
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout import Layout
from prompt_toolkit.output import DummyOutput

from ctui import Argument, CtuiApp, PathCompleter
from ctui.completion import completion_edit, move_completion_quote
from ctui.keybindings import get_key_bindings
from ctui.layout import CtuiLayout


class CompletionAcceptanceTests(unittest.IsolatedAsyncioTestCase):
    """Check shared edits and the actual Tab handler, including menu previews."""

    async def asyncSetUp(self):
        self.app = CtuiApp(register_defaults=False)
        self.app.layout = CtuiLayout(self.app)
        self.buffer = self.app.layout.input_field.buffer

        @self.app.commands.register(
            arguments={
                "environment": Argument(choices=("development", "production")),
                "server": Argument(choices=("web-1", "web-2")),
            }
        )
        def deploy(environment: str, server: str):
            return environment, server

        @self.app.commands.register(
            arguments={"path": Argument(completer=PathCompleter())}
        )
        def read(path: Path, count: int = 1):
            return path, count

        @self.app.commands.register(
            arguments={"path": Argument(flags=("--path",), completer=PathCompleter())}
        )
        def named(path: Path):
            return path

        @self.app.commands.register(
            arguments={"path": Argument(completer=PathCompleter(directories_only=True))}
        )
        def cd(path: Path):
            return str(path)

        @self.app.commands.register(
            arguments={"names": Argument(choices=("alpha", "beta"))}
        )
        def select(names: list[str]):
            return names

    async def candidates(self, text, cursor=None):
        document = Document(text, len(text) if cursor is None else cursor)
        items = [
            item
            async for item in self.app.layout.completer.get_completions_async(
                document, CompleteEvent(completion_requested=True)
            )
        ]
        return document, items

    async def edit(self, text, cursor=None, index=0):
        document, items = await self.candidates(text, cursor)
        return completion_edit(document, items[index])

    async def test_command_and_argument_acceptance_advance_and_reuse_space(self):
        edit = await self.edit("dep")
        self.assertEqual(edit, {"text": "deploy ", "cursor": 7, "quote": None})
        edit = await self.edit("deploy dev")
        self.assertEqual(edit["text"], "deploy development ")
        _, items = await self.candidates(edit["text"])
        self.assertEqual([item.text for item in items], ["web-1", "web-2"])
        for text, cursor in [
            ("deploy dev web-2", 10),
            ("deploy development web-2", 10),
        ]:
            with self.subTest(text=text):
                edit = await self.edit(text, cursor)
                self.assertEqual(edit["text"], "deploy development web-2")
                self.assertEqual(edit["cursor"], len("deploy development "))

    async def test_paths_continue_directories_and_finish_files(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "a folder's name"
            directory.mkdir()
            target = directory / "a file.json"
            target.touch()
            for command in ("read ", "cd "):
                with self.subTest(command=command):
                    edit = await self.edit(command + (Path(root) / "a").as_posix())
                    self.assertEqual(
                        shlex.split(edit["text"])[1], directory.as_posix() + "/"
                    )
                    self.assertEqual(edit["cursor"], len(edit["text"]) - 1)
                    self.assertEqual(edit["quote"], edit["cursor"])
            edit = await self.edit("read " + shlex.quote(directory.as_posix() + "/a f"))
            self.assertEqual(shlex.split(edit["text"])[1], target.as_posix())
            self.assertTrue(edit["text"].endswith("' "))
            self.assertEqual(edit["cursor"], len(edit["text"]))
            self.assertIsNone(edit["quote"])

    async def test_quotes_and_inline_options_preserve_suffix_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'a file\'s "name".json'
            target.touch()
            partial = (Path(root) / "a f").as_posix()
            for prefix in ("read ", "named --path="):
                for quote in ("'", '"'):
                    with self.subTest(prefix=prefix, quote=quote):
                        text = prefix + quote + partial + quote
                        edit = await self.edit(text, len(text) - 1)
                        self.assertEqual(edit["text"][len(prefix)], quote)
                        self.assertEqual(
                            shlex.split(edit["text"])[-1].split("=", 1)[-1],
                            target.as_posix(),
                        )
                        self.assertTrue(edit["text"].endswith(quote + " "))
            text = 'read "' + partial + '" 2'
            edit = await self.edit(text, len('read "' + partial))
            self.assertEqual(
                shlex.split(edit["text"]), ["read", target.as_posix(), "2"]
            )
            self.assertEqual(edit["cursor"], edit["text"].rindex("2"))

    async def test_lists_continue_and_hints_do_not_insert(self):
        edit = await self.edit("select al")
        self.assertEqual(edit["text"], "select alpha")
        edit = await self.edit("select alpha,be")
        self.assertEqual(edit["text"], "select alpha,beta")
        edit = await self.edit("read /a-new-unmatched-file")
        self.assertEqual(edit["text"], "read /a-new-unmatched-file")

    async def test_quoted_path_previews_reuse_closing_quote_and_preserve_suffix(self):
        with tempfile.TemporaryDirectory() as root:
            targets = [Path(root) / name for name in ("a folder", "a file's name")]
            targets[0].mkdir()
            targets[1].touch()
            for prefix in ("read ", "named --path="):
                for quote in ("'", '"'):
                    with self.subTest(prefix=prefix, quote=quote):
                        text = prefix + quote + (Path(root) / "a").as_posix()
                        document, items = await self.candidates(
                            text + quote + " 2", len(text)
                        )
                        self.buffer.document = document
                        self.buffer.complete_state = CompletionState(document, items)
                        for index in (0, 1, 0, 1):
                            self.buffer.go_to_completion(index)
                            self.assertEqual(self.buffer.text[len(prefix)], quote)
                            command = prefix.split()[0]
                            value = items[index].value
                            if command == "named":
                                value = "--path=" + value
                            self.assertEqual(
                                shlex.split(self.buffer.text),
                                [command, value, "2"],
                            )
                            self.assertEqual(
                                self.buffer.document.text_after_cursor, quote + " 2"
                            )
                        self.buffer.cancel_completion()
                        self.assertEqual(self.buffer.document, document)

    async def test_tab_accepts_highlighted_preview_and_fetches_first_candidate(self):
        document, items = await self.candidates("deploy ")
        self.buffer.document = document
        self.buffer.complete_state = CompletionState(document, items)
        self.buffer.go_to_completion(1)
        binding = next(
            b
            for b in get_key_bindings(self.app).bindings
            if str(b.keys[0]) == "Keys.ControlI"
        )
        tasks = []
        event = SimpleNamespace(
            app=SimpleNamespace(
                create_background_task=lambda coro: tasks.append(
                    asyncio.create_task(coro)
                )
            )
        )
        binding.handler(event)
        self.assertEqual(self.buffer.text, "deploy production ")
        self.buffer.document = Document("dep")
        binding.handler(event)
        await asyncio.gather(*tasks)
        self.assertEqual(self.buffer.text, "deploy ")

    async def test_accepting_directory_preview_refreshes_child_suggestions(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "plain"
            child = directory / "child"
            child.mkdir(parents=True)
            document, items = await self.candidates(
                "cd " + (Path(root) / "pl").as_posix()
            )
            self.buffer.document = document
            self.buffer.complete_state = CompletionState(document, items)
            self.buffer.go_to_completion(0)
            self.app.layout.accept_completion(items[0], document)
            self.assertIsNone(self.buffer.complete_state)
            async with asyncio.timeout(3):
                while self.buffer.complete_state is None:
                    await asyncio.sleep(0.01)
            self.assertEqual(
                [c.display_text for c in self.buffer.complete_state.completions],
                [child.as_posix() + "/"],
            )

    async def test_owned_quote_tracks_child_typing_and_space_accepts_directory(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "a folder"
            directory.mkdir()
            document, items = await self.candidates(
                "cd " + (Path(root) / "a").as_posix()
            )
            self.app.layout.accept_completion(items[0], document)
            self.assertTrue(self.app.layout.completion_quote_at_cursor())
            self.buffer.insert_text("new child/")
            self.assertTrue(self.app.layout.completion_quote_at_cursor())
            self.app.layout.finish_completion_quote(space=True)
            self.assertTrue(self.buffer.text.endswith("new child/' "))
            self.assertEqual(self.buffer.cursor_position, len(self.buffer.text))
            self.assertFalse(self.app.layout.completion_quote_at_cursor())
            self.buffer.document = Document(
                "cd 'manually entered/'", len("cd 'manually entered/")
            )
            self.assertFalse(self.app.layout.completion_quote_at_cursor())

    def test_quote_ownership_drops_when_quote_is_removed(self):
        self.assertEqual(move_completion_quote("'a/'", "'a/b/'", 3), 5)
        self.assertIsNone(move_completion_quote("'a/'", "'a/", 3))

    async def test_submitted_paths_do_not_expand_to_children_or_existing_prefixes(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "directory"
            (directory / "only child").mkdir(parents=True)
            (Path(root) / "report-old.json").touch()
            for text in (
                "cd " + shlex.quote(directory.as_posix() + "/"),
                "read " + shlex.quote((Path(root) / "report").as_posix()),
                "named --path=" + shlex.quote(directory.as_posix() + "/"),
            ):
                with self.subTest(text=text):
                    item, arguments = self.app.commands.resolve(text)
                    self.assertEqual(
                        shlex.split(await item.expand_unique_arguments(arguments)),
                        shlex.split(arguments),
                    )

    async def test_real_terminal_tab_menu_directory_space_and_enter(self):
        """Drive the actual input processor so default Tab bindings cannot mask ours."""

        async def wait_for(predicate):
            async with asyncio.timeout(3):
                while not predicate():
                    await asyncio.sleep(0.01)

        with tempfile.TemporaryDirectory() as root, create_pipe_input() as pipe:
            directory = Path(root) / "a folder"
            directory.mkdir()
            (directory / "only child").mkdir()
            terminal = Application(
                layout=Layout(
                    self.app.layout.root_container,
                    focused_element=self.app.layout.input_field,
                ),
                key_bindings=get_key_bindings(self.app),
                input=pipe,
                output=DummyOutput(),
                full_screen=True,
            )
            self.app.app = terminal
            running = asyncio.create_task(terminal.run_async())
            try:
                await wait_for(lambda: terminal.is_running)
                pipe.send_text("dep\t")
                try:
                    await wait_for(lambda: self.buffer.text == "deploy ")
                except TimeoutError:
                    self.fail(
                        f"Tab input: {self.buffer.text!r}; completer={self.buffer.completer!r}; state={self.buffer.complete_state!r}"
                    )
                await wait_for(lambda: self.buffer.complete_state is not None)
                pipe.send_text("\x1b[B\x1b[B\t")
                await wait_for(lambda: self.buffer.text == "deploy production ")
                # Start a fresh directory command, accept it, and submit from inside
                # its generated closing quote without descending into its children.
                self.buffer.document = Document("cd " + (Path(root) / "a").as_posix())
                pipe.send_text("\t")
                await wait_for(self.app.layout.completion_quote_at_cursor)
                pipe.send_text("\r")
                await wait_for(
                    lambda: self.app.layout.output_field.text == str(directory)
                )
                self.buffer.document = Document("cd " + (Path(root) / "a").as_posix())
                pipe.send_text("\t")
                await wait_for(self.app.layout.completion_quote_at_cursor)
                await wait_for(lambda: self.buffer.complete_state is not None)
                pipe.send_text("\x1b[B")
                await wait_for(lambda: self.buffer.complete_state.complete_index == 0)
                self.assertEqual(
                    shlex.split(self.buffer.text),
                    ["cd", (directory / "only child").as_posix() + "/"],
                )
                self.assertTrue(self.app.layout.completion_quote_at_cursor())
                pipe.send_text("\x1b[A")
                await wait_for(
                    lambda: self.buffer.complete_state.complete_index is None
                )
                self.assertEqual(
                    shlex.split(self.buffer.text), ["cd", directory.as_posix() + "/"]
                )
                pipe.send_text("\x1b[B\t")
                await wait_for(lambda: "only child" in self.buffer.text)
                await wait_for(self.app.layout.completion_quote_at_cursor)
                pipe.send_text(" ")
                await wait_for(lambda: self.buffer.text.endswith("' "))
                self.assertEqual(self.buffer.cursor_position, len(self.buffer.text))
                self.assertTrue(terminal.layout.has_focus(self.app.layout.input_field))
            finally:
                terminal.exit()
                await asyncio.wait_for(running, 3)
