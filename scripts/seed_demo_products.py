"""
Upload 3 invented demo sofas to the mock shop, so the website has
something to show before the real pipeline exists.

Usage (from the project folder, while the shop is running):
    python scripts/seed_demo_products.py

It reads SHOP_API_KEY from the .env file and only uses Python's standard
library, so nothing needs to be installed.
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

SHOP_URL = os.getenv("SHOP_URL", "http://localhost:8001")
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def read_api_key() -> str:
    """Read SHOP_API_KEY from the environment or from the .env file."""
    if os.getenv("SHOP_API_KEY"):
        return os.environ["SHOP_API_KEY"]
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("SHOP_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("SHOP_API_KEY not found in .env")


# Invented products: names, texts and pictures are our own.
DEMO_SOFAS = [
    {
        "title": "Sofa „Wolke“ 3-Sitzer",
        "price": "1890.00", "sku": "DEMO-SOFA-001",
        "body_html": "<p>Ein weich geschwungenes Sofa mit tiefer Sitzfläche – gemacht für lange Abende.</p>"
                     "<p>Die runden Armlehnen und der sandfarbene Bezug passen in moderne wie klassische Räume.</p>",
        "dimensions": "Breite: 228 cm\nTiefe: 98 cm\nHöhe: 78 cm\nSitzhöhe: 44 cm\nSitztiefe: 60 cm",
        "material_construction": "Gestell aus massivem Buchenholz\nWellenfederung mit Kaltschaumpolsterung\nBezug: 100 % Polyester-Bouclé\nFüße aus geölter Eiche",
        "features_feel": "Weicher, einladender Sitzkomfort\nBouclé-Bezug mit leicht körniger Haptik\nRückenkissen lose aufliegend",
        "images": [{"src": "/static/demo/sofa-1.svg", "alt": "Sandfarbenes Sofa Wolke, Frontansicht"},
                   {"src": "/static/demo/sofa-1b.svg", "alt": "Sofa Wolke vor hellem Hintergrund"}],
    },
    {
        "title": "Sofa „Linea“ 2-Sitzer",
        "price": "1290.00", "sku": "DEMO-SOFA-002",
        "body_html": "<p>Klare Linien, schmale Armlehnen, kompakte Maße: ideal für kleinere Wohnungen.</p>",
        "dimensions": "Breite: 176 cm\nTiefe: 86 cm\nHöhe: 80 cm\nSitzhöhe: 46 cm",
        "material_construction": "Gestell aus Kiefernholz und Sperrholz\nNosag-Federung\nBezug: Samt in Tannengrün\nMetallfüße, pulverbeschichtet",
        "features_feel": "Fester, aufrechter Sitzkomfort\nSamtiger, weicher Griff\nPflegeleicht: abwischbar mit feuchtem Tuch",
        "images": [{"src": "/static/demo/sofa-2.svg", "alt": "Grünes Sofa Linea, Frontansicht"},
                   {"src": "/static/demo/sofa-2b.svg", "alt": "Sofa Linea vor grauem Hintergrund"}],
    },
    {
        "title": "Sessel-Sofa „Terra“ Loveseat",
        "price": "990.00", "sku": "DEMO-SOFA-003",
        "body_html": "<p>Ein kleiner Loveseat in warmem Terrakotta – ein Farbtupfer für Lesecke oder Flur.</p>",
        "dimensions": "Breite: 140 cm\nTiefe: 84 cm\nHöhe: 76 cm",
        "material_construction": "Gestell aus Birkenholz\nSchaumstoffpolsterung\nBezug: Baumwoll-Leinen-Mischung",
        "features_feel": "Mittelfester Sitzkomfort\nNatürliche, leicht strukturierte Oberfläche",
        "images": [{"src": "/static/demo/sofa-3.svg", "alt": "Terrakottafarbenes Sofa Terra"}],
    },
]


def upload(product: dict, api_key: str) -> None:
    sku, price = product.pop("sku"), product.pop("price")
    body = {"product": {**product, "variants": [{"sku": sku, "price": price}]}}
    request = urllib.request.Request(
        f"{SHOP_URL}/products",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            action = "created" if response.status == 201 else "updated"
            print(f"  {response.status} {action}: {product['title']}")
    except urllib.error.HTTPError as err:
        print(f"  ERROR {err.code} for {product['title']}: {err.read().decode()}")


if __name__ == "__main__":
    key = read_api_key()
    print(f"Uploading {len(DEMO_SOFAS)} demo sofas to {SHOP_URL} ...")
    for sofa in DEMO_SOFAS:
        upload(dict(sofa), key)
    print(f"Done. Open {SHOP_URL}/ in your browser.")
