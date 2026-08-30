import sqlite3
import pandas as pd
import yfinance as yf
import os
import sys
from core.notifier import send_telegram_message, format_ipo_message
from core.db_manager import setup_halkarz_db, update_halkarz_db
from core.scraper import scrape_halkarz_list, scrape_halkarz_detail

def run_halkarz_pipeline():
    print("--- HALKA ARZ PIPELINE BASLADI ---")

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "halkarz.db")
    conn = setup_halkarz_db(db_path)

    print("Halka arz listesi cekiliyor...")
    ipo_list = scrape_halkarz_list()

    if not ipo_list:
        print("UYARI: Halka arz listesi cekilemedi!")
        send_telegram_message("Halka Arz Uyarisi: Liste verisi cekilemedi.")
        conn.close()
        return [], 0, 0, 0

    print(f"Toplam {len(ipo_list)} halka arz bulundu.")

    new_ipos = []
    updated_count = 0

    for i, ipo in enumerate(ipo_list):
        print(f"[{i+1}/{len(ipo_list)}] {ipo['bist_code']} - {ipo['company_name'][:30]}...")

        if ipo["detail_url"]:
            print(f"  Detaylar cekiliyor...")
            details = scrape_halkarz_detail(ipo["detail_url"])
            ipo.update(details)

        is_new = update_halkarz_db(conn, ipo)

        if is_new:
            new_ipos.append(ipo)
            print(f"  YENI!")
        else:
            updated_count += 1
            print(f"  Guncellendi.")

    conn.commit()
    conn.close()

    return new_ipos, len(ipo_list), len(new_ipos), updated_count


def send_halkarz_summary(new_ipos=None):
    """Son 6 halka arzin gunluk fiyat degisimlerini gonder. Yeni IPO varsa basa ekle."""
    print("--- HALKA ARZ OZETI BASLADI ---")

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "halkarz.db")
    if not os.path.exists(db_path):
        print("halkarz.db bulunamadi!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT bist_code, company_name, ipo_date, status, price, market, listing_date
        FROM halkarz_ipos
        WHERE bist_code != '' AND bist_code IS NOT NULL
          AND listing_date NOT LIKE '%Hazirlaniyor%'
          AND listing_date != '' AND listing_date IS NOT NULL
    """)
    ipos = cursor.fetchall()
    turkish_months = {
        "Ocak": 1, "Subat": 2, "Mart": 3, "Nisan": 4,
        "Mayis": 5, "Haziran": 6, "Temmuz": 7, "Agustos": 8,
        "Eylul": 9, "Ekim": 10, "Kasim": 11, "Aralik": 12
    }

    def parse_turkish_date(date_str):
        if not date_str:
            return pd.Timestamp.min
        try:
            parts = date_str.replace(",", "").split()
            day = int(parts[0])
            month = turkish_months.get(parts[1], 0)
            year = int(parts[2])
            return pd.Timestamp(year, month, day)
        except:
            return pd.Timestamp.min

    ipos_sorted = sorted(ipos, key=lambda x: parse_turkish_date(x[6]), reverse=True)
    ipos = ipos_sorted[:6]
    conn.close()

    msg = ""

    if new_ipos:
        msg += "YENI HALKA ARZLAR\n\n"
        for ipo in new_ipos:
            code = ipo.get("bist_code", "?")
            name = ipo.get("company_name", "N/A")[:30]
            price = ipo.get("price", "")
            price_str = f" - {price} TL" if price else ""
            msg += f"  {code} - {name}{price_str}\n"
        msg += "\n---\n\n"

    today = pd.Timestamp.now().strftime("%d %B %Y")
    msg += f"Son 6 Halka Arz - Gunluk Degisim\n{today}\n\n"

    status_emoji = {
        "Sonuçlandı": "✅",
        "Tamamlandı": "✅",
        "Ertelendi": "⏰",
        "": "📋",
    }

    for i, ipo in enumerate(ipos, 1):
        bist_code, company_name, ipo_date, status, ipo_price_str, market, listing_date = ipo
        emoji = status_emoji.get(status, "L")

        short_name = company_name.replace(" A.S.", "").replace(" A.S", "")[:25]

        msg += f"{i}. {emoji} {bist_code} - {short_name}\n"

        try:
            ticker = f"{bist_code}.IS"
            print(f"  {ticker} fiyat verisi cekiliyor...")
            t = yf.Ticker(ticker)
            current_price = t.fast_info.last_price
            yesterday_close = t.fast_info.previous_close

            if current_price and yesterday_close:
                daily_change = ((current_price - yesterday_close) / yesterday_close) * 100
                arrow = "YUKARI" if daily_change >= 0 else "ASAGI"
                sign = "+" if daily_change >= 0 else ""

                msg += f"   Dun: {yesterday_close:.2f} TL\n"
                msg += f"   Bugun: {current_price:.2f} TL ({arrow} {sign}{daily_change:.1f}%)\n"
            else:
                msg += f"   Fiyat verisi alinamadi\n"
        except Exception as e:
            print(f"  {bist_code} fiyat hatasi: {e}")
            msg += f"   Fiyat verisi alinamadi\n"

        if market:
            msg += f"   Pazar: {market}\n"

        msg += "\n"

    send_telegram_message(msg)
    print("--- HALKA ARZ OZETI BITTI ---")


# ============================================================
# MARKET DATA PIPELINE
# ============================================================

if os.environ.get("RUN_MARKET_DATA"):
    print("--- PIPELINE BASLADI ---")

    tickers = ["TRY=X", "XU100.IS"]
    print("Piyasa verileri cekiliyor...")

    try:
        df = yf.download(tickers, period="5d", interval="1d", progress=False)

        if "Close" in df:
            data = df["Close"].copy()
        else:
            data = df.copy()

        if data.empty:
            print("UYARI: Yahoo Finance veri dondurmedi!")
            send_telegram_message("Pipeline Uyarisi: Piyasa verisi cekilemedi.")
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
        print(f"Veri isleme hatasi: {e}")
        send_telegram_message(f"Pipeline Hatasi: Veri islenirken hata olustu: {e}")
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
        f"Data Pipeline Calisti!\n\n"
        f"Yeni Eklenen Veri: {added_count} gun\n"
        f"Son Veri Tarihi: {last_row['date']}\n"
        f"Dolar/TL: {float(last_row['usd_try']):.2f} TL\n"
        f"BIST 100: {float(last_row['bist100']):.2f}\n\n"
        f"Veritabani basariyla guncellendi."
    )

    print(f"Islem Tamamlandi! {added_count} yeni gun veritabanina islendi.")
    send_telegram_message(status_message)
    print("--- PIPELINE BITTI ---")

# ============================================================
# HALKA ARZ PIPELINE
# ============================================================

if os.environ.get("RUN_HALKARZ"):
    new_ipos, total, new_count, updated_count = run_halkarz_pipeline()

    if os.environ.get("HALKARZ_SUMMARY"):
        send_halkarz_summary(new_ipos)

    summary = (
        f"Halka Arz Ozeti: {total} IPO islendi, "
        f"{new_count} yeni, {updated_count} guncellendi"
    )
    send_telegram_message(summary)
    print("--- HALKA ARZ PIPELINE BITTI ---")
