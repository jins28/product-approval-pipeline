"""Tests for the mock shop. Run with:  pytest mock-shop/tests -v"""

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

KEY = "test-key-123"
HEADERS = {"X-API-Key": KEY}


def sample(sku="a897fe39b1053632", price="51.77", title="A Light in the Attic"):
    return {"product": {
        "title": title,
        "body_html": "<p>Ein Gedichtband für Kinder und Erwachsene.</p>",
        "source_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        "variants": [{"sku": sku, "price": price}],
    }}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Fresh database file and a known key for every test
    monkeypatch.setenv("SHOP_API_KEY", KEY)
    monkeypatch.setenv("SHOP_DB_PATH", str(tmp_path / "shop.db"))
    monkeypatch.setenv("SHOP_MEDIA_DIR", str(tmp_path / "media"))
    import app as shop
    importlib.reload(shop)
    with TestClient(shop.app) as c:  # "with" runs the startup code
        yield c


def test_health_needs_no_key(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_rejects_missing_or_wrong_key(client):
    assert client.post("/products", json=sample()).status_code == 401
    assert client.post("/products", json=sample(), headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/products").status_code == 401


def test_create_then_list(client):
    r = client.post("/products", json=sample(), headers=HEADERS)
    assert r.status_code == 201
    product = r.json()["product"]
    assert product["id"] == 1
    assert product["variants"] == [{"sku": "a897fe39b1053632", "price": "51.77"}]

    listed = client.get("/products", headers=HEADERS).json()["products"]
    assert len(listed) == 1
    assert client.get("/products/1", headers=HEADERS).json()["product"]["title"] == "A Light in the Attic"


def test_same_sku_twice_updates_instead_of_duplicating(client):
    client.post("/products", json=sample(price="51.77"), headers=HEADERS)
    r = client.post("/products", json=sample(price="49.99"), headers=HEADERS)
    assert r.status_code == 200  # updated, not created
    listed = client.get("/products", headers=HEADERS).json()["products"]
    assert len(listed) == 1
    assert listed[0]["variants"][0]["price"] == "49.99"


@pytest.mark.parametrize("bad", [
    {"product": {"title": "x", "variants": []}},                              # no variant
    {"product": {"title": "", "variants": [{"sku": "1", "price": "1.00"}]}},  # empty title
    {"product": {"title": "x", "variants": [{"sku": "1", "price": "£51.77"}]}},  # price not cleaned
    {"title": "x"},                                                            # missing envelope
])
def test_invalid_payloads_return_422(client, bad):
    assert client.post("/products", json=bad, headers=HEADERS).status_code == 422


def test_unknown_product_404(client):
    assert client.get("/products/999", headers=HEADERS).status_code == 404


