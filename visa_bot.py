import os
import requests
import time

# Read environment variables from Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

# Italy visa appointment site
URL = "https://prenotami.esteri.it/"

def send_alert():
    """Send a Telegram message."""
    message = ":rotating_light: TEST: Italy visa bot is running! Check appointments here: https://prenotami.esteri.it/"
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={
                "chat_id": CHAT_ID,
                "text": message
            }
        )
        print("Alert sent!")
    except Exception as e:
        print(f"Error sending alert: {e}")

def check_site():
    """Check the appointment page."""
    try:
        response = requests.get(URL)
        if "No appointments available" not in response.text:
            send_alert()
        else:
            print("No appointments yet")
    except Exception as e:
        print(f"Error checking site: {e}")

def main():
    # TEMPORARY TEST MESSAGE
    send_alert()
    while True:
        check_site()
        time.sleep(180)  # check every 3 minutes

if __name__ == "__main__":
    main()
  
