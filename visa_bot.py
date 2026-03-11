import os
import time
import json
import hashlib
from datetime import datetime
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "180"))

URLS = {
    "sf_visa_instructions": "https://conssanfrancisco.esteri.it/en/servizi-consolari-e-visti/servizi-per-il-cittadino-straniero/visti/instructions-for-visas/",
    "sf_visas_main": "https://conssanfrancisco.esteri.it/en/servizi-consolari-e-visti/servizi-per-il-cittadino-straniero/visti/",
}

STATE_FILE = "/tmp/page_state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message):
    print(f"[{now_str()}] {message}", flush=True)


def validate_env():
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not CHAT_ID:
        missing.append("CHAT_ID")
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))


def send_telegram(message):
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": message},
            timeout=20,
        )
        log(f"Telegram status: {response.status_code}")
    except Exception as e:
        log(f"Telegram error: {e}")


def normalize_text(text):
    return " ".join(text.lower().split())


def get_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        log(f"State load error: {e}")
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def fetch_page(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    normalized = normalize_text(response.text)
    return {
        "url": url,
        "status_code": response.status_code,
        "hash": get_hash(normalized),
        "snippet": normalized[:1000],
    }


def compare_page(name, current, previous):
    alerts = []

    if not previous:
        return alerts

    if current["hash"] != previous.get("hash"):
        alerts.append(f"{name}: page content changed")

    return alerts


def main():
    validate_env()
    log("San Francisco public-page monitor started")

    state = load_state()

    while True:
        try:
            all_alerts = []
            new_state = {}

            for name, url in URLS.items():
                log(f"Checking {name}: {url}")
                current = fetch_page(url)
                previous = state.get(name)

                log(f"{name} HTTP status: {current['status_code']}")

                alerts = compare_page(name, current, previous)
                for alert in alerts:
                    log(alert)
                all_alerts.extend(alerts)

                new_state[name] = {
                    "hash": current["hash"],
                    "checked_at": now_str(),
                    "url": current["url"],
                    "snippet": current["snippet"],
                }

            if not state:
                log("Initial snapshot saved. No Telegram alert sent.")
            elif all_alerts:
                message = (
                    "🚨 San Francisco visa public-page change detected:\n\n"
                    + "\n".join(f"- {a}" for a in all_alerts[:10])
                    + "\n\nCheck:\n"
                    + "https://conssanfrancisco.esteri.it/en/servizi-consolari-e-visti/servizi-per-il-cittadino-straniero/visti/instructions-for-visas/"
                )
                send_telegram(message)
            else:
                log("No page changes detected")

            save_state(new_state)
            state = new_state

        except Exception as e:
            log(f"Check error: {e}")

        log(f"Sleeping for {CHECK_INTERVAL} seconds")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
