from playwright.sync_api import sync_playwright, Error
from playwright_stealth import stealth_sync
import time
import traceback
import requests
import shutil
import os


URL = os.environ.get("URL", "")

# ---- Telegram config (read from environment / GitHub Secrets) ----
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ---- Chrome profile config ----
# Point this at a COPY of your real Chrome profile, not the live one Chrome
# itself is using — Chrome locks the profile folder while it's running.
#
# To make a copy (close Chrome first), e.g. on Windows:
#   xcopy "%LOCALAPPDATA%\Google\Chrome\User Data\Default" "%USERPROFILE%\bms_profile" /E /I
# On macOS:
#   cp -R "~/Library/Application Support/Google/Chrome/Default" ~/bms_profile
# On Linux:
#   cp -R ~/.config/google-chrome/Default ~/bms_profile
#
# If you'd rather not copy your real profile, just leave PROFILE_DIR pointing
# at a fresh empty folder — it'll still pass as a normal (if new) Chrome user.
PROFILE_DIR = os.path.expanduser("~/bms_profile")


def send_telegram_message(message: str):
    """Send a message via Telegram bot. Fails silently (logs) if it can't send."""
    if not TELEGRAM_BOT_TOKEN or "YOUR_BOT_TOKEN_HERE" in TELEGRAM_BOT_TOKEN:
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

    # Bail out early if Cloudflare is still showing the block page
    if "blocked" in page.title().lower() or page.locator("text=Sorry, you have been blocked").count() > 0:
        print("🚫 Still blocked by Cloudflare.")
        return

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
        print("❌ No matching theatres found.")
        send_telegram_message(
            f"❌ <b>No tickets found</b>\n"
            f"Checked at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Nexus: ❌\n"
            f"LUXE: ❌"
    )


with sync_playwright() as p:
    if not os.path.isdir(PROFILE_DIR):
        os.makedirs(PROFILE_DIR, exist_ok=True)
        print(f"ℹ️ Created fresh profile dir at {PROFILE_DIR}")

    context = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        channel="chrome",              # use real installed Chrome, not bundled Chromium
        headless=True,
        slow_mo=100,
        ignore_https_errors=True,
        locale="en-IN",
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        args=["--disable-blink-features=AutomationControlled"],
    )

    page = context.pages[0] if context.pages else context.new_page()
    stealth_sync(page)  # patches navigator.webdriver and other automation tells

    page.set_extra_http_headers({
        "Accept-Language": "en-US,en;q=0.9"
    })

    print(f"\n========== {time.strftime('%Y-%m-%d %H:%M:%S')} ==========")

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

    except Exception:
        tb = traceback.format_exc()
        traceback.print_exc()
        send_telegram_message(f"❌ <b>Unexpected Error</b>\n<pre>{tb[-3000:]}</pre>")

    finally:
        context.close()
