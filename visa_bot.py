import os
import requests
import time

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

URLS = [
    "https://prenotami.esteri.it/",
    "https://prenotami.esteri.it/Services"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept-Language": "en-US,en;q=0.9"
}

last_status = "unknown"



def send_alert(message):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={
                "chat_id": CHAT_ID,
                "text": message
            }
        )
        print("Telegram alert sent")
    except Exception as e:
        print(f"Telegram error: {e}")



def alarm_alert():
    for i in range(3):  # send 3 alerts so you notice
        send_alert(
            ":rotating_light::rotating_light: ITALY VISA APPOINTMENT POSSIBLY OPEN! :rotating_light::rotating_light:\n"
            "Login immediately:\n"
            "https://prenotami.esteri.it/"
        )
        time.sleep(5)



def check_site():
    global last_status

    try:
        for url in URLS:

            response = requests.get(url, headers=headers, timeout=20)
            page = response.text.lower()

            if "no appointments available" in page or "non ci sono appuntamenti disponibili" in page:
                status = "none"
            else:
                status = "possible"

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
        time.sleep(60)



if __name__ == "__main__":
    main()
    
