# PriceList Auto Updater (Render-ready)

This job writes 80 products to a Google Sheet named `pricelist` (first run) and fetches prices daily from 11 Egyptian stores, then computes the cheapest store per product.

## Files
- `main.py` — the scraper + Google Sheets writer
- `requirements.txt` — dependencies
- `pricelistupdater-0ba613a9eaed.json` — your Google Service Account credentials (keep private)

## Run on Render (recommended)
1. Create a free account at https://render.com
2. Create **New → Cron Job** (recommended) or Web Service.
3. **Environment variable**:
   - `GOOGLE_APPLICATION_CREDENTIALS` = `pricelistupdater-0ba613a9eaed.json`
4. **Build Command**:
   ```
   pip install -r requirements.txt && python -m playwright install --with-deps chromium
   ```
5. **Start Command**:
   ```
   python main.py
   ```
6. Schedule: daily at 09:00 (Africa/Cairo).

## Local Run (optional)
```bash
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

## Notes
- Make sure your Google Sheet `pricelist` is shared with the service account email shown inside the JSON file (Editor permission).
- Prices are stored as numbers (EGP stripped). Cheapest Store/Price are computed per row.
