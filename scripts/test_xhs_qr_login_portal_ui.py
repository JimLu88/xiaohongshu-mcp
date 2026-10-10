#!/usr/bin/env python3
"""Headless local-page smoke used with webapp-testing's server helper."""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


url = os.environ.get("PANSE_QR_PORTAL_URL", "http://127.0.0.1:18765/")
output = Path(os.environ.get("PANSE_QR_PORTAL_SCREENSHOT", "qr-portal-smoke.png"))
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 900, "height": 900})
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.get_by_role("heading", name="小红书专用登录二维码").wait_for()
    page.locator("#status").wait_for()
    assert page.get_by_role("button", name="刷新过期二维码").is_visible()
    assert page.get_by_role("button", name="切换账号并获取二维码").is_visible()
    assert page.get_by_role("button", name="我已扫码，检查状态").is_visible()
    page.screenshot(path=str(output), full_page=True)
    browser.close()
print(f"portal_ui_smoke=passed screenshot={output.resolve()}")
