"""Verify web mode from a standard installed wheel/sdist.

Use uv --isolated --no-project --with 'dist/ARTIFACT' tests/web_smoke.py.
This binds one ephemeral loopback port and tests assets plus command dispatch.
"""

import asyncio
import io

from aiohttp import ClientSession, CookieJar

from ctui import CtuiApp, command
from ctui.web import WebSession


class WebSmokeApp(CtuiApp):
    @command
    def echo(self, text: str) -> str:
        """Return text."""
        return text


async def main():
    app = WebSmokeApp()
    session = WebSession(app, port=0, stdout=io.StringIO())
    try:
        await session.start()
        async with ClientSession(cookie_jar=CookieJar(unsafe=True)) as client:
            for asset in ("", "app.js", "style.css"):
                async with client.get(session.url + asset) as response:
                    assert response.status == 200
                    assert await response.read()
            async with client.post(
                session.url + "login", json={"token": session.access_token}
            ) as response:
                assert response.status == 200
            async with client.ws_connect(session.url + "ws") as socket:
                assert (await socket.receive_json())["type"] == "state"
                await socket.send_json(
                    {"type": "command", "text": "echo installed", "id": 1}
                )
                async with asyncio.timeout(3):
                    while app.layout.output_field.text != "installed":
                        await socket.receive_json()
        print("Installed web assets and WebSocket command dispatch passed")
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
