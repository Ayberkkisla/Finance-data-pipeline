import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

REQUEST_DELAY = 2
MAX_RETRIES = 3
RETRY_DELAY = 5


def fetch_page(url, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            time.sleep(REQUEST_DELAY)
            res = requests.get(url, headers=HEADERS, timeout=30)
            res.raise_for_status()
            return res.text
        except requests.exceptions.Timeout:
            print(f"  [Deneme {attempt + 1}/{retries}] Zaman asimi: {url}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.ConnectionError:
            print(f"  [Deneme {attempt + 1}/{retries}] Baglanti hatasi: {url}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.HTTPError as e:
            print(f"  [Deneme {attempt + 1}/{retries}] HTTP hatasi ({e.response.status_code}): {url}")
            if e.response.status_code == 429:
                wait_time = RETRY_DELAY * (attempt + 2)
                print(f"  Rate limit, {wait_time}s bekleniyor...")
                time.sleep(wait_time)
            elif attempt < retries - 1:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"  [Deneme {attempt + 1}/{retries}] Beklenmeyen hata: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
    return None


def validate_ipo(ipo_data):
    """IPO verisini dogrula. Gerekli alanlar dolu mu kontrol et."""
    errors = []

    if not ipo_data.get("company_name") or len(ipo_data["company_name"].strip()) < 2:
        errors.append("Sirket adi bos veya cok kisa")

    if not ipo_data.get("ipo_date") or len(ipo_data["ipo_date"].strip()) < 3:
        errors.append("Tarih bilgisi eksik")

    if ipo_data.get("bist_code") and not re.match(r"^[A-Z0-9]+$", ipo_data["bist_code"]):
        errors.append(f"Gecersiz BIST kodu: {ipo_data['bist_code']}")

    return errors


def scrape_halkarz_list():
    html = fetch_page("https://halkarz.com/")
    if not html:
        print("HATA: Halkarz ana sayfasi cekilemedi!")
        return []

    soup = BeautifulSoup(html, "html.parser")
    ipos = []

    items = soup.select("ul.halka-arz-list li article.index-list")

    if not items:
        print("UYARI: Hic IPO bulunamadi! HTML yapisi degismis olabilir.")
        print("  Selector: 'ul.halka-arz-list li article.index-list' sonuc dondurmedi.")
        return []

    for item in items:
        try:
            badge_icon = item.select_one(".il-badge i")
            badge_text = ""
            if badge_icon:
                classes = badge_icon.get("class", [])
                if "fa-check-double" in classes:
                    badge_text = "Sonuçlandı"
                elif "fa-check" in classes:
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

            ipo = {
                "bist_code": bist_code,
                "company_name": company_name,
                "ipo_date": ipo_date,
                "status": badge_text,
                "is_new": is_new,
                "detail_url": detail_url,
            }

            validation_errors = validate_ipo(ipo)
            if validation_errors:
                print(f"  UYARI: Dogrulama hatasi ({company_name or 'BILINMEYEN'}): {', '.join(validation_errors)}")
                if not company_name:
                    print("  -> Sirket adi bos, bu IPO atlandi.")
                    continue

            ipos.append(ipo)
        except Exception as e:
            print(f"  Liste parse hatasi: {e}")
            continue

    print(f"  Toplam {len(items)} HTML elementi islen, {len(ipos)} gecerli IPO cikarildi.")
    return ipos


def scrape_halkarz_detail(url):
    html = fetch_page(url)
    if not html:
        print(f"  HATA: Detay sayfasi cekilemedi: {url}")
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
        print(f"  Detail parse hatasi: {e}")

    extracted = len(details)
    if extracted == 0:
        print(f"  UYARI: Hic detay cikarilamadi: {url}")
    else:
        print(f"  {extracted} alan cikarildi.")

    return details
