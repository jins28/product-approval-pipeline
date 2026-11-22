"""
Product scraper with two sources:
- "supplier":      our fictional supplier website (plain HTML pages, default)
- "jonathanadler": a real Shopify shop (JSON feed + product pages, local tests only)

What it does, step by step
1. Checks robots.txt: if the site does not allow a URL, we do not fetch it.
2. Gets the product list from Shopify's public JSON feed
   /collections/<collection>/products.json  (title, price, images, description).
   Why JSON and not HTML? The collection page builds its product grid with
   JavaScript, so a simple HTML scraper would see no products. The JSON feed
   is the same data in a clean, stable format.
3. Opens each product page (HTML) and reads three sections that are not in
   the JSON: "Dimensions", "Material & Construction", "Features & Feel".
4. Downloads the first few product images into a local folder
   (data/media). The shop serves that folder at /media/..., so the website
   shows our local copies.
5. Returns one clean dict per product. Problems with one product are
   collected in "errors" and do not stop the others.

Politeness rules (important when scraping a real site):
- a clear User-Agent, a pause between requests, robots.txt respected,
- a small limit per run, and images are only downloaded once.

Run it from the command line:
    python scraper.py --limit 3
    python scraper.py --collection furniture-by-category-chairs --limit 3
or call it through the API in app.py (that is what n8n does).

Scraped texts and images belong to the website owner. They are saved in
data/, which is in .gitignore and is never committed.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse, parse_qsl, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup, Tag

# ---------------------------------------------------------------------------
# Settings (environment variables, with safe defaults)
# ---------------------------------------------------------------------------

# Which source to scrape by default: "supplier" (our own demo supplier website)
# or "jonathanadler" (a real Shopify shop, for local tests only)
SOURCE = os.getenv("SCRAPER_SOURCE", "supplier")
SOURCES = ("supplier", "jonathanadler")
SUPPLIER_BASE_URL = os.getenv("SUPPLIER_BASE_URL", "http://supplier").rstrip("/")
BASE_URL = os.getenv("SCRAPER_BASE_URL", "https://jonathanadler.com").rstrip("/")
COLLECTION = os.getenv("SCRAPER_COLLECTION", "furniture-by-category-sofas")
MEDIA_DIR = Path(os.getenv("SCRAPER_MEDIA_DIR", "data/media"))
DELAY_SECONDS = float(os.getenv("SCRAPER_DELAY_SECONDS", "2"))
# How often to retry when the site answers 429 (too many requests) or 503
MAX_RETRIES = int(os.getenv("SCRAPER_MAX_RETRIES", "3"))
# Never wait longer than this for one retry (seconds)
MAX_RETRY_WAIT = float(os.getenv("SCRAPER_MAX_RETRY_WAIT", "60"))
MAX_IMAGES = int(os.getenv("SCRAPER_MAX_IMAGES", "4"))
IMAGE_WIDTH = int(os.getenv("SCRAPER_IMAGE_WIDTH", "1200"))
USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "PortfolioDemoScraper/1.0 (personal learning project; low request rate)",
)

# Sections we read from the product page: our field name -> heading on the page
SECTIONS = {
    "dimensions": "dimensions",
    "material_construction": "material & construction",
    "features_feel": "features & feel",
}


# ---------------------------------------------------------------------------
# A polite HTTP client
# ---------------------------------------------------------------------------

class PoliteClient:
    """requests.Session + robots.txt check + a pause between requests."""

    def __init__(self, base_url: str = BASE_URL, delay: float = DELAY_SECONDS,
                 session: requests.Session | None = None):
        self.base_url = base_url
        self.delay = delay
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_request = 0.0
        self.robots = self._load_robots()

    def _load_robots(self) -> RobotFileParser:
        parser = RobotFileParser()
        try:
            response = self.session.get(f"{self.base_url}/robots.txt", timeout=15)
            # No robots.txt (404) means "everything allowed"
            parser.parse(response.text.splitlines() if response.ok else [])
        except requests.RequestException:
            parser.parse([])
        return parser

    def get(self, url: str, **kwargs) -> requests.Response:
        if not self.robots.can_fetch(USER_AGENT, url):
            raise PermissionError(f"robots.txt does not allow fetching {url}")

        for attempt in range(MAX_RETRIES + 1):
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
            response = self.session.get(url, timeout=30, **kwargs)

            # 429 = "too many requests", 503 = "busy": the site asks us to slow down.
            # We respect that: wait (as long as the site says, if it says) and retry.
            if response.status_code in (429, 503) and attempt < MAX_RETRIES:
                time.sleep(self._retry_wait(response, attempt))
                continue
            if response.status_code == 429:
                raise RuntimeError(
                    f"The website is rate-limiting us (429 Too Many Requests) for {url}. "
                    "Wait a while (minutes up to an hour) before trying again."
                )
            response.raise_for_status()  # other 4xx/5xx -> exception with a clear message
            # If the server does not say which text encoding it uses, requests
            # assumes ISO-8859-1 and "–" turns into "â€“". Then we let it guess
            # from the content instead (our pages are UTF-8).
            headers = getattr(response, "headers", {}) or {}
            if "charset" not in headers.get("Content-Type", "").lower() and hasattr(response, "apparent_encoding"):
                response.encoding = response.apparent_encoding or "utf-8"
            return response
        raise RuntimeError(f"Giving up on {url}")  # not reached, keeps type checkers happy

    @staticmethod
    def _retry_wait(response: requests.Response, attempt: int) -> float:
        """Seconds to wait: the site's Retry-After header if present, else 10s, 20s, 40s ..."""
        header = getattr(response, "headers", {}).get("Retry-After", "")
        try:
            seconds = float(header)
        except ValueError:
            seconds = 10 * (2 ** attempt)
        return min(max(seconds, 1), MAX_RETRY_WAIT)


# ---------------------------------------------------------------------------
# Small text helpers
# ---------------------------------------------------------------------------

def normalize_heading(text: str) -> str:
    """'Material &amp; Construction +' -> 'material & construction'"""
    text = html_lib.unescape(text or "").lower()
    text = re.sub(r"[^a-z&]+", " ", text)
    return " ".join(text.split())


def html_to_text(value: str) -> str:
    """HTML -> plain text with line breaks, no tags, no empty lines."""
    soup = BeautifulSoup(value or "", "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    lines = [line.strip() for line in soup.get_text("\n").splitlines()]
    return "\n".join(line for line in lines if line)


def collection_handle(value: str) -> str:
    """
    Accept a handle or a full link and return the handle:
    'https://site.com/collections/furniture-by-category-chairs?srsltid=...'
        -> 'furniture-by-category-chairs'
    (?srsltid=... is only a Google tracking code, we drop it)
    """
    value = (value or "").strip()
    match = re.search(r"/collections/([^/?#]+)", value)
    handle = match.group(1) if match else value.strip("/")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", handle):
        raise ValueError(f"Not a valid collection: {value!r}")
    return handle


def clean_price(value) -> str:
    """'5750.00' / 5750 / '5,750.00' -> '5750.00'"""
    number = float(str(value).replace(",", ""))
    return f"{number:.2f}"


# ---------------------------------------------------------------------------
# Step 2: product list from the JSON feed
# ---------------------------------------------------------------------------

def fetch_product_list(client: PoliteClient, limit: int, collection: str = COLLECTION) -> list[dict]:
    products: list[dict] = []
    page = 1
    # Ask only for as many products as we need (Shopify allows max. 250 per page)
    page_size = min(max(limit, 1), 250)
    while len(products) < limit:
        url = f"{client.base_url}/collections/{collection}/products.json?limit={page_size}&page={page}"
        response = client.get(url)
        try:
            batch = response.json().get("products", [])
        except ValueError as err:
            raise RuntimeError(f"{url} did not return JSON. Is this a Shopify collection?") from err
        if not batch:
            break  # no more pages
        products.extend(batch)
        if len(batch) < page_size:
            break  # last page reached, no need to ask again
        page += 1
    return products[:limit]


# ---------------------------------------------------------------------------
# Step 3: read the sections from the product page
# ---------------------------------------------------------------------------

def _is_section_heading(tag: Tag) -> bool:
    known = set(SECTIONS.values())
    return normalize_heading(tag.get_text(" ", strip=True)) in known


def _content_after_heading(heading: Tag) -> str:
    """
    Product pages show sections in different ways. We try the common ones:
    A) <details><summary>Dimensions</summary> ...content... </details>   (accordion)
    B) <button aria-controls="panel-id">Dimensions</button> <div id="panel-id">...</div>
    C) <h2>Dimensions</h2> <p>...</p> <ul>...</ul> <h2>Next section</h2>
    """
    # A) accordion with <details>/<summary>
    summary = heading if heading.name == "summary" else heading.find_parent("summary")
    if summary is not None and summary.parent is not None and summary.parent.name == "details":
        parts = [c for c in summary.parent.children if c is not summary]
        return html_to_text("".join(str(p) for p in parts))

    # B) button that controls a panel by id
    button = heading if heading.name == "button" else heading.find_parent("button")
    if button is not None and button.get("aria-controls"):
        root = heading
        while root.parent is not None:  # go up to the whole document
            root = root.parent
        target = root.find(id=button["aria-controls"])
        if target is not None:
            return html_to_text(str(target))

    # C) heading followed by siblings until the next heading
    start = heading
    # if the heading text sits in a small wrapper without siblings, step up once
    if not any(isinstance(s, Tag) for s in start.next_siblings) and start.parent is not None:
        start = start.parent
    collected = []
    for sibling in start.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.name in {"h1", "h2", "h3", "h4", "summary"} or _is_section_heading(sibling):
            break
        collected.append(str(sibling))
    return html_to_text("".join(collected))


def parse_sections(page_html: str) -> dict[str, str]:
    soup = BeautifulSoup(page_html, "html.parser")
    for junk in soup(["script", "style", "noscript", "svg"]):
        junk.decompose()

    result = {field: "" for field in SECTIONS}
    candidates = soup.find_all(["summary", "button", "h2", "h3", "h4", "h5", "strong", "span", "p", "div"])
    for field, heading_text in SECTIONS.items():
        for tag in candidates:
            # the tag's OWN text must be exactly the heading (not a big container)
            if normalize_heading(tag.get_text(" ", strip=True)) != heading_text:
                continue
            content = _content_after_heading(tag)
            if content:
                result[field] = content
                break
    return result


def description_without_sections(body_html: str) -> str:
    """The description, cut off where one of the sections starts (if it is inside)."""
    text = html_to_text(body_html)
    lines = []
    for line in text.splitlines():
        if normalize_heading(line) in SECTIONS.values():
            break
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 4: images
# ---------------------------------------------------------------------------

def sized_image_url(src: str, width: int = IMAGE_WIDTH) -> str:
    """Shopify CDN images can be resized with ?width=... -> smaller downloads."""
    if src.startswith("//"):
        src = "https:" + src
    parts = urlparse(src)
    query = dict(parse_qsl(parts.query))
    query["width"] = str(width)
    return urlunparse(parts._replace(query=urlencode(query)))


def save_images(client: PoliteClient, slug: str, images: list[tuple[str, str]],
                media_dir: Path) -> list[dict]:
    """
    Download (url, alt) pairs to media_dir as <slug>-1.jpg, <slug>-2.jpg, ...
    Returns paths the shop can serve: /media/<file>. Each file is fetched only once.
    """
    media_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for index, (url, alt) in enumerate(images[:MAX_IMAGES], start=1):
        extension = Path(urlparse(url).path).suffix.lower() or ".jpg"
        filename = f"{slug}-{index}{extension}"
        target = media_dir / filename
        if not target.exists():  # download only once
            target.write_bytes(client.get(url).content)
        saved.append({"src": f"/media/{filename}", "alt": alt})
    return saved


def download_images(client: PoliteClient, product: dict, media_dir: Path) -> list[dict]:
    """Shopify: images come from the JSON feed; we ask the CDN for a smaller size."""
    images = sorted(product.get("images", []), key=lambda img: img.get("position", 0))
    pairs = [(sized_image_url(img["src"]), img.get("alt") or product["title"]) for img in images]
    return save_images(client, product["handle"], pairs, media_dir)


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------

def build_product(client: PoliteClient, raw: dict, with_images: bool, media_dir: Path,
                  collection: str = COLLECTION) -> dict:
    url = f"{client.base_url}/products/{raw['handle']}"
    variant = (raw.get("variants") or [{}])[0]
    sections = parse_sections(client.get(url).text)
    return {
        # Stable id: the shop's SKU if it has one, otherwise its product id
        "id": f"JA-{variant.get('sku') or raw['id']}",
        "title": raw["title"],
        # e.g. "Sofa" or "Chair"; falls back to the collection name
        "product_type": raw.get("product_type") or collection.split("-")[-1].rstrip("s").title(),
        "collection": collection,
        "price": clean_price(variant.get("price", "0")),
        "currency": "USD",
        "url": url,                               # duplicate check in the sheet uses this
        "images": download_images(client, raw, media_dir) if with_images else [],
        "description_en": description_without_sections(raw.get("body_html", "")),
        **sections,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# Source 2: our demo supplier website (plain HTML, no JSON feed)
# ---------------------------------------------------------------------------

def supplier_product_links(client: PoliteClient, category: str | None) -> list[str]:
    """Read the catalogue page and collect the links to all product pages."""
    soup = BeautifulSoup(client.get(f"{client.base_url}/index.html").text, "html.parser")
    links = []
    for card in soup.select("a.product-card[href]"):
        if category and card.get("data-category") != category:
            continue
        links.append(urljoin(f"{client.base_url}/", card["href"]))
    return links


def build_supplier_product(client: PoliteClient, url: str, with_images: bool, media_dir: Path) -> dict:
    page_html = client.get(url).text
    soup = BeautifulSoup(page_html, "html.parser")
    title = soup.select_one(".product-title").get_text(strip=True)
    sku = soup.select_one("[data-sku]").get_text(strip=True)
    price = soup.select_one("[data-price]")["data-price"]
    wrapper = soup.select_one("[data-category]")
    slug = Path(urlparse(url).path).stem
    images = [(urljoin(url, img["src"]), img.get("alt") or title) for img in soup.select("img.gallery-image")]
    return {
        "id": sku,
        "title": title,
        "product_type": (wrapper.get("data-category", "") if wrapper else "").title(),
        "collection": "supplier",
        "price": clean_price(price),
        "currency": "EUR",
        "url": url,
        "images": save_images(client, slug, images, media_dir) if with_images else [],
        "description_en": html_to_text(str(soup.select_one(".description") or "")),
        **parse_sections(page_html),
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def scrape_supplier(limit: int, with_images: bool, client: PoliteClient, media_dir: Path,
                    category: str | None = None) -> dict:
    products, errors = [], []
    for url in supplier_product_links(client, category)[:limit]:
        try:
            products.append(build_supplier_product(client, url, with_images, media_dir))
        except Exception as err:  # one broken page must not stop the run
            errors.append({"url": url, "error": str(err)})
    return {"source": f"{client.base_url}/", "count": len(products), "products": products, "errors": errors}


# ---------------------------------------------------------------------------
# Entry point: choose the source
# ---------------------------------------------------------------------------

def scrape(limit: int = 5, with_images: bool = True, client: PoliteClient | None = None,
           media_dir: Path = MEDIA_DIR, collection: str = COLLECTION, source: str | None = None) -> dict:
    """
    source="supplier"      -> our demo supplier website (default)
    source="jonathanadler" -> Shopify JSON feed + product pages
    For the supplier, "collection" can be "sofa" or "chair" to filter (anything else = all).
    """
    source = source or SOURCE
    if source not in SOURCES:
        raise ValueError(f"Unknown source {source!r}. Use one of: {', '.join(SOURCES)}")
    if source == "supplier":
        client = client or PoliteClient(base_url=SUPPLIER_BASE_URL)
        category = collection if collection in ("sofa", "chair") else None
        return scrape_supplier(limit, with_images, client, media_dir, category)

    collection = collection_handle(collection)
    client = client or PoliteClient()
    products, errors = [], []
    for raw in fetch_product_list(client, limit, collection):
        try:
            products.append(build_product(client, raw, with_images, media_dir, collection))
        except Exception as err:  # one broken product must not stop the run
            errors.append({"url": f"{client.base_url}/products/{raw.get('handle')}", "error": str(err)})
    return {
        "source": f"{client.base_url}/collections/{collection}",
        "count": len(products),
        "products": products,
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape products from a Shopify collection.")
    parser.add_argument("--source", default=SOURCE, choices=SOURCES,
                        help="supplier (demo website, default) or jonathanadler")
    parser.add_argument("--collection", default=COLLECTION,
                        help="collection handle or full collection link (default: sofas)")
    parser.add_argument("--limit", type=int, default=3, help="max. number of products (default 3)")
    parser.add_argument("--no-images", action="store_true", help="do not download images")
    parser.add_argument("--output", help="also save the result to this JSON file")
    args = parser.parse_args()

    result = scrape(limit=args.limit, with_images=not args.no_images,
                    collection=args.collection, source=args.source)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(f"\n{result['count']} products scraped, {len(result['errors'])} errors.")
