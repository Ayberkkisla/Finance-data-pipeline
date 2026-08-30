import sqlite3
import pandas as pd
import yfinance as yf
import os
import sys
from core.notifier import send_telegram_message, format_ipo_message
from core.db_manager import setup_halkarz_db, update_halkarz_db
from core.scraper import scrape_halkarz_list, scrape_halkarz_detail

TURKISH_MONTHS = {
    "Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4,
    "Mayıs": 5, "Haziran": 6, "Temmuz": 7, "Ağustos": 8,
    "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12
}

def parse_ipo_date(date_str):
    if not date_str:
        return pd.Timestamp.min
    try:
        parts = date_str.replace(",", "").split()
        day = int(parts[0])
        month = TURKISH_MONTHS.get(parts[1], 0)
        year = int(parts[2])
        return pd.Timestamp(year, month, day)
    except:
        return pd.Timestamp.min

def run_halkarz_pipeline():
    print("--- HALKA ARZ PIPELINE BAŞLADI ---")

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "halkarz.db")
    conn = setup_halkarz_db(db_path)

    print("Halka arz listesi çekiliyor...")
    ipo_list = scrape_halkarz_list()

    if not ipo_list:
        print("UYARI: Halka arz listesi çekilemedi!")
        conn.close()
        return 0, 0, 0

    print(f"Toplam {len(ipo_list)} halka arz bulundu.")

    new_count = 0
    updated_count = 0

    for i, ipo in enumerate(ipo_list):
        print(f"[{i+1}/{len(ipo_list)}] {ipo['bist_code']} - {ipo['company_name'][:30]}...")

        if ipo["detail_url"]:
            print(f"  Detaylar çekiliyor...")
            details = scrape_halkarz_detail(ipo["detail_url"])
            ipo.update(details)

        is_new = update_halkarz_db(conn, ipo)

        if is_new:
            new_count += 1
            msg = format_ipo_message(ipo, is_new=True)
            send_telegram_message(msg)
            print(f"  YENİ! Telegram bildirimi gönderildi.")
        else:
            updated_count += 1
            print(f"  Güncellendi.")

    conn.commit()
    conn.close()

    return len(ipo_list), new_count, updated_count


def send_halkarz_summary():
    """Son 6 halka arzın günlük fiyat değişimlerini gönder."""
    print("--- HALKA ARZ ÖZETİ BAŞLADI ---")

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "halkarz.db")
    if not os.path.exists(db_path):
        print("halkarz.db bulunamadı!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT bist_code, company_name, ipo_date, status, price, market, listing_date
        FROM halkarz_ipos
        WHERE bist_code != '' AND bist_code IS NOT NULL
          AND listing_date NOT LIKE '%Hazırlanıyor%'
          AND listing_date != '' AND listing_date IS NOT NULL
    """)
    ipos = cursor.fetchall()

    ipos_sorted = sorted(ipos, key=lambda x: parse_ipo_date(x[6]), reverse=True)
    ipos = ipos_sorted[:6]
    conn.close()

    if not ipos:
        print("Veritabanında IPO bulunamadı!")
        return

    today = pd.Timestamp.now().strftime("%d %B %Y")
    msg = f"📊 *Son 6 Halka Arz - Günlük Değişim*\n📅 {today}\n\n"

    status_emoji = {
        "Sonuçlandı": "✅",
        "Tamamlandı": "✅",
        "Ertelendi": "⏰",
        "": "📋",
    }

    for i, ipo in enumerate(ipos, 1):
        bist_code, company_name, ipo_date, status, ipo_price_str, market, listing_date = ipo
        emoji = status_emoji.get(status, "📋")

        short_name = company_name.replace(" A.Ş.", "").replace(" A.Ş", "")[:25]

        msg += f"{i}. {emoji} *{bist_code}* - {short_name}\n"

        try:
            ticker = f"{bist_code}.IS"
            print(f"  {ticker} fiyat verisi çekiliyor...")
            t = yf.Ticker(ticker)
            current_price = t.fast_info.last_price
            yesterday_close = t.fast_info.previous_close

            if current_price and yesterday_close:
                daily_change = ((current_price - yesterday_close) / yesterday_close) * 100
                arrow = "▲" if daily_change >= 0 else "▼"
                sign = "+" if daily_change >= 0 else ""

                msg += f"   💰 Dün: {yesterday_close:.2f} TL\n"
                msg += f"   📈 Bugün: {current_price:.2f} TL ({arrow} {sign}{daily_change:.1f}%)\n"
            else:
                msg += f"   📈 Fiyat verisi alınamadı\n"
        except Exception as e:
            print(f"  {bist_code} fiyat hatası: {e}")
            msg += f"   📈 Fiyat verisi alınamadı\n"

        if market:
            msg += f"   🏛️ {market}\n"

        msg += "\n"

    send_telegram_message(msg)
    print("--- HALKA ARZ ÖZETİ BİTTİ ---")


# ============================================================
# MARKET DATA PIPELINE
# ============================================================

if os.environ.get("RUN_MARKET_DATA"):
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
            sys.exit()

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
        sys.exit()

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance_data.db")
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

# ============================================================
# HALKA ARZ PIPELINE
# ============================================================

if os.environ.get("RUN_HALKARZ"):
    total, new_count, updated_count = run_halkarz_pipeline()

    if os.environ.get("HALKARZ_SUMMARY"):
        send_halkarz_summary()

    summary = (
        f"📋 *Halka Arz Özeti:* {total} IPO işlendi, "
        f"{new_count} yeni, {updated_count} güncellendi"
    )
    send_telegram_message(summary)
    print("--- HALKA ARZ PIPELINE BİTTİ ---")
