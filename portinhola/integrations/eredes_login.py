"""Assisted E-Redes login: an in-process Playwright page streamed to the
user's browser over WebSocket so they can solve the CAPTCHA themselves.

Protocol (JSON text messages):
  server → client: {"type":"frame","data":<b64 jpeg>,"w":int,"h":int}
                   {"type":"success"} | {"type":"error","message":str}
  client → server: {"type":"click","x":int,"y":int}
                   {"type":"type","text":str}
                   {"type":"key","key":str}
                   {"type":"scroll","dy":int}
"""

import asyncio
import base64
import contextlib
import json
from collections.abc import Awaitable, Callable

from fastapi import WebSocket

LOGIN_URL = "https://balcaodigital.e-redes.pt/login"
VIEWPORT_W = 1024
VIEWPORT_H = 768
FRAME_INTERVAL = 0.7


async def is_logged_in(page) -> bool:
    """Logged-in detection: navigated away from any login-ish URL."""
    url = page.url.lower()
    return url.startswith("http") and "login" not in url and "signin" not in url


async def run_login_session(
    ws: WebSocket,
    on_success: Callable[[list[dict]], Awaitable[None]],
) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": VIEWPORT_W, "height": VIEWPORT_H}
        )
        page = await context.new_page()
        try:
            await page.goto(LOGIN_URL)

            done = asyncio.Event()

            async def frames() -> None:
                previous: bytes | None = None
                while not done.is_set():
                    with contextlib.suppress(Exception):
                        shot = await page.screenshot(type="jpeg", quality=55)
                        if shot != previous:
                            previous = shot
                            await ws.send_text(
                                json.dumps(
                                    {
                                        "type": "frame",
                                        "data": base64.b64encode(shot).decode(),
                                        "w": VIEWPORT_W,
                                        "h": VIEWPORT_H,
                                    }
                                )
                            )
                    await asyncio.sleep(FRAME_INTERVAL)

            async def check_success() -> bool:
                if await is_logged_in(page):
                    cookies = await context.cookies()
                    await on_success([dict(c) for c in cookies])
                    await ws.send_text(json.dumps({"type": "success"}))
                    done.set()
                    return True
                return False

            frame_task = asyncio.create_task(frames())
            try:
                while not done.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
                    except TimeoutError:
                        await check_success()
                        continue
                    event = json.loads(raw)
                    if event["type"] == "click":
                        await page.mouse.click(event["x"], event["y"])
                    elif event["type"] == "type":
                        await page.keyboard.type(event["text"])
                    elif event["type"] == "key":
                        await page.keyboard.press(event["key"])
                    elif event["type"] == "scroll":
                        await page.mouse.wheel(0, event["dy"])
                    await asyncio.sleep(0.3)
                    await check_success()
            finally:
                done.set()
                frame_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await frame_task
        finally:
            await context.close()
            await browser.close()
