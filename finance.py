import sqlite3
import pandas as pd
import yfinance as yf
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_message(message):
    """Telegram botu üzerinden bildirim gönderen fonksiyon."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=30)
        print(f"Telegram Yanıt Kodu: {res.status_code}")
    except Exception as e:
        print(f"Telegram Bağlantı Hatası: {e}")

print("--- PIPELINE BAŞLADI ---")

tickers = ["TRY=X", "XU100.IS"]
print("Piyasa verileri çekiliyor...")

try:
    df = yf.download(tickers, period="5d", interval="1d", progress=False)

    if "Close" in df:
        data = df["Close"].copy()
    else:
        data = df.copy()

    if data.empty:
        print("UYARI: Yahoo Finance veri döndürmedi!")
        send_telegram_message("⚠️ *Pipeline Uyarısı:* Piyasa verisi çekilemedi.")
        exit()

    data = data.reset_index()

    data.rename(columns={
        "Date": "date",
        "XU100.IS": "bist100",
        "TRY=X": "usd_try"
    }, inplace=True)

    data["date"] = pd.to_datetime(data["date"]).dt.strftime("%Y-%m-%d")
    data = data.ffill().dropna()

except Exception as e:
    print(f"Veri işleme hatası: {e}")
    send_telegram_message(f"🚨 *Pipeline Hatası:* Veri işlenirken hata oluştu: {e}")
    exit()

db_path = "/home/ayberk/projeler/finance_data.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_market_data (
    date TEXT PRIMARY KEY,
    bist100 REAL,
    usd_try REAL
)
""")

added_count = 0
for index, row in data.iterrows():
    try:
        cursor.execute("""
        INSERT INTO daily_market_data (date, bist100, usd_try)
        VALUES (?, ?, ?)
        """, (str(row["date"]), float(row["bist100"]), float(row["usd_try"])))
        added_count += 1
    except sqlite3.IntegrityError:
 
        pass

conn.commit()
conn.close()

last_row = data.iloc[-1]
status_message = (
    f"🚀 *Data Pipeline Çalıştı!*\n\n"
    f"📊 *Yeni Eklenen Veri:* {added_count} gün\n"
    f"📅 *Son Veri Tarihi:* {last_row['date']}\n"
    f"💵 *Dolar/TL:* {float(last_row['usd_try']):.2f} TL\n"
    f"📈 *BIST 100:* {float(last_row['bist100']):.2f}\n\n"
    f"✅ Veritabanı başarıyla güncellendi."
)

print(f"İşlem Tamamlandı! {added_count} yeni gün veritabanına işlendi.")
send_telegram_message(status_message)
print("--- PIPELINE BİTTİ ---")