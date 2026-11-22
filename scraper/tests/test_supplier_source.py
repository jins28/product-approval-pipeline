"""Scrape the REAL supplier pages built by supplier-site/build.py (read from disk, no network)."""
import subprocess, sys
from pathlib import Path
from urllib.parse import urlparse
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scraper  # noqa: E402

SITE = Path(__file__).resolve().parents[2] / "supplier-site"
PUBLIC = SITE / "public"
BASE = "https://nordholm-demo.example"


@pytest.fixture(scope="module", autouse=True)
def built_site():
    subprocess.run([sys.executable, str(SITE / "build.py")], check=True, capture_output=True)


class Resp:
    def __init__(self, body: bytes, status=200):
        self.content, self.status_code, self.ok = body, status, status < 400
        self.text, self.headers = body.decode("utf-8", "replace"), {}
    def raise_for_status(self):
        if not self.ok:
            raise scraper.requests.HTTPError(f"{self.status_code}")


class FileSession:
    """Serves the built website from disk, like a web server would."""
    def __init__(self):
        self.headers, self.calls = {}, []
    def get(self, url, timeout=None, **kw):
        self.calls.append(url)
        path = PUBLIC / urlparse(url).path.lstrip("/")
        return Resp(path.read_bytes()) if path.is_file() else Resp(b"not found", 404)


def client():
    return scraper.PoliteClient(base_url=BASE, delay=0, session=FileSession())


def test_scrapes_all_ten_products(tmp_path):
    result = scraper.scrape(limit=50, source="supplier", client=client(), media_dir=tmp_path)
    assert result["count"] == 10 and result["errors"] == []


def test_product_fields_are_complete(tmp_path):
    p = scraper.scrape(limit=1, source="supplier", client=client(), media_dir=tmp_path)["products"][0]
    assert p["id"] == "NH-1001"
    assert p["title"] == "Fjord 3-Seater Sofa"
    assert p["price"] == "1890.00" and p["currency"] == "EUR"
    assert p["product_type"] == "Sofa"
    assert p["url"] == f"{BASE}/products/fjord-3-seater-sofa.html"
    assert p["description_en"].startswith("A relaxed three-seater")
    assert p["dimensions"].splitlines()[0] == "Width: 228 cm"
    assert "solid beech" in p["material_construction"]
    assert "Cleaning code: S" in p["features_feel"]
    assert [i["src"] for i in p["images"]] == ["/media/fjord-3-seater-sofa-1.svg", "/media/fjord-3-seater-sofa-2.svg"]
    assert (tmp_path / "fjord-3-seater-sofa-1.svg").read_text().startswith("<svg")


def test_category_filter(tmp_path):
    r = scraper.scrape(limit=50, source="supplier", collection="chair", with_images=False,
                       client=client(), media_dir=tmp_path)
    assert r["count"] == 5 and {p["product_type"] for p in r["products"]} == {"Chair"}


def test_robots_allows_supplier():
    assert client().robots.can_fetch(scraper.USER_AGENT, f"{BASE}/products/x.html")


def test_unknown_source_rejected(tmp_path):
    with pytest.raises(ValueError):
        scraper.scrape(source="amazon", client=client(), media_dir=tmp_path)
