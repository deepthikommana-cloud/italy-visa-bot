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
    "prenotami_home": "https://prenotami.esteri.it/",
    "prenotami_services": "https://prenotami.esteri.it/Services",
}

STATE_FILE = "page_state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

INTERESTING_KEYWORDS = [
    "appointment",
    "appointments",
    "available",
    "calendar",
    "book",
    "booking",
    "prenota",
    "visa",
    "visas",
    "schengen",
    "study",
    "work",
    "waiting list",
    "lista d'attesa",
    "confirm your reservation",
    "reservation pending",
]

NEGATIVE_PATTERNS = [
    "no appointments available",
    "non ci sono appuntamenti disponibili",
    "there are no available appointments",
    "all appointments for this service are booked",
    "non sono disponibili appuntamenti",
    "fully booked",
]

POSITIVE_PATTERNS = [
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
    "waiting list",
    "lista d'attesa",
    "confirm your reservation",
    "reservation pending",
]


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str):
    print(f"[{now_str()}] {message}", flush=True)


def validate_env():
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not CHAT_ID:
        missing.append("CHAT_ID")
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))


def send_telegram(message: str):
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": message},
            timeout=20,
        )
        log(f"Telegram status: {response.status_code}")
        log(f"Telegram response: {response.text[:300]}")
    except Exception as e:
        log(f"Telegram error: {e}")


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def get_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        log(f"State load error: {e}")
        return {}


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def extract_keyword_hits(text: str) -> list:
    hits = []
    for keyword in INTERESTING_KEYWORDS:
        if keyword in text:
            hits.append(keyword)
    return hits


def classify_signal(text: str) -> str:
    for pattern in NEGATIVE_PATTERNS:
        if pattern in text:
            return "none"

    for pattern in POSITIVE_PATTERNS:
        if pattern in text:
            return "possible"

    return "unknown"


def fetch_page(url: str) -> dict:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    normalized = normalize_text(response.text)
    return {
        "url": url,
        "status_code": response.status_code,
        "text": normalized,
        "hash": get_hash(normalized),
        "keywords": extract_keyword_hits(normalized),
        "signal": classify_signal(normalized),
        "snippet": normalized[:1000],
    }


def compare_page(name: str, current: dict, previous: dict | None) -> list:
    alerts = []

    if not previous:
        alerts.append(f"{name}: first snapshot created")
        return alerts

    if current["hash"] != previous.get("hash"):
        alerts.append(f"{name}: page content changed")

    previous_keywords = set(previous.get("keywords", []))
    current_keywords = set(current.get("keywords", []))

    added_keywords = sorted(current_keywords - previous_keywords)
    removed_keywords = sorted(previous_keywords - current_keywords)

    if added_keywords:
        alerts.append(f"{name}: new keywords appeared: {', '.join(added_keywords[:8])}")

    if removed_keywords:
        alerts.append(f"{name}: keywords disappeared: {', '.join(removed_keywords[:8])}")

    previous_signal = previous.get("signal", "unknown")
    current_signal = current.get("signal", "unknown")

    if current_signal != previous_signal:
        alerts.append(f"{name}: signal changed from {previous_signal} to {current_signal}")

    return alerts


def main():
    validate_env()
    log("San Francisco public-page monitor started")
    send_telegram("🤖 San Francisco public-page visa monitor started.")

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
                log(f"{name} signal: {current['signal']}")
                log(
                    f"{name} keywords: "
                    f"{', '.join(current['keywords'][:10]) if current['keywords'] else 'none'}"
                )

                alerts = compare_page(name, current, previous)
                for alert in alerts:
                    log(alert)
                all_alerts.extend(alerts)

                new_state[name] = {
                    "hash": current["hash"],
                    "keywords": current["keywords"],
                    "signal": current["signal"],
                    "checked_at": now_str(),
                    "url": current["url"],
                    "snippet": current["snippet"],
                }

            if all_alerts:
                message = (
                    "🚨 San Francisco visa public-page change detected:\n\n"
                    + "\n".join(f"- {a}" for a in all_alerts[:10])
                    + "\n\nCheck:\n"
                    + "https://conssanfrancisco.esteri.it/en/servizi-consolari-e-visti/"
                    + "servizi-per-il-cittadino-straniero/visti/instructions-for-visas/\n"
                    + "https://prenotami.esteri.it/"
                )
                send_telegram(message)
            else:
                log("No meaningful public-page changes detected")

            save_state(new_state)
            state = new_state

        except Exception as e:
            log(f"Check error: {e}")

        log(f"Sleeping for {CHECK_INTERVAL} seconds")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
