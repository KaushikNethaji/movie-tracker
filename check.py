import os
import sys
import time
import traceback

import requests
from playwright.sync_api import sync_playwright, Error

URL = os.environ.get("URL", "")

# ---- Telegram config (read from environment / GitHub Secrets) ----
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_telegram_message(message: str):
    """Send a message via Telegram bot. Fails silently (logs) if it can't send."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured, skipping notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, data=payload, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️ Telegram send failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"⚠️ Telegram send exception: {e}")


def check(page):
    print("Opening page...")

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    # Give JavaScript time to render
    page.wait_for_timeout(5000)

    print("Title:", page.title())

    # Save artifacts for debugging
    content = page.content()

    with open("page.html", "w", encoding="utf-8") as f:
        f.write(content)

    page.screenshot(path="page.png", full_page=True)

    print("Saved page.html and page.png")

    # Check rendered DOM instead of raw HTML
    nexus = page.locator("text=Nexus").count() > 0
    luxe = page.locator("text=LUXE").count() > 0

    if nexus:
        print("✅ Nexus Tickets available!")
        send_telegram_message(f"✅ <b>Nexus tickets available!</b>\n{URL}")

    if luxe:
        print("✅ Luxe Tickets available!")
        send_telegram_message(f"✅ <b>LUXE tickets available!</b>\n{URL}")

    if not nexus and not luxe:
        print("❓ Couldn't determine status.")


def main():
    print(f"\n========== {time.strftime('%Y-%m-%d %H:%M:%S')} ==========")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            ignore_https_errors=True,
            locale="en-IN",
        )

        page = context.new_page()

        page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9"
        })

        try:
            check(page)
        except Error as e:
            print(f"Playwright Error: {e}")
            send_telegram_message(f"❌ <b>Playwright Error</b>\n{e}")

            try:
                page.screenshot(
                    path=f"error_{int(time.time())}.png",
                    full_page=True,
                )
            except Exception:
                pass

            browser.close()
            sys.exit(1)
        except Exception:
            tb = traceback.format_exc()
            traceback.print_exc()
            send_telegram_message(f"❌ <b>Unexpected Error</b>\n<pre>{tb[-3000:]}</pre>")
            browser.close()
            sys.exit(1)

        browser.close()


if __name__ == "__main__":
    main()
