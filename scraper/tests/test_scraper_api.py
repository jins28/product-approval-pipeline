"""API tests for the scraper service (the real scraping is replaced by a stub)."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as api  # noqa: E402

def test_scrape_endpoint_passes_parameters(monkeypatch):
    seen = {}
    def fake(limit, with_images, collection, source):
        seen.update(limit=limit, images=with_images, collection=collection, source=source)
        return {"count": 0, "products": [], "errors": []}
    monkeypatch.setattr(api.scraper, "scrape", fake)
    c = TestClient(api.app)
    r = c.get("/scrape", params={"limit": 2, "images": "false", "source": "jonathanadler",
              "collection": "https://jonathanadler.com/collections/furniture-by-category-chairs?srsltid=x"})
    assert r.status_code == 200
    assert seen == {"limit": 2, "images": False, "collection": "furniture-by-category-chairs",
                    "source": "jonathanadler"}

def test_bad_input_rejected():
    c = TestClient(api.app)
    assert c.get("/scrape", params={"limit": 0}).status_code == 422
    assert c.get("/scrape", params={"source": "jonathanadler", "collection": "../x"}).status_code == 422
    assert c.get("/scrape", params={"source": "amazon"}).status_code == 422

def test_site_down_gives_502(monkeypatch):
    def boom(**kw): raise ConnectionError("unreachable")
    monkeypatch.setattr(api.scraper, "scrape", boom)
    r = TestClient(api.app).get("/scrape")
    assert r.status_code == 502 and "unreachable" in r.json()["detail"]
