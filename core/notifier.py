import os
import requests

telegram_token = os.environ.get("TELEGRAM_TOKEN")
chat_id = os.environ.get("CHAT_ID")

def send_telegram_message(message):
    if not telegram_token or not chat_id:
        print("Telegram token or chat ID is not set.")
        return

    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        print("Message sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message: {e}")

def format_ipo_message(ipo_data, is_new=False):
    prefix = "YENI HALKA ARZ!\n\n" if is_new else ""
    status_emoji = {
        "Sonuclandi": "Y",
        "Tamamlandi": "Y",
        "Ertelendi": "E",
        "": "L",
    }
    emoji = status_emoji.get(ipo_data.get("status", ""), "L")

    msg = f"{prefix}{emoji} *{ipo_data.get('company_name', 'N/A')}*\n"
    msg += f"Kod: `{ipo_data.get('bist_code', 'N/A')}`\n"
    msg += f"Tarih: {ipo_data.get('ipo_date', 'N/A')}\n"

    if ipo_data.get("status"):
        msg += f"Durum: {ipo_data['status']}\n"

    if ipo_data.get("price"):
        msg += f"Fiyat: {ipo_data['price']} TL\n"

    if ipo_data.get("lot_size"):
        msg += f"Lot: {ipo_data['lot_size']}\n"

    if ipo_data.get("distribution"):
        msg += f"Dagitim: {ipo_data['distribution']}\n"

    if ipo_data.get("market"):
        msg += f"Pazar: {ipo_data['market']}\n"

    if ipo_data.get("ipo_size"):
        msg += f"Buyukluk: {ipo_data['ipo_size']}\n"

    if ipo_data.get("listing_date"):
        msg += f"Islem Tarihi: {ipo_data['listing_date']}\n"

    if ipo_data.get("discount"):
        msg += f"Iskonto: {ipo_data['discount']}\n"

    return msg

def send_error_alert(component, error_msg):
    msg = f"ALERT: {component}\nDetay: {error_msg}"
    send_telegram_message(msg)
