import requests
import time
import os

# ====== CONFIGURE VIA ENVIRONMENT VARIABLES ======
# Set these in Railway (or your cloud service)
# TELEGRAM_TOKEN = your BotFather token
# CHAT_ID = your numeric chat ID
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
# ==================================================

# Italy appointment page URL
URL = "https://prenotami.esteri.it/"

def send_alert():
    """Send a Telegram message to notify about available appointments."""
    message = ":rotating_light: Italy visa appointments might be open! Check now: https://prenotami.esteri.it/"
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": message}
        )
        print("Alert sent!")
    except Exception as e:
        print(f"Error sending alert: {e}")

def check_site():
    """Check the Italy appointment page for availability."""
    try:
        response = requests.get(URL)
        # If "No appointments available" is NOT in the page, send alert
        if "No appointments available" not in response.text:
            send_alert()
        else:
            print("No appointments yet")
    except Exception as e:
        print(f"Error checking site: {e}")

def main():
    """Run the bot continuously every 3 minutes."""
    send_alert()
    while True:
        check_site()
        time.sleep(180)  # Wait 3 minutes between checks

if __name__ == "__main__":
    main()
