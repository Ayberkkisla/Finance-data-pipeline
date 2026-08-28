import sqlite3
import pandas as pd
import yfinance as yf
import requests
import os
import sys
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

REQUEST_DELAY = 2

def send_telegram_message(message):
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

def fetch_page(url):
    try:
        time.sleep(REQUEST_DELAY)
        res = requests.get(url, headers=HEADERS, timeout=30)
        res.raise_for_status()
        return res.text
    except Exception as e:
        print(f"Sayfa çekilemedi ({url}): {e}")
        return None

def scrape_halkarz_list():
    html = fetch_page("https://halkarz.com/")
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    ipos = []

    items = soup.select("ul.halka-arz-list li article.index-list")
    for item in items:
        try:
            badge_icon = item.select_one(".il-badge i")
            badge_text = ""
            if badge_icon:
                if "fa-check-double" in badge_icon.get("class", []):
                    badge_text = "Sonuçlandı"
                elif "fa-check" in badge_icon.get("class", []):
                    badge_text = "Tamamlandı"

            ert_badge = item.select_one(".il-ert a")
            if ert_badge:
                badge_text = "Ertelendi"

            new_badge = item.select_one(".il-new")
            is_new = bool(new_badge)

            bist_code_el = item.select_one(".il-bist-kod")
            bist_code = bist_code_el.get_text(strip=True) if bist_code_el else ""

            name_el = item.select_one(".il-halka-arz-sirket a")
            company_name = name_el.get_text(strip=True) if name_el else ""
            detail_url = name_el["href"] if name_el and name_el.has_attr("href") else ""

            date_el = item.select_one(".il-halka-arz-tarihi time")
            ipo_date = date_el.get_text(strip=True) if date_el else ""

            if detail_url and not detail_url.startswith("http"):
                detail_url = urljoin("https://halkarz.com/", detail_url)

            ipos.append({
                "bist_code": bist_code,
                "company_name": company_name,
                "ipo_date": ipo_date,
                "status": badge_text,
                "is_new": is_new,
                "detail_url": detail_url,
            })
        except Exception as e:
            print(f"Liste parse hatası: {e}")
            continue

    return ipos

def scrape_halkarz_detail(url):
    html = fetch_page(url)
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    details = {}

    try:
        all_text = soup.get_text(" ", strip=True)

        price_match = re.search(r"Halka\s*Arz\s*Fiyat[ıi]\s*/?\s*Aral[ıi][ğg][ıi]\s*:\s*([\d.,]+)\s*TL", all_text)
        if price_match:
            details["price"] = price_match.group(1).strip()

        lot_match = re.search(r"Pay\s*:\s*([\d.]+)\s*Lot", all_text)
        if lot_match:
            details["lot_size"] = lot_match.group(1).strip()

        method_match = re.search(r"D[aä][ğg][ıı]t[ıi]m\s*Y[öo]ntemi\s*:\s*(.+?)(?=Pay\s*:|$)", all_text)
        if method_match:
            details["distribution"] = method_match.group(1).strip()

        broker_match = re.search(r"Arac[ıi]\s*Kurum\s*:\s*(.+?)(?=Bist\s*Kodu|$)", all_text)
        if broker_match:
            details["broker"] = broker_match.group(1).strip()

        market_match = re.search(r"Pazar\s*:\s*(.+?)(?=Bist\s*İlk|$)", all_text)
        if market_match:
            details["market"] = market_match.group(1).strip()

        size_match = re.search(r"Halka\s*Arz\s*B[üy]y[üy]kll[üu][ğg][üu]\s*[~≈]\s*(.+?TL)", all_text)
        if not size_match:
            size_match = re.search(r"Halka\s*Arz\s*B[üy]y[üy]kll[üy][ğg][üu]\s*:\s*[~≈]?\s*(.+?TL)", all_text)
        if size_match:
            details["ipo_size"] = size_match.group(1).strip()

        listing_match = re.search(r"Bist\s*İlk\s*İ[sş]lem\s*Tarihi\s*:\s*(.+?)(?=Son\s*Güncelleme|$)", all_text)
        if listing_match:
            details["listing_date"] = listing_match.group(1).strip()

        discount_match = re.search(r"Halka\s*Arz\s*İskontosu\s*:\s*%([\d.,]+)", all_text)
        if discount_match:
            details["discount"] = f"%{discount_match.group(1)}"

        freefloat_match = re.search(r"Halka\s*A[cç][ıı][lq]l[ıi][kq]\s*:\s*%([\d.,]+)", all_text)
        if freefloat_match:
            details["free_float"] = f"%{freefloat_match.group(1)}"

        spk_match = re.search(r"SPK.*?(\d{4}/\d+)", all_text)
        if spk_match:
            details["spk_bulletin"] = spk_match.group(1)

    except Exception as e:
        print(f"Detail parse hatası: {e}")

    return details

def setup_halkarz_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS halkarz_ipos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bist_code TEXT,
        company_name TEXT,
        ipo_date TEXT,
        status TEXT,
        price TEXT,
        lot_size TEXT,
        distribution TEXT,
        broker TEXT,
        market TEXT,
        ipo_size TEXT,
        listing_date TEXT,
        discount TEXT,
        free_float TEXT,
        spk_bulletin TEXT,
        detail_url TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(company_name, ipo_date)
    )
    """)
    conn.commit()
    return conn

def update_halkarz_db(conn, ipo_data):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM halkarz_ipos WHERE company_name = ? AND ipo_date = ?",
                   (ipo_data.get("company_name", ""), ipo_data.get("ipo_date", "")))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
        UPDATE halkarz_ipos
        SET bist_code = ?, status = ?, price = ?, lot_size = ?, distribution = ?, broker = ?,
            market = ?, ipo_size = ?, listing_date = ?, discount = ?, free_float = ?,
            spk_bulletin = ?, last_updated = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (
            ipo_data.get("bist_code", ""),
            ipo_data.get("status", ""),
            ipo_data.get("price", ""),
            ipo_data.get("lot_size", ""),
            ipo_data.get("distribution", ""),
            ipo_data.get("broker", ""),
            ipo_data.get("market", ""),
            ipo_data.get("ipo_size", ""),
            ipo_data.get("listing_date", ""),
            ipo_data.get("discount", ""),
            ipo_data.get("free_float", ""),
            ipo_data.get("spk_bulletin", ""),
            existing[0],
        ))
        return False
    else:
        cursor.execute("""
        INSERT INTO halkarz_ipos (bist_code, company_name, ipo_date, status, price, lot_size,
            distribution, broker, market, ipo_size, listing_date, discount, free_float,
            spk_bulletin, detail_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ipo_data.get("bist_code", ""),
            ipo_data.get("company_name", ""),
            ipo_data.get("ipo_date", ""),
            ipo_data.get("status", ""),
            ipo_data.get("price", ""),
            ipo_data.get("lot_size", ""),
            ipo_data.get("distribution", ""),
            ipo_data.get("broker", ""),
            ipo_data.get("market", ""),
            ipo_data.get("ipo_size", ""),
            ipo_data.get("listing_date", ""),
            ipo_data.get("discount", ""),
            ipo_data.get("free_float", ""),
            ipo_data.get("spk_bulletin", ""),
            ipo_data.get("detail_url", ""),
        ))
        return True

def format_ipo_message(ipo_data, is_new=False):
    prefix = "🆕 *YENİ HALKA ARZ!*\n\n" if is_new else ""
    status_emoji = {
        "Sonuçlandı": "✅",
        "Tamamlandı": "✅",
        "Ertelendi": "⏰",
        "": "📋",
    }
    emoji = status_emoji.get(ipo_data.get("status", ""), "📋")

    msg = f"{prefix}{emoji} *{ipo_data.get('company_name', 'N/A')}*\n"
    msg += f"📌 Kod: `{ipo_data.get('bist_code', 'N/A')}`\n"
    msg += f"📅 Tarih: {ipo_data.get('ipo_date', 'N/A')}\n"

    if ipo_data.get("status"):
        msg += f"📊 Durum: {ipo_data['status']}\n"

    if ipo_data.get("price"):
        msg += f"💰 Fiyat: {ipo_data['price']} TL\n"

    if ipo_data.get("lot_size"):
        msg += f"📦 Lot: {ipo_data['lot_size']}\n"

    if ipo_data.get("distribution"):
        msg += f"🔄 Dağıtım: {ipo_data['distribution']}\n"

    if ipo_data.get("market"):
        msg += f"🏛️ Pazar: {ipo_data['market']}\n"

    if ipo_data.get("ipo_size"):
        msg += f"💵 Büyüklük: {ipo_data['ipo_size']}\n"

    if ipo_data.get("listing_date"):
        msg += f"📈 İşlem Tarihi: {ipo_data['listing_date']}\n"

    if ipo_data.get("discount"):
        msg += f"📉 İskonto: {ipo_data['discount']}\n"

    return msg

def run_halkarz_pipeline():
    print("--- HALKA ARZ PIPELINE BAŞLADI ---")

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "halkarz.db")
    conn = setup_halkarz_db(db_path)

    print("Halka arz listesi çekiliyor...")
    ipo_list = scrape_halkarz_list()

    if not ipo_list:
        print("UYARI: Halka arz listesi çekilemedi!")
        send_telegram_message("⚠️ *Halka Arz Uyarısı:* Liste verisi çekilemedi.")
        conn.close()
        return

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

    summary = (
        f"📋 *Halka Arz Pipeline Tamamlandı!*\n\n"
        f"📊 *Toplam IPO:* {len(ipo_list)}\n"
        f"🆕 *Yeni:* {new_count}\n"
        f"🔄 *Güncellenen:* {updated_count}\n\n"
        f"Veritabanı: {db_path}"
    )
    send_telegram_message(summary)
    print(f"--- HALKA ARZ PIPELINE BİTTİ ---")
    return new_count

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
        ORDER BY listing_date DESC
        LIMIT 6
    """)
    turkish_months = {
        "Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4,
        "Mayıs": 5, "Haziran": 6, "Temmuz": 7, "Ağustos": 8,
        "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12
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
    run_halkarz_pipeline()

if os.environ.get("HALKARZ_SUMMARY"):
    send_halkarz_summary()
