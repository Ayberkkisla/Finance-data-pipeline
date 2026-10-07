import os

import pytest

import core.scraper as scraper

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


@pytest.fixture(autouse=True)
def no_alerts(monkeypatch):
    monkeypatch.setattr(scraper, "send_error_alert", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def no_delays(monkeypatch):
    monkeypatch.setattr(scraper.time, "sleep", lambda *_: None)


class TestValidateIpo:
    def test_valid(self):
        assert scraper.validate_ipo(
            {"company_name": "Acme A.Ş.", "ipo_date": "1 Ocak 2026", "bist_code": "ACME"}
        ) == []

    def test_empty_company_name(self):
        errors = scraper.validate_ipo({"company_name": "", "ipo_date": "1 Ocak 2026"})
        assert any("Sirket adi" in e for e in errors)

    def test_missing_date(self):
        errors = scraper.validate_ipo({"company_name": "Acme A.Ş.", "ipo_date": ""})
        assert any("Tarih" in e for e in errors)

    def test_invalid_bist_code(self):
        errors = scraper.validate_ipo(
            {"company_name": "Acme A.Ş.", "ipo_date": "1 Ocak 2026", "bist_code": "ac-me!"}
        )
        assert any("BIST kodu" in e for e in errors)


class TestScrapeList:
    def test_parses_fixture(self, monkeypatch):
        monkeypatch.setattr(scraper, "fetch_page", lambda url, retries=3: _fixture("halkarz_list.html"))
        ipos = scraper.scrape_halkarz_list()
        assert len(ipos) == 2
        first = ipos[0]
        assert first["bist_code"] == "NETGL"
        assert "Net Global" in first["company_name"]
        assert first["ipo_date"] == "9-10-11 Eylül 2026"
        assert first["detail_url"].startswith("https://halkarz.com/")

    def test_empty_html_returns_empty(self, monkeypatch):
        monkeypatch.setattr(scraper, "fetch_page", lambda url, retries=3: "<html><body></body></html>")
        assert scraper.scrape_halkarz_list() == []

    def test_fetch_failure_returns_empty(self, monkeypatch):
        monkeypatch.setattr(scraper, "fetch_page", lambda url, retries=3: None)
        assert scraper.scrape_halkarz_list() == []


class TestScrapeDetail:
    def test_parses_fixture(self, monkeypatch):
        monkeypatch.setattr(scraper, "fetch_page", lambda url, retries=3: _fixture("halkarz_detail.html"))
        details = scraper.scrape_halkarz_detail("https://halkarz.com/x/")
        assert details["price"] == "25,52"
        assert details["lot_size"] == "87.500.000"
        assert details["distribution"].startswith("Eşit")
        assert details["market"] == "Yıldız Pazar"
        assert details["listing_date"] == "17 Eylül 2026"
        assert details["spk_bulletin"] == "2026/56"

    def test_unparseable_html_returns_empty(self, monkeypatch):
        monkeypatch.setattr(scraper, "fetch_page", lambda url, retries=3: "<html><body>hiç alan yok</body></html>")
        assert scraper.scrape_halkarz_detail("https://halkarz.com/x/") == {}

    def test_fetch_failure_returns_empty(self, monkeypatch):
        monkeypatch.setattr(scraper, "fetch_page", lambda url, retries=3: None)
        assert scraper.scrape_halkarz_detail("https://halkarz.com/x/") == {}
