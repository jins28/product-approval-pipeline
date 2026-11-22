"""Scraper tests with saved sample pages: no internet needed, fast, repeatable.
Run with:  pytest scraper/tests -v"""
import json, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scraper  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def shopify_is_default(monkeypatch):
    # The tests in this file are about the Shopify source
    monkeypatch.setattr(scraper, "SOURCE", "shopify")
    monkeypatch.setattr(scraper, "COLLECTION", "furniture-by-category-sofas")


class FakeResponse:
    def __init__(self, text="", status=200, content=b""):
        self.text, self.status_code, self.content = text, status, content or text.encode()
        self.ok = status < 400
    def json(self):
        return json.loads(self.text)
    def raise_for_status(self):
        if not self.ok:
            raise scraper.requests.HTTPError(f"{self.status_code} error")


class FakeSession:
    """Answers like the real website would, from the fixture files."""
    def __init__(self, robots="User-agent: *\nDisallow: /checkout\n", page="page_details.html"):
        self.headers, self.calls, self.robots, self.page = {}, [], robots, page
    def get(self, url, timeout=None, **kw):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return FakeResponse(self.robots)
        if "products.json" in url:
            return FakeResponse((FIX / "products.json").read_text() if "page=1" in url else '{"products": []}')
        if "/products/broken-sofa" in url:
            return FakeResponse("server error", status=500)
        if "/products/" in url:
            return FakeResponse((FIX / self.page).read_text())
        if "cdn.example.com" in url:
            return FakeResponse(content=b"\xff\xd8fake-jpeg")
        return FakeResponse("not found", status=404)


def client(**kw):
    return scraper.PoliteClient(base_url="https://shop.example.com", delay=0, session=FakeSession(**kw))


@pytest.mark.parametrize("page", ["page_details.html", "page_buttons.html", "page_headings.html"])
def test_sections_found_in_all_page_styles(page):
    s = scraper.parse_sections((FIX / page).read_text())
    assert s["dimensions"] and s["material_construction"] and s["features_feel"]


def test_details_style_content_exact():
    s = scraper.parse_sections((FIX / "page_details.html").read_text())
    assert s["dimensions"] == '94" W, 52" D, 32" H.\nSeat height: 17".'
    assert s["material_construction"] == "Polished brass tapered legs.\nVelvet upholstery."
    assert s["features_feel"] == "Imported."


def test_headings_style_stops_at_next_heading():
    s = scraper.parse_sections((FIX / "page_headings.html").read_text())
    assert s["dimensions"] == '60" W\n34" D'
    assert "Wipe clean" not in s["features_feel"]


def test_full_scrape(tmp_path):
    result = scraper.scrape(limit=5, client=client(), media_dir=tmp_path)
    assert result["count"] == 2
    first = result["products"][0]
    assert first["id"] == "SH-31548"
    assert first["price"] == "5750.00"
    assert first["url"] == "https://shop.example.com/products/demo-curved-sofa"
    assert first["description_en"] == "Heaven Sent.\nA curved sofa with brass legs.\nAlways dreamy."
    # max 4 images, in gallery order, saved locally, served by the shop at /media
    assert [i["src"] for i in first["images"]] == [f"/media/demo-curved-sofa-{n}.jpg" for n in range(1, 5)]
    assert first["images"][0]["alt"] == "Front view"
    assert (tmp_path / "demo-curved-sofa-1.jpg").read_bytes().startswith(b"\xff\xd8")
    # second product: no SKU -> product id, price with comma cleaned, description cut before "Dimensions"
    second = result["products"][1]
    assert second["id"] == "SH-222" and second["price"] == "2100.00"
    assert second["description_en"] == "A small settee."
    # the broken product is reported, the run continues
    assert result["errors"][0]["url"].endswith("/products/broken-sofa")


def test_images_downloaded_only_once(tmp_path):
    c = client()
    scraper.scrape(limit=1, client=c, media_dir=tmp_path)
    cdn_calls = sum("cdn.example.com" in u for u in c.session.calls)
    c2 = client()
    scraper.scrape(limit=1, client=c2, media_dir=tmp_path)
    assert cdn_calls == 4
    assert sum("cdn.example.com" in u for u in c2.session.calls) == 0


def test_image_urls_get_https_and_width():
    url = scraper.sized_image_url("//cdn.example.com/a.jpg?v=1", 800)
    assert url == "https://cdn.example.com/a.jpg?v=1&width=800"


def test_robots_txt_is_respected(tmp_path):
    c = client(robots="User-agent: *\nDisallow: /collections/\n")
    with pytest.raises(PermissionError):
        scraper.scrape(limit=1, client=c, media_dir=tmp_path)


def test_no_images_option(tmp_path):
    result = scraper.scrape(limit=1, with_images=False, client=client(), media_dir=tmp_path)
    assert result["products"][0]["images"] == [] and not any(tmp_path.iterdir())


@pytest.mark.parametrize("value,expected", [
    ("furniture-by-category-chairs", "furniture-by-category-chairs"),
    ("https://example-store.com/collections/furniture-by-category-chairs?srsltid=AYCX9vJ66Y", "furniture-by-category-chairs"),
    ("https://example-store.com/collections/furniture-by-category-sofas/", "furniture-by-category-sofas"),
])
def test_collection_handle_accepts_links(value, expected):
    assert scraper.collection_handle(value) == expected


def test_collection_handle_rejects_junk():
    with pytest.raises(ValueError):
        scraper.collection_handle("../../etc")


def test_other_collection_is_used_in_urls(tmp_path):
    c = client()
    result = scraper.scrape(limit=1, with_images=False, client=c, media_dir=tmp_path,
                            collection="https://shop.example.com/collections/furniture-by-category-chairs?srsltid=x")
    assert any("/collections/furniture-by-category-chairs/products.json" in u for u in c.session.calls)
    assert result["products"][0]["collection"] == "furniture-by-category-chairs"
    assert result["products"][0]["product_type"] == "Chair"


class RateLimitedSession(FakeSession):
    """Answers 429 for the first `fail_times` product-list requests."""
    def __init__(self, fail_times, retry_after="5", **kw):
        super().__init__(**kw)
        self.fail_times, self.retry_after = fail_times, retry_after
    def get(self, url, timeout=None, **kw):
        if "products.json" in url and self.fail_times > 0:
            self.fail_times -= 1
            self.calls.append(url)
            r = FakeResponse("Too Many Requests", status=429)
            r.headers = {"Retry-After": self.retry_after}
            return r
        return super().get(url, timeout, **kw)


def test_429_is_retried_with_retry_after(tmp_path, monkeypatch):
    waits = []
    monkeypatch.setattr(scraper.time, "sleep", lambda s: waits.append(s))
    c = scraper.PoliteClient(base_url="https://shop.example.com", delay=0, session=RateLimitedSession(fail_times=1))
    result = scraper.scrape(limit=1, with_images=False, client=c, media_dir=tmp_path)
    assert result["count"] == 1
    assert 5.0 in waits                      # waited as long as the site asked


def test_429_gives_up_with_clear_message(tmp_path, monkeypatch):
    monkeypatch.setattr(scraper.time, "sleep", lambda s: None)
    c = scraper.PoliteClient(base_url="https://shop.example.com", delay=0, session=RateLimitedSession(fail_times=99))
    with pytest.raises(RuntimeError, match="rate-limiting"):
        scraper.scrape(limit=1, with_images=False, client=c, media_dir=tmp_path)
    assert sum("products.json" in u for u in c.session.calls) == scraper.MAX_RETRIES + 1


def test_only_needed_page_size_is_requested(tmp_path):
    c = client()
    scraper.scrape(limit=1, with_images=False, client=c, media_dir=tmp_path)
    lists = [u for u in c.session.calls if "products.json" in u]
    assert lists == ["https://shop.example.com/collections/furniture-by-category-sofas/products.json?limit=1&page=1"]


def test_retry_wait_without_header_grows_and_is_capped():
    r = FakeResponse("x", status=429); r.headers = {}
    assert [scraper.PoliteClient._retry_wait(r, a) for a in range(4)] == [10, 20, 40, 60]
