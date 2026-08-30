import os
import requests

telegram_token = os.environ.get("TELEGRAM_TOKEN")
chat_id = os.environ.get("CHAT_ID")

def send_telegram_message(message):
    if not telegram_token or not chat_id:
        print("Telegram token or chat ID is not set.")
        return

    url = "https://api.telegram.org/bot{}/sendMessage".format(telegram_token)
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
        print("Failed to send message: {}".format(e))

def format_ipo_message(ipo_data, is_new=False):
    prefix = "🆕 *YENİ HALKA ARZ!*\n\n" if is_new else ""
    status_emoji = {
        "Sonuçlandı": "✅",
        "Tamamlandı": "✅",
        "Ertelendi": "⏰",
        "": "📋",
    }
    emoji = status_emoji.get(ipo_data.get("status", ""), "📋")

    msg = "{}{}*{}*\n".format(prefix, emoji, ipo_data.get("company_name", "N/A"))
    msg += "📌 Kod: `{}`\n".format(ipo_data.get("bist_code", "N/A"))
    msg += "📅 Tarih: {}\n".format(ipo_data.get("ipo_date", "N/A"))

    if ipo_data.get("status"):
        msg += "📊 Durum: {}\n".format(ipo_data["status"])

    if ipo_data.get("price"):
        msg += "💰 Fiyat: {} TL\n".format(ipo_data["price"])

    if ipo_data.get("lot_size"):
        msg += "📦 Lot: {}\n".format(ipo_data["lot_size"])

    if ipo_data.get("distribution"):
        msg += "🔄 Dağıtım: {}\n".format(ipo_data["distribution"])

    if ipo_data.get("market"):
        msg += "🏛️ Pazar: {}\n".format(ipo_data["market"])

    if ipo_data.get("ipo_size"):
        msg += "💵 Büyüklük: {}\n".format(ipo_data["ipo_size"])

    if ipo_data.get("listing_date"):
        msg += "📈 İşlem Tarihi: {}\n".format(ipo_data["listing_date"])

    if ipo_data.get("discount"):
        msg += "📉 İskonto: {}\n".format(ipo_data["discount"])

    return msg

def send_error_alert(component, error_msg):
    """Hata durumunda Telegram'a acil durum bildirimi gonder."""
    msg = "🚨 *HATA:* {}\nDetay: {}".format(component, error_msg)
    send_telegram_message(msg)
