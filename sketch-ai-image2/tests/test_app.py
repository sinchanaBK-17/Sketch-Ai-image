import base64
import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["STABILITY_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

from app import app  # noqa: E402
from backend import preprocess  # noqa: E402


def make_sketch(png=True):
    img = np.full((400, 500, 3), 255, np.uint8)
    cv2.circle(img, (250, 140), 80, (0, 0, 0), 4)
    cv2.rectangle(img, (100, 290), (400, 380), (0, 0, 0), 4)
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_preprocess_and_analysis():
    clean_png, clean, mask, analysis = preprocess.process(make_sketch())
    assert clean.shape == (1024, 1024, 3)
    assert analysis["elements"] >= 1
    assert analysis["shapes"]["circles"] >= 1


def test_blank_image_rejected():
    blank = cv2.imencode(".png", np.full((200, 200, 3), 255, np.uint8))[1].tobytes()
    with pytest.raises(preprocess.ImageError):
        preprocess.process(blank)


def test_garbage_rejected():
    with pytest.raises(preprocess.ImageError):
        preprocess.process(b"not an image")


def test_index_and_health(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/health").get_json()["status"] == "ok"


def test_generate_demo(client):
    img = "data:image/png;base64," + base64.b64encode(make_sketch()).decode()
    r = client.post("/api/generate", json={"image": img, "prompt": "a house", "style": "anime"})
    data = r.get_json()
    assert r.status_code == 200 and data["ok"] and data["provider"] == "demo"
    assert data["image"].startswith("data:image/png;base64,")


def test_generate_multipart_file(client):
    import io
    r = client.post("/api/generate", data={"file": (io.BytesIO(make_sketch()), "s.png"), "style": "pencil"},
                    content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["ok"]


def test_generate_errors_are_json(client):
    r = client.post("/api/generate", json={"image": ""})
    assert r.status_code == 400 and r.get_json()["ok"] is False
    r = client.post("/api/generate", json={"image": "data:image/png;base64,AAAA"})
    assert r.status_code == 400
    img = "data:image/png;base64," + base64.b64encode(make_sketch()).decode()
    r = client.post("/api/generate", json={"image": img, "provider": "stability"})
    assert r.status_code == 400 and "STABILITY_API_KEY" in r.get_json()["error"]
