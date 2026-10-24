"""Real browser acceptance checks for command, path and list completion.

Run: CTUI_BROWSER=chromium uv run --with playwright tests/browser_completion.py
Install the selected Playwright browser first. No external service is used.
"""

import asyncio
import io
import os
import shlex
import tempfile
from pathlib import Path
from typing import Literal

from playwright.async_api import async_playwright, expect

from ctui import Argument, CtuiApp, PathCompleter
from ctui.web import WebSession


async def check_completion_layout(page, field, menu):
    """Check natural label widths, optional help and viewport-constrained wrapping.

    Exercise real string choices and PathCompleter results at normal/enlarged
    text sizes. Short labels should fit on one line; genuinely long paths may
    wrap, with the popup remaining inside the viewport. Help stays aligned on
    desktop and stacks below labels on narrow screens.
    """

    async def label_lines():
        return await menu.locator(".completion-label").evaluate_all(
            """labels => labels.map(label => {
                const range = document.createRange();
                range.selectNodeContents(label);
                return {text: label.textContent, lines: range.getClientRects().length};
            })"""
        )

    with tempfile.TemporaryDirectory() as root:
        target = Path(root) / ("a" * 192 + ".json")
        target.touch()
        for width, font_size in ((910, 24), (673, 24), (1280, 15), (390, 15)):
            await page.set_viewport_size({"width": width, "height": 1080})
            await page.evaluate(
                "size => { document.documentElement.style.fontSize = size + 'px'; }",
                font_size,
            )
            await field.fill("read tag ")
            await expect(menu).to_contain_text("EmergencyTimer")
            labels = await label_lines()
            assert all(label["lines"] == 1 for label in labels), (width, labels)

            await field.fill("read ")
            await expect(menu).to_contain_text("pyproject.toml")
            paths = [
                label
                for label in await label_lines()
                if label["text"] in ("README.md", "pyproject.toml", "src/")
            ]
            assert len(paths) == 3, paths
            assert all(label["lines"] == 1 for label in paths), (width, paths)

            await field.fill("explain ")
            await expect(menu).to_contain_text("Help for a selectable value")
            row = menu.locator("button").filter(has_text="helped").first
            aligned = await row.evaluate("""row => {
                    const label = row.children[0].getBoundingClientRect();
                    const help = row.children[1].getBoundingClientRect();
                    return {columns: help.left >= label.right - 1,
                            stacked: help.top >= label.bottom - 1};
                }""")
            assert aligned["columns" if width > 600 else "stacked"], (width, aligned)

            await field.fill("read " + Path(root).as_posix() + "/")
            await expect(menu).to_contain_text(target.name)
            bounds = await menu.evaluate(
                "element => ({left: element.getBoundingClientRect().left, "
                "right: element.getBoundingClientRect().right})"
            )
            assert bounds["left"] >= 0 and bounds["right"] <= width, (width, bounds)
            assert (await label_lines())[0]["lines"] > 1


async def main():
    app = CtuiApp(register_defaults=False)

    @app.commands.register(
        arguments={
            "environment": Argument(choices=("development", "production")),
            "server": Argument(choices=("web-1", "web-2")),
        }
    )
    def deploy(environment: str, server: str):
        return f"{environment}: {server}"

    @app.commands.register(arguments={"path": Argument(completer=PathCompleter())})
    def read(path: Path, count: Literal[1, 2] = 1):
        return str(path)

    @app.commands.register(
        arguments={"path": Argument(completer=PathCompleter(directories_only=True))}
    )
    def cd(path: Path):
        return str(path)

    @app.commands.register(arguments={"names": Argument(choices=("alpha", "beta"))})
    def select(names: list[str]):
        return ",".join(names)

    @app.commands.register(
        arguments={
            "tag": Argument(
                help="Tag to read",
                choices=(
                    "BTimer",
                    "BatchTimer",
                    "Chem1Pump",
                    "ETimer",
                    "EmergencyFlush",
                    "EmergencyTimer",
                ),
            )
        }
    )
    def read_tag(tag: str):
        return tag

    @app.commands.register(
        arguments={
            "value": Argument(
                help="Value to explain",
                choices={"plain": "", "helped": "Help for a selectable value"},
            )
        }
    )
    def explain(value: str):
        return value

    @app.commands.register(name="project history clear")
    def clear_history():
        return "cleared"

    @app.commands.register(name="project history export")
    def export_history():
        return "exported"

    session = WebSession(app, port=0, stdout=io.StringIO())
    await session.start()
    original = app.layout.completer.get_completions_async

    async def delayed_commands(document, event):
        if document.text_before_cursor in ("", "   ", "project ", "project history "):
            await asyncio.sleep(0.15)
        async for item in original(document, event):
            yield item

    app.layout.completer.get_completions_async = delayed_commands
    browser_name = os.environ.get("CTUI_BROWSER", "chromium")
    try:
        async with async_playwright() as playwright:
            options = {"headless": True}
            if browser_name == "chromium" and os.environ.get(
                "CTUI_CHROMIUM_EXECUTABLE"
            ):
                options["executable_path"] = os.environ["CTUI_CHROMIUM_EXECUTABLE"]
            browser = await getattr(playwright, browser_name).launch(**options)
            try:
                page = await browser.new_page()
                page.set_default_timeout(10000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto(session.url + "#token=" + session.access_token)
                field = page.get_by_role("textbox", name="Command", exact=True)
                menu = page.locator("#suggestions")
                await field.wait_for(state="visible")
                # Repeated Tab while loading must reveal, not insert, an unseen command.
                await field.press("Tab")
                await field.press("Tab")
                await expect(menu).to_be_visible()
                await expect(field).to_have_value("")
                await expect(menu.locator(".selected")).to_contain_text("deploy")
                await field.press("Tab")
                await expect(field).to_have_value("deploy ")

                for prefix in ("   ", "project ", "project history "):
                    await field.fill(prefix)
                    await field.press("Escape")
                    await expect(menu).to_be_hidden()
                    await field.press("Tab")
                    await field.press("Tab")
                    await expect(menu).to_be_visible()
                    await expect(field).to_have_value(prefix)
                    await field.press("Escape")
                    await expect(menu).to_be_hidden()
                    await expect(field).to_have_value(prefix)
                    await field.press("Tab")
                    await expect(menu).to_be_visible()
                    await expect(field).to_have_value(prefix)
                    await field.press("Tab")
                    await expect(field).not_to_have_value(prefix)

                # Escape must invalidate a response that has not arrived yet.
                await field.fill("project history ")
                await field.press("Tab")
                await field.press("Escape")
                await page.wait_for_timeout(350)
                await expect(menu).to_be_hidden()
                await expect(field).to_have_value("project history ")
                await field.press("Tab")
                await expect(menu).to_be_visible()
                await field.press("ArrowDown")
                await field.press("Tab")
                await expect(field).to_have_value("project history export ")

                await field.fill("dep")
                # Tab before the delayed response must still accept the first result.
                await field.press("Tab")
                await expect(field).to_have_value("deploy ")
                await expect(menu).to_contain_text("production")
                await field.press("ArrowDown")
                await field.press("Tab")
                await expect(field).to_have_value("deploy production ")
                await expect(menu).to_contain_text("web-1")
                await menu.locator(".completion-label", has_text="web-2").click()
                await expect(field).to_have_value("deploy production web-2 ")

                with tempfile.TemporaryDirectory() as root:
                    directory = Path(root) / 'a folder\'s "name" 😀'
                    child = directory / "nested dir"
                    child.mkdir(parents=True)
                    target = directory / 'z file\'s "name".json'
                    target.touch()
                    await field.fill("cd " + (Path(root) / "a").as_posix())
                    await field.press("Tab")
                    await expect(field).to_have_value(
                        "cd " + shlex.quote(directory.as_posix() + "/")
                    )
                    assert await field.evaluate(
                        "(e)=>e.selectionStart===e.value.length-1"
                    )
                    await field.press_sequentially("ne")
                    await expect(menu).to_contain_text("nested dir")
                    await field.press("Tab")
                    await expect(field).to_have_value(
                        "cd " + shlex.quote(child.as_posix() + "/")
                    )
                    value = await field.input_value()
                    assert shlex.split(value)[1] == child.as_posix() + "/"
                    assert await field.evaluate(
                        "(e)=>e.selectionStart===e.value.length-1"
                    )
                    await field.press("Space")
                    await expect(field).to_have_value(
                        "cd " + shlex.quote(child.as_posix() + "/") + " "
                    )
                    assert (await field.input_value()).endswith("' ")
                    assert await field.evaluate(
                        "(e)=>e.selectionStart===e.value.length"
                    )

                    # Submitting a directory must not dispatch-expand its sole
                    # directory-only candidate into the nested child.
                    await field.fill("cd " + shlex.quote(directory.as_posix() + "/"))
                    await field.press("Enter")
                    await expect(page.locator(".output_field")).to_have_text(
                        str(directory)
                    )

                    partial = directory.as_posix() + "/z"
                    await field.fill("read " + shlex.quote(partial))
                    await field.press("Tab")
                    await expect(field).to_have_value(
                        "read " + shlex.quote(target.as_posix()) + " "
                    )
                    value = await field.input_value()
                    assert shlex.split(value) == ["read", target.as_posix()]
                    assert value.endswith("' ")
                    await expect(menu).to_contain_text("2")
                    # Completion in the middle consumes the old token's closing
                    # quote and suffix, retaining the subsequent count argument.
                    text = "read " + shlex.quote(partial) + " 2"
                    await field.fill(text)
                    await field.evaluate(
                        '(e)=>{const p=e.value.length-3;e.setSelectionRange(p,p);e.dispatchEvent(new Event("input",{bubbles:true}));}'
                    )
                    await expect(menu).to_contain_text("z file")
                    await field.press("Tab")
                    await expect(field).to_have_value(
                        "read " + shlex.quote(target.as_posix()) + " 2"
                    )
                    assert shlex.split(await field.input_value()) == [
                        "read",
                        target.as_posix(),
                        "2",
                    ]

                await field.fill("select al")
                await field.press("Tab")
                await expect(field).to_have_value("select alpha")
                await field.press_sequentially(",be")
                await expect(menu).to_contain_text("beta")
                await field.press("Tab")
                await expect(field).to_have_value("select alpha,beta")
                await check_completion_layout(page, field, menu)
                assert not errors, errors
                print(
                    f"{browser_name}: menu-first Tab, loading/cancellation, completion acceptance, path quotes, Unicode, lists, clicking, middle-of-command editing and popup sizing passed"
                )
            finally:
                await browser.close()
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
