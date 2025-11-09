# -*- coding: utf-8 -*-
"""
PriceList Auto Updater (Render-ready)
------------------------------------
- On first run: writes 80 products to Google Sheet 'pricelist' (one column: Product)
  (20 TVs + 40 Phones + 20 Air Conditioners)
- Then fetches prices from 11 Egyptian stores for each product using Playwright.
- Writes prices as pure numbers (EGP stripped).
- Computes "Cheapest Store" and "Cheapest Price" per row.

Environment:
- GOOGLE_APPLICATION_CREDENTIALS must point to the JSON file path (in this repo directory).

Render notes:
- Use a Cron Job (recommended) or a Web Service if you want to trigger on-demand.
- Build Command:
    pip install -r requirements.txt && python -m playwright install --with-deps chromium
- Start Command:
    python main.py

Local run (optional):
    pip install -r requirements.txt
    python -m playwright install chromium
    python main.py
"""
import os
import re
import asyncio
import traceback
from typing import List, Dict, Optional

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

# Playwright
from playwright.async_api import async_playwright

SHEET_NAME = "pricelist"

STORE_COLUMNS = [
    "Jumia",
    "2B",
    "BTECH",
    "Rizkalla",
    "Carrefour",
    "Vodafone Shop",
    "Etisalat",
    "Raneen",
    "Raya Shop",
    "Shaheen Center",
    "Noon",
]
SUMMARY_COLUMNS = ["Cheapest Store", "Cheapest Price"]
ALL_COLUMNS = ["Product"] + STORE_COLUMNS + SUMMARY_COLUMNS

# ---------- Products ----------
def default_tv_products() -> List[str]:
    return [
        "Samsung 43 inch Crystal UHD 4K TV",
        "Samsung 50 inch Crystal UHD 4K TV",
        "Samsung 55 inch Crystal UHD 4K TV",
        "Samsung 65 inch Crystal UHD 4K TV",
        "Samsung 75 inch Crystal UHD 4K TV",
        "Samsung 43 inch Smart TV",
        "Samsung 55 inch Smart TV",
        "Samsung 65 inch QLED 4K TV",
        "Samsung 55 inch QLED 4K TV",
        "Samsung 50 inch QLED 4K TV",
        "LG 43 inch 4K Smart TV",
        "LG 50 inch 4K Smart TV",
        "LG 55 inch 4K Smart TV",
        "LG 65 inch 4K Smart TV",
        "LG 75 inch 4K Smart TV",
        "LG 55 inch OLED Smart TV",
        "LG 65 inch OLED Smart TV",
        "LG 43 inch Smart TV",
        "LG 55 inch NanoCell 4K TV",
        "LG 65 inch NanoCell 4K TV",
    ]

def default_phone_products() -> List[str]:
    return [
        "Samsung Galaxy A15 6GB 128GB",
        "Samsung Galaxy A25 8GB 128GB",
        "Samsung Galaxy A35 8GB 256GB",
        "Samsung Galaxy A55 8GB 256GB",
        "Samsung Galaxy S23 FE 8GB 256GB",
        "Samsung Galaxy A05s 6GB 128GB",
        "Samsung Galaxy A14 6GB 128GB",
        "Samsung Galaxy M14 6GB 128GB",
        "Apple iPhone 13 128GB",
        "Apple iPhone 14 128GB",
        "Apple iPhone 14 Plus 128GB",
        "Apple iPhone 15 128GB",
        "Apple iPhone 15 Plus 128GB",
        "Apple iPhone SE 64GB",
        "Xiaomi Redmi Note 13 8GB 256GB",
        "Xiaomi Redmi Note 13 6GB 128GB",
        "Xiaomi Redmi Note 13 Pro 8GB 256GB",
        "POCO X6 8GB 256GB",
        "POCO X6 Pro 12GB 256GB",
        "Xiaomi Redmi 13C 4GB 128GB",
        "OPPO Reno 11 8GB 256GB",
        "OPPO Reno 11F 8GB 256GB",
        "OPPO A78 8GB 256GB",
        "OPPO A79 8GB 128GB",
        "Realme 12 Pro 8GB 256GB",
        "Realme 12+ 8GB 256GB",
        "Realme C67 6GB 128GB",
        "Samsung Galaxy A24 8GB 128GB",
        "Samsung Galaxy A34 8GB 128GB",
        "Samsung Galaxy A54 8GB 256GB",
        "Xiaomi Redmi Note 12 8GB 128GB",
        "Xiaomi Redmi Note 12S 8GB 256GB",
        "Xiaomi Redmi Note 11 6GB 128GB",
        "POCO M6 Pro 8GB 256GB",
        "POCO C65 6GB 128GB",
        "OPPO A58 8GB 128GB",
        "Realme C53 6GB 128GB",
        "Realme Narzo 70 8GB 128GB",
        "Samsung Galaxy A15 4GB 128GB",
        "Xiaomi Redmi Note 13 Pro+ 12GB 512GB",
    ]

def default_ac_products() -> List[str]:
    return [
        "Carrier Split Air Conditioner 1.5 HP Cool",
        "Carrier Split Air Conditioner 2.25 HP Cool",
        "Carrier Split Air Conditioner 3 HP Cool",
        "Carrier Optimax Inverter 1.5 HP Cool",
        "Sharp Split Air Conditioner 1.5 HP Cool",
        "Sharp Split Air Conditioner 2.25 HP Cool",
        "Sharp Split Air Conditioner 3 HP Cool",
        "Unionaire Split Air Conditioner 1.5 HP Cool",
        "Unionaire Split Air Conditioner 2.25 HP Cool",
        "LG Dual Inverter 1.5 HP Cool",
        "LG Dual Inverter 2.25 HP Cool",
        "Tornado Split Air Conditioner 1.5 HP Cool",
        "Tornado Split Air Conditioner 2.25 HP Cool",
        "Fresh Split Air Conditioner 1.5 HP Cool",
        "Fresh Split Air Conditioner 2.25 HP Cool",
        "Midea Split Air Conditioner 1.5 HP Cool",
        "Midea Split Air Conditioner 2.25 HP Cool",
        "Carrier Optimum Inverter 1.5 HP Cool",
        "Sharp Plasmacluster 1.5 HP Cool",
        "Unionaire Artify 1.5 HP Cool",
    ]

def default_products() -> List[str]:
    return default_tv_products() + default_phone_products() + default_ac_products()

SPACE_VARIANTS = ["\u00a0", "\u200f", "\u200e", "\u202f"]

def parse_price_number(text: str) -> Optional[float]:
    if not text:
        return None
    t = text
    for s in SPACE_VARIANTS:
        t = t.replace(s, " ")
    t = t.replace(",", "")
    t = re.sub(r"(EGP|ج\.م|جنيه|ريال|درهم|SAR|AED|USD|EGP\.)", "", t, flags=re.I)
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    try:
        return float(m.group(1)) if m else None
    except:
        return None

class BaseAdapter:
    seller: str = ""
    search_url: str = ""
    def build_query_url(self, q: str) -> str:
        return self.search_url + q.replace(" ", "+")
    async def extract_price_candidates(self, page):
        return []
    async def search_price(self, page, query: str) -> Optional[float]:
        try:
            url = self.build_query_url(query)
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(800)
            texts = await self.extract_price_candidates(page)
            prices = [parse_price_number(t) for t in texts]
            prices = [p for p in prices if p and p > 0]
            return min(prices) if prices else None
        except Exception:
            return None

class JumiaAdapter(BaseAdapter):
    seller = "Jumia"
    search_url = "https://www.jumia.com.eg/catalog/?q="
    async def extract_price_candidates(self, page):
        locs = await page.locator("article.prd div.prc").all()
        return [await l.text_content() or "" for l in locs[:30]]

class TwoBAdapter(BaseAdapter):
    seller = "2B"
    search_url = "https://2b.com.eg/en/search?query="
    async def extract_price_candidates(self, page):
        locs = await page.locator(".price, .price-wrapper .price").all()
        return [await l.text_content() or "" for l in locs[:30]]

class BtechAdapter(BaseAdapter):
    seller = "BTECH"
    search_url = "https://btech.com/en/search?q="
    async def extract_price_candidates(self, page):
        locs = await page.locator("[data-cy='product-price'], .product-card [class*=price]").all()
        return [await l.text_content() or "" for l in locs[:30]]

class RizkallaAdapter(BaseAdapter):
    seller = "Rizkalla"
    search_url = "https://rizkalla.com/search?q="
    async def extract_price_candidates(self, page):
        locs = await page.locator(".price, .card-product .price, .product-price").all()
        return [await l.text_content() or "" for l in locs[:30]]

class CarrefourAdapter(BaseAdapter):
    seller = "Carrefour"
    search_url = "https://www.carrefouregypt.com/mafegy/en/search?q="
    async def extract_price_candidates(self, page):
        locs = await page.locator("[data-test='product-price'], .product-price, .price").all()
        return [await l.text_content() or "" for l in locs[:30]]

class VodafoneAdapter(BaseAdapter):
    seller = "Vodafone Shop"
    search_url = "https://eshop.vodafone.com.eg/shop/search?q="
    async def extract_price_candidates(self, page):
        locs = await page.locator(".product-price, .price, [class*=price]").all()
        return [await l.text_content() or "" for l in locs[:30]]

class EtisalatAdapter(BaseAdapter):
    seller = "Etisalat"
    search_url = "https://www.etisalat.eg/etisalat/portal/Search?text="
    async def extract_price_candidates(self, page):
        locs = await page.locator(".price, .prd-price, [class*=price]").all()
        return [await l.text_content() or "" for l in locs[:30]]

class RaneenAdapter(BaseAdapter):
    seller = "Raneen"
    search_url = "https://raneen.com/en/catalogsearch/result/?q="
    async def extract_price_candidates(self, page):
        locs = await page.locator(".price, .special-price .price, .old-price .price").all()
        return [await l.text_content() or "" for l in locs[:30]]

class RayaAdapter(BaseAdapter):
    seller = "Raya Shop"
    search_url = "https://www.rayashop.com/search?q="
    async def extract_price_candidates(self, page):
        locs = await page.locator(".price, .product-price, [class*=price]").all()
        return [await l.text_content() or "" for l in locs[:30]]

class ShaheenAdapter(BaseAdapter):
    seller = "Shaheen Center"
    search_url = "https://shaheen.center/en/search?q="
    async def extract_price_candidates(self, page):
        locs = await page.locator(".price, .woocommerce-Price-amount, [class*=price]").all()
        return [await l.text_content() or "" for l in locs[:30]]

class NoonAdapter(BaseAdapter):
    seller = "Noon"
    search_url = "https://www.noon.com/egypt-en/search?q="
    async def extract_price_candidates(self, page):
        locs = await page.locator("[data-qa='product-price'], .price, [class*=price]").all()
        return [await l.text_content() or "" for l in locs[:30]]

ADAPTERS = [
    JumiaAdapter(),
    TwoBAdapter(),
    BtechAdapter(),
    RizkallaAdapter(),
    CarrefourAdapter(),
    VodafoneAdapter(),
    EtisalatAdapter(),
    RaneenAdapter(),
    RayaAdapter(),
    ShaheenAdapter(),
    NoonAdapter(),
]

def get_sheet_client():
    json_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not json_path or not os.path.exists(json_path):
        raise RuntimeError(
            "GOOGLE_APPLICATION_CREDENTIALS not set or file not found. "
            "Set it to the credentials JSON path (e.g., pricelistupdater-xxxx.json)."
        )
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(json_path, scopes=scope)
    gc = gspread.authorize(creds)
    return gc

def open_or_create_pricelist(gc):
    try:
        sh = gc.open(SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sh = gc.create(SHEET_NAME)
    ws = sh.sheet1
    headers = ws.row_values(1)
    if headers != ALL_COLUMNS:
        ws.clear()
        ws.append_row(ALL_COLUMNS)
    return sh, ws

def ensure_products(ws):
    existing = ws.col_values(1)[1:]
    if existing:
        return existing
    products = default_products()
    rows = [[p] + [""] * (len(ALL_COLUMNS) - 1) for p in products]
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    return products

def write_prices_block(ws, row_idx: int, prices_map: Dict[str, Optional[float]]):
    values = []
    for store in STORE_COLUMNS:
        val = prices_map.get(store)
        values.append("" if val is None else val)
    cheapest_store, cheapest_price = "", ""
    numeric_prices = [(s, prices_map.get(s)) for s in STORE_COLUMNS if prices_map.get(s) is not None]
    if numeric_prices:
        s, p = min(numeric_prices, key=lambda kv: kv[1])
        cheapest_store, cheapest_price = s, p
    start_col = 2
    end_col = 1 + len(STORE_COLUMNS) + len(SUMMARY_COLUMNS)
    rng = gspread.utils.rowcol_to_a1(row_idx, start_col) + ":" + gspread.utils.rowcol_to_a1(row_idx, end_col)
    ws.update(rng, [values + [cheapest_store, cheapest_price]], value_input_option="USER_ENTERED")

async def fetch_prices_for_product(context, product: str) -> Dict[str, Optional[float]]:
    prices = {}
    page = await context.new_page()
    try:
        for ad in ADAPTERS:
            price = await ad.search_price(page, product)
            prices[ad.seller] = price
            await page.wait_for_timeout(300)
    finally:
        await page.close()
    return prices

async def update_all():
    gc = get_sheet_client()
    sh, ws = open_or_create_pricelist(gc)
    products = ensure_products(ws)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        for idx, product in enumerate(products, start=2):
            print(f"[{idx-1}/{len(products)}] Fetching: {product}")
            try:
                price_map = await fetch_prices_for_product(context, product)
                write_prices_block(ws, idx, price_map)
            except Exception as e:
                print(f"[ERROR] {product}: {e}")
        await context.close()
        await browser.close()
    print("✅ Sheet updated successfully.")

def main():
    # Ensure env var points to the local JSON path by default
    # (Render Cron Job: set the env var in the service settings)
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        # Fallback to local file in repo
        if os.path.exists("pricelistupdater-0ba613a9eaed.json"):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "pricelistupdater-0ba613a9eaed.json"
    asyncio.run(update_all())

if __name__ == "__main__":
    main()
