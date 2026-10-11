import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["STABILITY_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
import pytest
from app import app
from backend import keys


class FakeResp:
    def __init__(self, code, js=None):
        self.status_code, self._js = code, js or {}
    def json(self):
        return self._js


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ENV_FILE_PATH", str(tmp_path / ".env"))
    app.config["TESTING"] = True
    yield app.test_client()
    os.environ["STABILITY_API_KEY"] = ""


def test_valid_key_is_saved(client, monkeypatch, tmp_path):
    monkeypatch.setattr(keys.requests, "get", lambda *a, **k: FakeResp(200, {"credits": 25.0}))
    r = client.post("/api/key", json={"key": "sk-abcdefghijklmnop1234"})
    assert r.status_code == 200 and r.get_json()["active"] is True
    assert "STABILITY_API_KEY=sk-abcdefghijklmnop1234" in (tmp_path / ".env").read_text()
    assert client.get("/api/key").get_json()["active"] is True


def test_invalid_key_rejected(client, monkeypatch, tmp_path):
    monkeypatch.setattr(keys.requests, "get", lambda *a, **k: FakeResp(401))
    r = client.post("/api/key", json={"key": "sk-badbadbadbadbad"})
    assert r.status_code == 400 and r.get_json()["active"] is False
    assert not (tmp_path / ".env").exists()


def test_short_key_and_remove(client, monkeypatch):
    assert client.post("/api/key", json={"key": "abc"}).status_code == 400
    assert client.delete("/api/key").get_json()["active"] is False
    assert client.get("/api/key").get_json()["active"] is False
