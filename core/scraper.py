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
