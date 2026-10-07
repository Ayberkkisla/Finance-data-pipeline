"""Canlı halkarz.com yapısını kontrol eder. HTML şablonu değişirse bu test patlar.

Çalıştırmak için: pytest -m live
Varsayılan koşuda çalışmaz (ağ ve site bağımlılığı vardır).
"""

import pytest

import core.scraper as scraper

pytestmark = pytest.mark.live


def test_halkarz_list_still_scrapeable():
    ipos = scraper.scrape_halkarz_list()
    assert ipos, "halkarz.com listesi parse edilemedi - HTML yapısı değişmiş olabilir"
    for ipo in ipos[:5]:
        assert ipo["company_name"].strip(), "Şirket adı boş - HTML yapısı değişmiş olabilir"
        assert ipo["bist_code"].strip() or ipo["ipo_date"].strip()


def test_halkarz_detail_still_scrapeable():
    ipos = scraper.scrape_halkarz_list()
    if not ipos:
        pytest.skip("Liste çekilemedi")
    url = next((i["detail_url"] for i in ipos if i["detail_url"]), None)
    if not url:
        pytest.skip("Detay URL bulunamadı")
    details = scraper.scrape_halkarz_detail(url)
    assert details, f"Detay sayfasından alan çıkarılamadı: {url} - HTML yapısı değişmiş olabilir"
