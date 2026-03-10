import os
import requests
import time

# Get secrets from Railway environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

# Pages to monitor
URLS = [
    "https://prenotami.esteri.it/",
    "https://prenotami.esteri.it/Services"
]

# Headers to look like a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9"
}

# Track last known status to avoid duplicate alerts
last_status = "unknown"



def send_alert(message):
    """Send a Telegram message"""
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": message},
            timeout=10
        )
        print("Telegram alert sent")
    except Exception as e:
        print(f"Telegram error: {e}")



def alarm_alert():
    """Send 3 alerts spaced 5 seconds apart"""
    for _ in range(3):
        send_alert(
            ":rotating_light::rotating_light: ITALY VISA APPOINTMENT POSSIBLY OPEN! :rotating_light::rotating_light:\n"
            "Login immediately:\nhttps://prenotami.esteri.it/"
        )
        time.sleep(5)



def check_site():
    """Check each page for changes"""
    global last_status
    try:
        for url in URLS:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            page = resp.text.lower()

            if "no appointments available" in page \
               or "non ci sono appuntamenti disponibili" in page:
                status = "none"
            else:
                status = "possible"

            # Alert only if status changes
            if status != last_status:
                if status == "possible":
                    alarm_alert()
                else:
                    print("Still no appointments")
                last_status = status

    except Exception as e:
        print(f"Error checking site: {e}")



def main():
    while True:
        check_site()
        time.sleep(30)  # check every 30 seconds



if __name__ == "__main__":
    main()
    
