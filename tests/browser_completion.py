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

    session = WebSession(app, port=0, stdout=io.StringIO())
    await session.start()
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
                assert not errors, errors
                print(
                    f"{browser_name}: completion acceptance, path quotes, Unicode, lists, clicking and middle-of-command editing passed"
                )
            finally:
                await browser.close()
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
