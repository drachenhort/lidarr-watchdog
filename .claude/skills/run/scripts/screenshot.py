"""Screenshot a running lidarr-watchdog dashboard.

Usage: python scripts/screenshot.py <url> <output_png> [chromium|firefox]
"""

import sys

from playwright.sync_api import sync_playwright

url = sys.argv[1]
output_path = sys.argv[2]
engine = sys.argv[3] if len(sys.argv) > 3 else "chromium"

with sync_playwright() as p:
    browser = getattr(p, engine).launch()
    page = browser.new_page(viewport={"width": 1000, "height": 700})
    page.goto(url)
    page.wait_for_selector("text=lidarr-watchdog")
    page.screenshot(path=output_path, full_page=True)
    browser.close()
