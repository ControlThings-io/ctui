"""Optional real-browser check (requires Playwright and Chromium or Firefox).

Run: uv run --with playwright tests/browser_smoke.py
Set CTUI_CHROMIUM_EXECUTABLE to use a system Chromium, or install Playwright's
browser with: uv run --with playwright python -m playwright install chromium
Set CTUI_BROWSER=firefox and install Firefox to run the same checks there.
This check is separate from the portable unittest suite.
"""

import asyncio
import io
import os

from playwright.async_api import async_playwright
from test_web import BrowserApp

from ctui.web import WebSession


async def main():
    session = WebSession(BrowserApp(), port=0, stdout=io.StringIO())
    await session.start()
    try:
        async with async_playwright() as playwright:
            options = {"headless": True}
            browser_name = os.environ.get("CTUI_BROWSER", "chromium")
            executable = os.environ.get("CTUI_CHROMIUM_EXECUTABLE")
            if executable and browser_name == "chromium":
                options["executable_path"] = executable
            browser_type = getattr(playwright, browser_name)
            browser = await browser_type.launch(**options)
            try:
                context = await browser.new_context()
                first = await context.new_page()
                errors = []
                first.on("pageerror", lambda error: errors.append(str(error)))
                await first.goto(session.url + "#token=" + session.access_token)
                await first.locator("#workspace").wait_for(state="visible")
                second = await context.new_page()
                await second.goto(session.url)
                await second.locator("#workspace").wait_for(state="visible")
                first_input = first.get_by_role("textbox", name="Command", exact=True)
                second_input = second.get_by_role("textbox", name="Command", exact=True)
                await second_input.fill("unfinished local draft")
                await first_input.fill("echo preserved")
                await first_input.press("Enter")
                await second.wait_for_function(
                    "() => document.querySelector('.output_field').textContent === 'preserved'"
                )
                assert await second_input.input_value() == "unfinished local draft"
                for text in ("help", "help echo"):
                    await first_input.fill(text)
                    await first_input.press("Enter")
                    dialog = first.get_by_role("dialog")
                    await dialog.wait_for(state="visible")
                    assert await dialog.locator("h2").text_content() == "Help"
                    if text == "help":
                        await dialog.get_by_role("button", name="OK", exact=True).press(
                            "ArrowDown"
                        )
                        assert await dialog.locator("pre").evaluate(
                            "el => el.scrollTop > 0"
                        )
                    assert (
                        await first.locator(".output_field").text_content()
                        == "preserved"
                    )
                    assert await second.locator("dialog").count() == 0
                    await dialog.get_by_role("button", name="OK", exact=True).click()
                    await dialog.wait_for(state="detached")
                    assert await first_input.evaluate(
                        "el => document.activeElement === el"
                    )
                await first.get_by_role("button", name="Increment", exact=True).click()
                await second.wait_for_function(
                    "() => document.querySelector('.statusbar').textContent === 'Clicks: 1'"
                )
                await first_input.press("F2")
                await second.wait_for_function(
                    "() => document.querySelector('.statusbar').textContent === 'Clicks: 2'"
                )
                await first_input.fill("ec")
                await first.locator("#suggestions").wait_for(state="visible")
                row = first.locator("#suggestions button").first
                assert await row.locator(".completion-label").text_content() == "echo"
                assert await row.locator(".completion-help").text_content()
                assert await row.evaluate(
                    "el => el.children[1].getBoundingClientRect().left > "
                    "el.children[0].getBoundingClientRect().left"
                )
                await first_input.press("Tab")
                assert await first_input.input_value() == "echo"
                await first.set_viewport_size({"width": 390, "height": 844})
                assert await first.locator(".output_field").evaluate(
                    "el => el.clientHeight > 400"
                )
                await first_input.fill("ec")
                await first.locator("#suggestions").wait_for(state="visible")
                assert await row.evaluate(
                    "el => el.children[1].getBoundingClientRect().top >= "
                    "el.children[0].getBoundingClientRect().bottom"
                )
                session.ctui.layout.set_output("x" * 300)
                await first.wait_for_function(
                    "() => document.querySelector('.output_field').textContent.includes('x'.repeat(300))"
                )
                await first_input.press("Escape")
                await first_input.press("Alt+ArrowRight")
                assert await first.locator(".output_field").evaluate(
                    "el => el.scrollLeft > 0"
                )
                assert await first_input.evaluate("el => document.activeElement === el")
                await first_input.press("Alt+ArrowLeft")
                assert await first.locator(".output_field").evaluate(
                    "el => el.scrollLeft === 0"
                )
                assert not errors, errors
                print(
                    f"{browser_name}: multi-tab output, local drafts, help popup, focus, buttons, completion and mobile layout passed"
                )
            finally:
                await browser.close()
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
