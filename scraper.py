import asyncio
import json
import math
import random
import re
import logging
from pathlib import Path
from urllib.parse import urljoin
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

class ProductRunner:
    def __init__(self, category_urls, headless=True, min_delay=2, max_delay=5):
        self.category_urls = category_urls
        self.homepage = "https://www.joueclub.fr/"
        self.headless = headless
        self.per_page = 60
        self.browser = None
        self.context = None
        self.playwright = None
        self.products = []
        self.product_urls = set()
        self.existing_gtins = set()
        self.args = ["--disable-blink-features=AutomationControlled"]
        self.products_file = Path("products.json")
        self.state_file = Path("category_state.json")
        self.min_delay = min_delay
        self.max_delay = max_delay

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless, args=self.args)
        self.context = await self.browser.new_context()

    async def close(self):
        await self.browser.close()
        await self.playwright.stop()

    def load_state(self):
        if not self.state_file.exists():
            with open(self.state_file, "w") as f:
                json.dump({"index": 0}, f)
            return 0
        with open(self.state_file) as f:
            return json.load(f).get("index", 0)

    def save_state(self, index):
        with open(self.state_file, "w") as f:
            json.dump({"index": index}, f)

    def load_products(self):
        if not self.products_file.exists():
            return []
        with open(self.products_file, encoding="utf-8") as f:
            data = json.load(f)
            self.existing_gtins = {p["product_gtin"] for p in data if "product_gtin" in p and p["product_gtin"]}
            return data

    def save_products(self, products):
        with open(self.products_file, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)

    async def get_total_pages(self, url):
        page = await self.context.new_page()
        try:
            await page.goto(url, wait_until="load")
            selector = "span.product-list-count-value"
            await page.wait_for_selector(selector, timeout=30000)
            text = await page.locator(selector).inner_text()
            total_products = int(re.search(r"\d+", text.replace(",", "")).group())
            total_pages = math.ceil(total_products / self.per_page)
            return total_pages
        except:
            return 1
        finally:
            await page.close()

    @staticmethod
    def generate_page_urls(base_url, total_pages):
        return [(page, f"{base_url}?pageNumber-3={page}") for page in range(1, total_pages + 1)]

    async def collect_from_page(self, page_number, url):
        page = await self.context.new_page()
        try:
            await page.goto(url, wait_until="load")
            await page.wait_for_selector("a.product__title-card.product-label", timeout=30000)
            cards = page.locator("a.product__title-card.product-label")
            prices = page.locator("span.price-value")
            count = await cards.count()
            for i in range(count):
                name = (await cards.nth(i).get_attribute("title") or "").strip()
                href = await cards.nth(i).get_attribute("href") or ""
                product_url = urljoin(self.homepage, href)
                gtin_match = re.search(r"\d{13}", product_url)
                gtin = gtin_match.group(0) if gtin_match else ""
                price_text = (await prices.nth(i).inner_text() or "").strip()
                try:
                    price = float(price_text.replace("€", "").replace(",", ".").strip())
                except:
                    price = None
                if not all([name, gtin, price, product_url]):
                    continue
                if gtin in self.existing_gtins:
                    continue
                self.existing_gtins.add(gtin)
                self.product_urls.add(product_url)
                self.products.append({
                    "product_name": name,
                    "product_gtin": gtin,
                    "supplier_price": price,
                    "product_link": product_url
                })
        finally:
            await page.close()
            await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))

    async def run(self):
        index = self.load_state()
        if index >= len(self.category_urls):
            return
        category_url = self.category_urls[index]
        await self.start()
        total_pages = await self.get_total_pages(category_url)
        page_urls = self.generate_page_urls(category_url, total_pages)
        self.load_products()
        for page_number, page_url in page_urls:
            await self.collect_from_page(page_number, page_url)
        await self.close()
        existing = self.load_products()
        existing.extend(self.products)
        self.save_products(existing)
        self.save_state(index + 1)

async def main():

    category_urls = ['https://www.joueclub.fr/nos-univers/peluche.html', 'https://www.joueclub.fr/nos-univers/jeux-d-imitation.html', 'https://www.joueclub.fr/nos-univers/jeux-de-constructions-maquettes.html', 'https://www.joueclub.fr/nos-univers/jeux-educatifs.html', 'https://www.joueclub.fr/nos-univers/activites-creatives-et-manuelles.html', 'https://www.joueclub.fr/nos-univers/jouets-en-bois.html', 'https://www.joueclub.fr/nos-univers/poupees.html', 'https://www.joueclub.fr/nos-univers/jeux-de-societe.html', 'https://www.joueclub.fr/nos-univers/musiques-sons-images.html', 'https://www.joueclub.fr/nos-univers/puzzle.html', 'https://www.joueclub.fr/nos-univers/figurines.html', 'https://www.joueclub.fr/nos-univers/jeux-exterieurs-et-sports.html', 'https://www.joueclub.fr/nos-univers/chambre-enfants.html', 'https://www.joueclub.fr/nos-univers/fetes-et-anniversaires.html', 'https://www.joueclub.fr/nos-univers/piles-chargeurs-batteries.html', 'https://www.joueclub.fr/nos-univers/comme-a-l-ecole-rentree-scolaire.html', 'https://www.joueclub.fr/nos-univers/petits-cadeaux.html', 'https://www.joueclub.fr/nos-univers/bagagerie.html', 'https://www.joueclub.fr/nos-univers/jo-paris-2024.html', 'https://www.joueclub.fr/nos-univers/vehicules-garages.html']

    runner = ProductRunner(
        category_urls,
        headless=True,
        min_delay=2,
        max_delay=5
    )

    await runner.run()


asyncio.run(main())
