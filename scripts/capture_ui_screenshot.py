"""Capture a screenshot of the running Streamlit UI."""

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/opt/cursor/artifacts/screenshots/stock-trader-ui.png")
OUT.parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto("http://127.0.0.1:8501", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    page.screenshot(path=str(OUT), full_page=True)
    browser.close()

print(f"Saved {OUT}")
