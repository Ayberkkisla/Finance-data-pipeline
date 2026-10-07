# Finance Data Pipeline

Borsa İstanbul (BIST) ve halka arz verilerini otomatik olarak toplayan, SQLite veritabanına kaydeden ve Telegram üzerinden bildiren bir veri pipeline'ı.

## Özellikler

- **Halka Arz Takibi**: [halkarz.com](https://halkarz.com/) sitesinden halka arz listesi ve detay bilgilerini (fiyat, lot, dağıtım yöntemi, aracı kurum, pazar, halka arz büyüklüğü, BIST işlem tarihi, iskonto, halka açıklık, SPK bülteni) çeker.
- **Yeni Halka Arz Bildirimi**: Yeni bir IPO tespit edildiğinde Telegram'a bildirim gönderir.
- **Günlük Halka Arz Özeti**: Son 6 halka arzın günlük fiyat değişimini yfinance ile çekip Telegram'a gönderir.
- **Piyasa Verisi**: USD/TRY kuru ve BIST 100 endeksini günlük olarak `finance_data.db`'ye kaydeder.
- **Hata Uyarıları**: Scraping hatası veya veri çekilememesi durumunda Telegram'a hata bildirimi gönderir.
- **Zamanlanmış Çalışma**: GitHub Actions ile hafta içi her gün otomatik çalışır ve veritabanını güncelleyerek commit'ler.

## Proje Yapısı

```
Finance-data-pipeline/
├── finance.py              # Ana pipeline betiği
├── core/
│   ├── scraper.py          # halkarz.com scraper'ı (retry, rate-limit, doğrulama)
│   ├── db_manager.py       # SQLite tablo kurulumu ve güncelleme
│   └── notifier.py         # Telegram mesaj gönderimi ve IPO mesaj formatı
├── .github/workflows/
│   ├── scheduler.yml       # BIST & Dolar/TL günlük piyasa verisi (Pzt-Cum 15:30 UTC)
│   └── halkarz.yml         # Halka arz günlük özeti (her gün 15:00 UTC)
├── halkarz.db              # Halka arz veritabanı
├── finance_data.db         # Piyasa verisi veritabanı (gitignore'da)
└── requirements.txt
```

## Kurulum

```bash
git clone https://github.com/Ayberkkisla/Finance-data-pipeline.git
cd Finance-data-pipeline
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Yapılandırma

Telegram bildirimleri için ortam değişkenlerini ayarlayın:

```bash
export TELEGRAM_TOKEN="bot_token"
export CHAT_ID="chat_id"
```

GitHub Actions için bu değerleri repo ayarlarından **Secrets** olarak ekleyin: `TELEGRAM_TOKEN`, `CHAT_ID`.

## Kullanım

```bash
# Halka arz pipeline'ı
RUN_HALKARZ=1 python finance.py

# Halka arz + günlük özet
RUN_HALKARZ=1 HALKARZ_SUMMARY=1 python finance.py

# Piyasa verisi (BIST100, USD/TRY)
RUN_MARKET_DATA=1 python finance.py
```

## Veritabanı Şemaları

**halkarz_ipos** (`halkarz.db`): `bist_code`, `company_name`, `ipo_date`, `status`, `price`, `lot_size`, `distribution`, `broker`, `market`, `ipo_size`, `listing_date`, `discount`, `free_float`, `spk_bulletin`, `detail_url`, `first_seen`, `last_updated` — `UNIQUE(company_name, ipo_date)`

**daily_market_data** (`finance_data.db`): `date` (PK), `bist100`, `usd_try`

## Zamanlayıcı

| Workflow | Zamanlama | Ne yapar |
|---|---|---|
| `scheduler.yml` | Hafta içi 15:30 UTC | BIST100 & USD/TRY çeker, DB'ye yazar, Telegram'a bildirir |
| `halkarz.yml` | Her gün 15:00 UTC | Halka arz listesini günceller, özet gönderir, `halkarz.db`'yi commit'ler |
