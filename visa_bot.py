import os
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PRENOTAMI_EMAIL = os.getenv("PRENOTAMI_EMAIL")
PRENOTAMI_PASSWORD = os.getenv("PRENOTAMI_PASSWORD")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "180"))

LOGIN_URL = "https://prenotami.esteri.it/"
SERVICES_URL = "https://prenotami.esteri.it/Services"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

last_state = "unknown"


def validate_env():
    required = {
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "CHAT_ID": CHAT_ID,
        "PRENOTAMI_EMAIL": PRENOTAMI_EMAIL,
        "PRENOTAMI_PASSWORD": PRENOTAMI_PASSWORD,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))


def send_telegram(message: str):
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": message},
            timeout=15,
        )
        print(f"Telegram status: {response.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def detect_state_from_text(text: str) -> str:
    t = normalize_text(text)

    pending_patterns = [
        "confirm your reservation",
        "reservation pending",
        "conferma la prenotazione",
        "prenotazione da confermare",
        "mandatory appointment confirmation",
    ]

    waitlist_patterns = [
        "waiting list",
        "lista d'attesa",
        "join the waiting list",
        "entra in lista d'attesa",
    ]

    no_slot_patterns = [
        "no appointments available",
        "non ci sono appuntamenti disponibili",
        "all appointments for this service are booked",
        "non sono disponibili appuntamenti",
        "fully booked",
        "there are no available appointments",
    ]

    positive_patterns = [
        "select a date",
        "calendar",
        "book",
        "prenota",
        "available appointments",
        "date available",
        "giorni disponibili",
        "date disponibili",
        "choose day",
        "choose date",
    ]

    for p in pending_patterns:
        if p in t:
            return "pending_confirmation"

    for p in waitlist_patterns:
        if p in t:
            return "waitlist"

    for p in no_slot_patterns:
        if p in t:
            return "none"

    for p in positive_patterns:
        if p in t:
            return "possible"

    return "unknown"


def try_click_if_exists(page, selectors):
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.is_visible(timeout=2000):
                locator.click(timeout=3000)
                return True
        except Exception:
            pass
    return False


def accept_cookies_if_present(page):
    labels = ["Accept", "I Agree", "Accetta", "OK", "Accept all"]
    for label in labels:
        try:
            page.get_by_role("button", name=label).click(timeout=2000)
            return
        except Exception:
            pass


def fill_login_form(page):
    email_selectors = [
        'input[name="Email"]',
        'input[name="email"]',
        'input[type="email"]',
        '#Email',
        '#email',
    ]

    password_selectors = [
        'input[name="Password"]',
        'input[name="password"]',
        'input[type="password"]',
        '#Password',
        '#password',
    ]

    email_ok = False
    password_ok = False

    for selector in email_selectors:
        try:
            page.locator(selector).first.fill(PRENOTAMI_EMAIL, timeout=3000)
            email_ok = True
            break
        except Exception:
            pass

    for selector in password_selectors:
        try:
            page.locator(selector).first.fill(PRENOTAMI_PASSWORD, timeout=3000)
            password_ok = True
            break
        except Exception:
            pass

    if not email_ok or not password_ok:
        raise RuntimeError("Could not find login fields.")


def submit_login(page):
    submit_selectors = [
        'button[type="submit"]',
        'input[type="submit"]',
    ]

    for selector in submit_selectors:
        try:
            page.locator(selector).first.click(timeout=3000)
            return
        except Exception:
            pass

    for label in ["Login", "Accedi", "Sign in"]:
        try:
            page.get_by_role("button", name=label).click(timeout=3000)
            return
        except Exception:
            pass

    raise RuntimeError("Could not submit login form.")


def open_san_francisco_visa_service(page) -> str:
    page.goto(SERVICES_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    services_text = normalize_text(page.content())
    print("Loaded services page")

    # Since your account only shows San Francisco, we can search for visa-related cards/buttons/links.
    visa_selectors = [
        'a:has-text("Visa")',
        'a:has-text("Visas")',
        'a:has-text("National Visa")',
        'a:has-text("Schengen")',
        'a:has-text("Study")',
        'a:has-text("Work")',
        'button:has-text("Visa")',
        'button:has-text("Visas")',
        'text=Visa',
        'text=Visas',
        'text=Schengen',
        'text=National Visa',
        'text=Study',
        'text=Work',
    ]

    clicked = try_click_if_exists(page, visa_selectors)

    if clicked:
        page.wait_for_load_state("networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        return page.content()

    # Fallback: if no explicit click target is found, inspect Services page itself.
    if any(word in services_text for word in ["visa", "visas", "schengen", "study", "work"]):
        return page.content()

    raise RuntimeError("Could not find a visa-related service on the Services page.")


def login_and_check() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
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
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            accept_cookies_if_present(page)
            fill_login_form(page)
            submit_login(page)

            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(4000)

            current_url = page.url.lower()
            current_text = normalize_text(page.content())

            if "login" in current_url and any(x in current_text for x in ["invalid", "wrong", "errore"]):
                raise RuntimeError("Login failed. Check email/password.")

            service_html = open_san_francisco_visa_service(page)
            state = detect_state_from_text(service_html)

            browser.close()
            return state

        except PlaywrightTimeoutError:
            browser.close()
            raise RuntimeError("Timed out while loading Prenotami.")
        except Exception:
            browser.close()
            raise


def handle_state(state: str):
    global last_state

    print(f"Detected state: {state} | Previous: {last_state}")

    if state == last_state:
        return

    if state == "possible":
        send_telegram(
            "🚨 San Francisco Prenotami: POSSIBLE APPOINTMENT AVAILABILITY detected.\n\n"
            "Log in now:\nhttps://prenotami.esteri.it/"
        )
    elif state == "waitlist":
        send_telegram(
            "🟡 San Francisco Prenotami: WAITLIST detected.\n\n"
            "Log in now:\nhttps://prenotami.esteri.it/"
        )
    elif state == "pending_confirmation":
        send_telegram(
            "✅ San Francisco Prenotami: PENDING CONFIRMATION detected.\n\n"
            "Log in now:\nhttps://prenotami.esteri.it/"
        )
    elif state == "none":
        print("No appointments available.")
    else:
        send_telegram(
            "ℹ️ San Francisco Prenotami: UNKNOWN state detected.\n\n"
            "Please check manually:\nhttps://prenotami.esteri.it/"
        )

    last_state = state


def main():
    validate_env()
    print("San Francisco Prenotami monitor started.")
    send_telegram("🤖 San Francisco Prenotami monitor started.")

    while True:
        try:
            state = login_and_check()
            handle_state(state)
        except Exception as e:
            print(f"Check error: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
