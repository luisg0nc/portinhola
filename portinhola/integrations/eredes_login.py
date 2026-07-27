"""Assisted E-Redes login: an in-process Playwright page streamed to the
user's browser over WebSocket so they can solve the CAPTCHA themselves.

Frames come from Chromium's native screencast (CDP Page.startScreencast):
the browser pushes pre-encoded JPEG frames whenever content changes, which
is far faster and smoother than polling page.screenshot().

Protocol (JSON text messages):
  server → client: {"type":"frame","data":<b64 jpeg>,"w":int,"h":int}
                   {"type":"success"} | {"type":"error","message":str}
  client → server: {"type":"click","x":int,"y":int}
                   {"type":"type","text":str}
                   {"type":"key","key":str}
                   {"type":"scroll","dy":int}
"""

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable

from fastapi import WebSocket

LOGIN_URL = "https://balcaodigital.e-redes.pt/login"
HISTORY_URL = "https://balcaodigital.e-redes.pt/consumptions/history"
VALIDATION_MARKER = "Validação de Segurança"
VIEWPORT_W = 1280
VIEWPORT_H = 800
JPEG_QUALITY = 60
SCREENCAST_MAX_W = 1920
SCREENCAST_MAX_H = 1200


async def is_logged_in(page) -> bool:
    """Phase 1: navigated away from any login-ish URL."""
    url = page.url.lower()
    return url.startswith("http") and "login" not in url and "signin" not in url


async def is_fully_validated(page) -> bool:
    """Phase 2: on the consumption-history page past the security gate."""
    if "consumptions/history" not in page.url.lower():
        return False
    body = await page.inner_text("body")
    return VALIDATION_MARKER not in body and len(body) > 200


async def run_login_session(
    ws: WebSocket,
    on_success: Callable[[list[dict]], Awaitable[None]],
) -> None:
    from playwright.async_api import async_playwright

    from portinhola.config import Config

    profile_dir = Config().data_dir / "eredes-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        # Persistent profile: the E-Redes session is bound to the browser
        # fingerprint + localStorage, so the sync job must reuse the exact
        # same profile the user logged in with. Full-chromium new-headless +
        # fingerprint cleanup keeps reCAPTCHA solvable.
        context = await pw.chromium.launch_persistent_context(
            str(profile_dir),
            headless=True,
            channel="chromium",
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": VIEWPORT_W, "height": VIEWPORT_H},
            device_scale_factor=2,
            locale="pt-PT",
            timezone_id="Europe/Lisbon",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            await page.goto(LOGIN_URL)

            done = asyncio.Event()
            frame_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=4)

            cdp = await context.new_cdp_session(page)

            def on_screencast_frame(params: dict) -> None:
                with contextlib.suppress(asyncio.QueueFull):
                    frame_queue.put_nowait(params["data"])
                asyncio.get_running_loop().create_task(
                    cdp.send(
                        "Page.screencastFrameAck", {"sessionId": params["sessionId"]}
                    )
                )

            cdp.on("Page.screencastFrame", on_screencast_frame)
            await cdp.send(
                "Page.startScreencast",
                {
                    "format": "jpeg",
                    "quality": JPEG_QUALITY,
                    "maxWidth": SCREENCAST_MAX_W,
                    "maxHeight": SCREENCAST_MAX_H,
                    "everyNthFrame": 1,
                },
            )

            phase = {"at_history": False}

            async def check_success() -> bool:
                # Two human checkpoints: the login CAPTCHA, then the
                # "Validação de Segurança" gate on the history page. Only a
                # session past BOTH is worth saving for the sync job.
                if not await is_logged_in(page):
                    return False
                if not phase["at_history"]:
                    phase["at_history"] = True
                    with contextlib.suppress(Exception):
                        await page.goto(HISTORY_URL)
                    return False
                if await is_fully_validated(page):
                    cookies = await context.cookies()
                    await on_success([dict(c) for c in cookies])
                    await ws.send_text(json.dumps({"type": "success"}))
                    done.set()
                    return True
                return False

            async def sender() -> None:
                while not done.is_set():
                    with contextlib.suppress(TimeoutError):
                        data = await asyncio.wait_for(frame_queue.get(), timeout=0.5)
                        await ws.send_text(
                            json.dumps(
                                {
                                    "type": "frame",
                                    "data": data,
                                    "w": VIEWPORT_W,
                                    "h": VIEWPORT_H,
                                }
                            )
                        )

            async def success_watcher() -> None:
                while not done.is_set():
                    await asyncio.sleep(1.0)
                    with contextlib.suppress(Exception):
                        await check_success()

            sender_task = asyncio.create_task(sender())
            watcher_task = asyncio.create_task(success_watcher())
            try:
                while not done.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.receive_text(), timeout=0.5)
                    except TimeoutError:
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
            finally:
                done.set()
                with contextlib.suppress(Exception):
                    await cdp.send("Page.stopScreencast")
                for task in (sender_task, watcher_task):
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
        finally:
            await context.close()
