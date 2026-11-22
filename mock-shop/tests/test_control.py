"""Tests for the test page backend (/api/control/*). n8n is replaced by a fake."""
import importlib, io, json, sys, urllib.error
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def shop(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOP_API_KEY", "k")
    monkeypatch.setenv("SHOP_DB_PATH", str(tmp_path / "s.db"))
    monkeypatch.setenv("SHOP_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("CONTROL_PASSWORD", "demo123")
    monkeypatch.setenv("N8N_WEBHOOK_BASE", "http://n8n.test/webhook")
    monkeypatch.setenv("VOICE_AGENT_ID", "agent_x")
    import app
    importlib.reload(app)
    monkeypatch.setattr(app.time, "sleep", lambda s: None)
    calls = []

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        calls.append((req.full_url, json.loads(req.data)))
        mode = app.FAKE_N8N
        if mode == "down":
            raise urllib.error.URLError("refused")
        if mode == "inactive":
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO())
        return FakeResp()

    app.FAKE_N8N = "ok"
    monkeypatch.setattr(app.urllib.request, "urlopen", fake_urlopen)
    with TestClient(app.app) as c:
        yield c, app, calls


def test_config_has_no_secrets(shop):
    c, app, _ = shop
    cfg = c.get("/api/control/config").json()
    assert cfg["enabled"] is True and cfg["voice_agent_id"] == "agent_x"
    assert "demo123" not in json.dumps(cfg)


def test_wrong_password(shop):
    c, _, calls = shop
    r = c.post("/api/control/check-new-products", json={"password": "nope"})
    assert r.status_code == 401 and calls == []


def test_check_forwards_to_n8n_then_cooldown(shop):
    c, _, calls = shop
    r = c.post("/api/control/check-new-products", json={"password": "demo123", "limit": 2, "collection": "chair"})
    assert r.status_code == 200
    assert calls == [("http://n8n.test/webhook/check-new-products", {"limit": 2, "collection": "chair"})]
    again = c.post("/api/control/check-new-products", json={"password": "demo123"})
    assert again.status_code == 429 and "Sekunden" in again.json()["detail"]
    # the other button has its own cooldown
    assert c.post("/api/control/upload-approved", json={"password": "demo123"}).status_code == 200


def test_invalid_input_rejected(shop):
    c, _, calls = shop
    assert c.post("/api/control/check-new-products", json={"password": "demo123", "limit": 99}).status_code == 422
    assert c.post("/api/control/check-new-products", json={"password": "demo123", "collection": "tables"}).status_code == 422
    assert calls == []


def test_n8n_down_and_inactive_workflow(shop):
    c, app, _ = shop
    app.FAKE_N8N = "down"
    r = c.post("/api/control/upload-approved", json={"password": "demo123"})
    assert r.status_code == 502 and "nicht erreichbar" in r.json()["detail"]
    app.FAKE_N8N = "inactive"
    r = c.post("/api/control/upload-approved", json={"password": "demo123"})
    assert r.status_code == 502 and "nicht aktiv" in r.json()["detail"]


def test_disabled_without_password(shop, monkeypatch):
    c, _, _ = shop
    monkeypatch.delenv("CONTROL_PASSWORD")
    assert c.get("/api/control/config").json()["enabled"] is False
    assert c.post("/api/control/upload-approved", json={"password": ""}).status_code == 503
