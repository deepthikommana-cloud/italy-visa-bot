import os
import time
import traceback
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

PRENOTAMI_EMAIL = os.getenv("PRENOTAMI_EMAIL")
PRENOTAMI_PASSWORD = os.getenv("PRENOTAMI_PASSWORD")

LOGIN_URL = "https://prenotami.esteri.it/"
SERVICES_URL = "https://prenotami.esteri.it/Services"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def log(msg: str):
    print(msg, flush=True)


def validate_env():
    missing = []
    if not PRENOTAMI_EMAIL:
        missing.append("PRENOTAMI_EMAIL")
    if not PRENOTAMI_PASSWORD:
        missing.append("PRENOTAMI_PASSWORD")
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def dump_page_debug(page, label: str):
    log(f"\n--- {label} ---")
    try:
        log(f"{label} URL: {page.url}")
    except Exception as e:
        log(f"{label} URL error: {e}")

    try:
        log(f"{label} TITLE: {page.title()}")
    except Exception as e:
        log(f"{label} TITLE error: {e}")

    try:
        snippet = normalize_text(page.content())[:2000]
        log(f"{label} HTML SNIPPET: {snippet}")
    except Exception as e:
        log(f"{label} HTML error: {e}")

    try:
        path = f"{label.lower().replace(' ', '_')}.png"
        page.screenshot(path=path, full_page=True)
        log(f"{label} screenshot saved: {path}")
    except Exception as e:
        log(f"{label} screenshot error: {e}")


def list_frames(page):
    log("\n--- FRAMES ---")
    try:
        for i, frame in enumerate(page.frames):
            try:
                log(f"Frame {i}: {frame.url}")
            except Exception:
                log(f"Frame {i}: <url unavailable>")
    except Exception as e:
        log(f"Frame listing error: {e}")


def accept_cookies_if_present(page):
    labels = ["Accept", "I Agree", "Accetta", "OK", "Accept all"]
    for label in labels:
        try:
            log(f"Trying cookie button: {label}")
            page.get_by_role("button", name=label).click(timeout=2000)
            log(f"Clicked cookie button: {label}")
            page.wait_for_timeout(1500)
            return
        except Exception:
            pass
    log("No cookie popup handled")


def click_login_and_capture(context, page):
    targets = [
        'a:has-text("Login")',
        'a:has-text("Accedi")',
        'button:has-text("Login")',
        'button:has-text("Accedi")',
        'text=Login',
        'text=Accedi',
    ]

    for target in targets:
        try:
            log(f"Trying login target: {target}")
            locator = page.locator(target).first
            locator.wait_for(state="visible", timeout=5000)

            try:
                with context.expect_page(timeout=5000) as new_page_info:
                    locator.click(timeout=3000)
                new_page = new_page_info.value
                new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                new_page.wait_for_timeout(5000)
                log(f"Login opened a new page via: {target}")
                return new_page
            except Exception:
                locator.click(timeout=3000)
                page.wait_for_timeout(5000)
                log(f"Login clicked on same page via: {target}")
                return page

        except Exception as e:
            log(f"Login target failed: {target} | {e}")

    log("No login target found; staying on current page")
    return page


def inspect_for_login_fields(page):
    log("\n--- INSPECTING MAIN PAGE FOR FIELDS ---")
    selectors = [
        'input[name="Email"]',
        'input[name="email"]',
        'input[type="email"]',
        'input[autocomplete="username"]',
        'input[type="text"]',
        '#Email',
        '#email',
        'input[name="Password"]',
        'input[name="password"]',
        'input[type="password"]',
        'input[autocomplete="current-password"]',
        '#Password',
        '#password',
    ]

    for selector in selectors:
        try:
            count = page.locator(selector).count()
            log(f"Main page selector {selector} count: {count}")
        except Exception as e:
            log(f"Main page selector {selector} error: {e}")

    list_frames(page)

    log("\n--- INSPECTING FRAMES FOR FIELDS ---")
    for i, frame in enumerate(page.frames):
        for selector in selectors:
            try:
                count = frame.locator(selector).count()
                if count > 0:
                    log(f"Frame {i} selector {selector} count: {count}")
            except Exception:
                pass


def try_fill_login(page):
    candidates = [page] + list(page.frames)

    email_selectors = [
        'input[name="Email"]',
        'input[name="email"]',
        'input[type="email"]',
        'input[autocomplete="username"]',
        'input[type="text"]',
        '#Email',
        '#email',
    ]

    password_selectors = [
        'input[name="Password"]',
        'input[name="password"]',
        'input[type="password"]',
        'input[autocomplete="current-password"]',
        '#Password',
        '#password',
    ]

    for idx, target in enumerate(candidates):
        log(f"\nTrying target {idx} for login fill")
        email_ok = False
        password_ok = False

        for selector in email_selectors:
            try:
                locator = target.locator(selector).first
                locator.wait_for(state="visible", timeout=3000)
                locator.fill(PRENOTAMI_EMAIL, timeout=3000)
                log(f"Filled email using selector: {selector} on target {idx}")
                email_ok = True
                break
            except Exception:
                pass

        for selector in password_selectors:
            try:
                locator = target.locator(selector).first
                locator.wait_for(state="visible", timeout=3000)
                locator.fill(PRENOTAMI_PASSWORD, timeout=3000)
                log(f"Filled password using selector: {selector} on target {idx}")
                password_ok = True
                break
            except Exception:
                pass

        if email_ok and password_ok:
            log(f"Successfully filled both fields on target {idx}")
            return target

    raise RuntimeError("Could not find visible login fields on page or frames.")


def try_submit_login(target):
    submit_selectors = [
        'button[type="submit"]',
        'input[type="submit"]',
    ]

    for selector in submit_selectors:
        try:
            target.locator(selector).first.click(timeout=3000)
            log(f"Clicked submit selector: {selector}")
            return
        except Exception:
            pass

    for label in ["Login", "Accedi", "Sign in"]:
        try:
            target.get_by_role("button", name=label).click(timeout=3000)
            log(f"Clicked submit button label: {label}")
            return
        except Exception:
            pass

    raise RuntimeError("Could not submit login form.")


def main():
    validate_env()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=500,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="en-US",
            viewport={"width": 1440, "height": 1000},
        )

        page = context.new_page()

        try:
            log("Opening homepage")
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            dump_page_debug(page, "HOME")

            accept_cookies_if_present(page)
            dump_page_debug(page, "AFTER_COOKIES")

            login_page = click_login_and_capture(context, page)
            dump_page_debug(login_page, "AFTER_LOGIN_CLICK")

            inspect_for_login_fields(login_page)

            target = try_fill_login(login_page)
            dump_page_debug(login_page, "AFTER_FILL")

            try_submit_login(target)
            login_page.wait_for_timeout(8000)
            dump_page_debug(login_page, "AFTER_SUBMIT")

            log("\nNow trying to open Services page")
            login_page.goto(SERVICES_URL, wait_until="domcontentloaded", timeout=60000)
            login_page.wait_for_timeout(8000)
            dump_page_debug(login_page, "SERVICES")

            log("Done. Browser will stay open for 60 seconds.")
            time.sleep(60)

        except PlaywrightTimeoutError:
            log("Timed out while loading page.")
            traceback.print_exc()
            time.sleep(60)
        except Exception as e:
            log(f"Error: {e}")
            traceback.print_exc()
            time.sleep(60)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
