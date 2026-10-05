"""Exercise every runnable tutorial through its real --web entry point.

Run: CTUI_BROWSER=firefox uv run --with playwright tests/browser_tutorials.py
For Chromium, set CTUI_BROWSER=chromium and optionally CTUI_CHROMIUM_EXECUTABLE.
Install a bundled browser with Playwright's install command first. Application
storage is redirected into a temporary test directory. Tutorial processes exit
through the UI and are forcibly cleaned up on any failure.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "01_first_command.py": [("hello Ada", "Hello, Ada!")],
    "02_class_application.py": [
        ("add 2 3", "2 + 3 = 5"),
        ("multiply 4 5", "4 * 5 = 20"),
    ],
    "03_types_and_options.py": [
        ("greet Justin", "Hello, Justin."),
        ('greet "Justin Searle" excited true', "HELLO, JUSTIN SEARLE!"),
    ],
    "04_named_arguments.py": [
        (
            "deploy api -e prod -r 3 --verbose",
            "Deploying 3 api replica(s) to production with verbose logging.",
        )
    ],
    "05_hex_bytes.py": [
        ("inspect deadbeef", "de ad be ef (4 bytes)"),
        ('inspect "0xbe 0b10101100 0xef 0d10 0o377"', "be ac ef 0a ff (5 bytes)"),
    ],
    "06_fuzzy_patterns.py": [
        ("hex expand 56ffff07f[0-2]01", "56ffff07f201"),
        ("text expand {admin,user}-[1-2]", "user-2"),
    ],
    "07_integer_ranges.py": [
        ("inspect 0-5,9", "7 unique values"),
        ("expand 0-5,9", "0, 1, 2, 3, 4, 5, 9"),
    ],
    "08_automatic_cli.py": [
        ("greet Ada true", "Hello, Ada!"),
        ("add 12 30", "42.0"),
        ("count-words 'hello world'", "2 words"),
    ],
    "09_completion_and_validation.py": [
        ("dep dev dev-1", "Deploying to dev-1 in development")
    ],
    "10_async_and_events.py": [],
    "11_statusbar_progress.py": [],
    "12_keyboard_shortcuts.py": [],
    "13_custom_layout.py": [("system status", "Controller: online")],
    "14_lifecycle_and_storage.py": [
        ("configs show local", "127.0.0.1"),
        ("profile save lab 10.0.0.20 502", "Saved profile 'lab'."),
        ("traffic record sent 010300000001", "Recorded 6 bytes."),
    ],
    "15_web_frontend.py": [("echo hello", "hello")],
    "filesystem.py": [
        ("ls examples --long", "01_first_command.py"),
        ("cd examples", "Changed to"),
        ("ls", "15_web_frontend.py"),
    ],
}


async def check_tutorial(browser, name, commands, directory):
    token = "temporary-tutorial-browser-token-123456789"
    environment = dict(
        os.environ, CTUI_TUTORIAL_TOKEN=token, XDG_DATA_HOME=str(directory)
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(ROOT / "examples" / name),
        "--web",
        "--web-port",
        "0",
        "--web-token-env",
        "CTUI_TUTORIAL_TOKEN",
        cwd=ROOT,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    context = await browser.new_context()
    try:
        line = (await asyncio.wait_for(process.stdout.readline(), 10)).decode().strip()
        if " web session: " not in line:
            errors = (await process.stderr.read()).decode()
            raise AssertionError(f"{name} failed to start: {errors}")
        address = line.split(" web session: ", 1)[1]
        page = await context.new_page()
        page.set_default_timeout(15000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(address)
        await page.locator("#workspace").wait_for(state="visible")
        command_input = page.get_by_role("textbox", name="Command", exact=True)
        output = page.locator(".output_field")

        async def submit(text, expected=None):
            await command_input.fill(text)
            await command_input.press("Enter")
            if expected is not None:
                await page.wait_for_function(
                    "value => document.querySelector('.output_field').textContent.includes(value)",
                    arg=expected,
                )

        for text, expected in commands:
            await submit(text, expected)
        if name == "09_completion_and_validation.py":
            await command_input.fill("deploy development dev-")
            await page.locator("#suggestions").wait_for(state="visible")
            assert "dev-1" in await page.locator("#suggestions").text_content()
            previous = await output.text_content()
            await submit("deploy development invalid")
            dialog = page.get_by_role("dialog")
            await dialog.wait_for(state="visible")
            assert "Server names must end" in await dialog.text_content()
            await dialog.get_by_role("button", name="OK", exact=True).click()
            assert await output.text_content() == previous
        elif name in ("10_async_and_events.py", "11_statusbar_progress.py"):
            await submit("download report.csv")
            if name.startswith("10"):
                await page.wait_for_function(
                    "() => document.querySelector('.output_field').textContent.includes('Started report.csv')"
                )
            else:
                await page.wait_for_function(
                    "() => document.querySelector('.statusbar').textContent.includes('report.csv:')"
                )
            await submit("download photo.jpg")
            await page.wait_for_function(
                "() => document.querySelector('.output_field').textContent.includes('Completed report.csv') && document.querySelector('.output_field').textContent.includes('Completed photo.jpg')"
            )
            if name.startswith("11"):
                assert await page.locator(".statusbar").text_content() == "Ready"
        elif name == "12_keyboard_shortcuts.py":
            await command_input.press("F2")
            await page.wait_for_function(
                "() => document.querySelector('.statusbar').textContent === 'F2 presses: 1'"
            )
        elif name == "15_web_frontend.py":
            await submit("progress 50")
            await page.wait_for_function(
                "() => document.querySelector('progress').value === 50"
            )
            await page.get_by_role("button", name="Increment", exact=True).click()
            await page.wait_for_function(
                "() => document.querySelector('.statusbar').textContent === 'Button clicks: 1'"
            )
        elif name == "filesystem.py":
            await command_input.fill("ls 01")
            await page.locator("#suggestions").wait_for(state="visible")
            assert (
                "01_first_command.py"
                in await page.locator("#suggestions").text_content()
            )

        previous = await output.text_content()
        await submit("help")
        dialog = page.get_by_role("dialog")
        await dialog.wait_for(state="visible")
        assert await dialog.locator("h2").text_content() == "Help"
        assert await output.text_content() == previous
        await dialog.get_by_role("button", name="OK", exact=True).click()
        await submit("exit")
        await dialog.wait_for(state="visible")
        await dialog.get_by_role("button", name="Yes", exact=True).click()
        await asyncio.wait_for(process.wait(), 5)
        assert process.returncode == 0, (await process.stderr.read()).decode()
        assert not errors, errors
        print(f"PASS {name}", flush=True)
    finally:
        await context.close()
        if process.returncode is None:
            process.kill()
            await process.wait()


async def main():
    browser_name = os.environ.get("CTUI_BROWSER", "firefox")
    async with async_playwright() as playwright:
        options = {"headless": True}
        if browser_name == "chromium" and os.environ.get("CTUI_CHROMIUM_EXECUTABLE"):
            options["executable_path"] = os.environ["CTUI_CHROMIUM_EXECUTABLE"]
        browser = await getattr(playwright, browser_name).launch(**options)
        try:
            with tempfile.TemporaryDirectory(prefix="ctui-tutorials-") as directory:
                selected = sys.argv[1:] or CASES
                for name in selected:
                    await check_tutorial(
                        browser, name, CASES[name], Path(directory) / name
                    )
            print(
                f"{browser_name}: {len(selected)} tutorial applications passed",
                flush=True,
            )
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
