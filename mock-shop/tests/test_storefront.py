"""Tests for the storefront part of the mock shop."""
import importlib, sqlite3, sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
KEY = "test-key-123"
H = {"X-API-Key": KEY}

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOP_API_KEY", KEY)
    monkeypatch.setenv("SHOP_DB_PATH", str(tmp_path / "shop.db"))
    monkeypatch.setenv("SHOP_MEDIA_DIR", str(tmp_path / "media"))
    import app as shop
    importlib.reload(shop)
    with TestClient(shop.app) as c:
        yield c

def sofa(**extra):
    p = {"title": "Sofa Test", "body_html": "<p>Zeile 1</p><p>Zeile 2</p>",
         "dimensions": "Breite: 200 cm", "material_construction": "Buche",
         "features_feel": "weich", "images": [{"src": "/static/demo/sofa-1.svg", "alt": "x"}],
         "variants": [{"sku": "S1", "price": "1890.00"}]}
    p.update(extra)
    return {"product": p}

def test_storefront_is_public_and_returns_plain_text(client):
    client.post("/products", json=sofa(), headers=H)
    data = client.get("/api/storefront/products").json()   # no key needed
    p = data["products"][0]
    assert data["currency"] == "EUR"
    assert p["description"] == "Zeile 1\nZeile 2"
    assert p["dimensions"] == "Breite: 200 cm"
    assert p["images"][0]["src"] == "/static/demo/sofa-1.svg"

def test_storefront_strips_scripts(client):
    client.post("/products", json=sofa(body_html="<script>alert(1)</script><b>Hallo</b>"), headers=H)
    desc = client.get("/api/storefront/products").json()["products"][0]["description"]
    assert "<" not in desc and "Hallo" in desc

def test_storefront_cannot_write(client):
    assert client.post("/api/storefront/products", json=sofa()).status_code == 405

def test_homepage_and_assets_served(client):
    assert "Demo Möbelshop" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/demo/sofa-1.svg").status_code == 200

def test_old_database_is_migrated(tmp_path, monkeypatch):
    # A database from the first version (without the new columns) must keep working
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE products (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL, body_html TEXT NOT NULL, vendor TEXT NOT NULL, product_type TEXT NOT NULL,
        price TEXT NOT NULL, source_url TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    con.execute("INSERT INTO products VALUES (1,'OLD','Altes Produkt','','v','Book','9.99',NULL,'t','t')")
    con.commit(); con.close()
    monkeypatch.setenv("SHOP_API_KEY", KEY)
    monkeypatch.setenv("SHOP_DB_PATH", str(db))
    monkeypatch.setenv("SHOP_MEDIA_DIR", str(tmp_path / "media"))
    import app as shop
    importlib.reload(shop)
    with TestClient(shop.app) as c:
        p = c.get("/api/storefront/products").json()["products"][0]
        assert p["title"] == "Altes Produkt" and p["images"] == []
