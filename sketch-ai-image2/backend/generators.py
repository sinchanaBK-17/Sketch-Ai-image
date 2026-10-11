"""Image generation providers: Stability AI (real) and Demo (local, no key)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict

import cv2
import numpy as np
import requests

from .preprocess import encode_png


class GenerationError(RuntimeError):
    """Raised when a provider fails (message is shown to the user)."""


@dataclass
class GenResult:
    image: bytes
    mime: str
    provider: str
    note: str = ""


def available_providers() -> Dict[str, bool]:
    return {"stability": bool(os.getenv("STABILITY_API_KEY", "").strip()), "demo": True}


def resolve_provider(requested: str) -> str:
    requested = (requested or os.getenv("IMAGE_PROVIDER", "auto") or "auto").lower()
    if requested == "auto":
        return "stability" if available_providers()["stability"] else "demo"
    if requested not in ("stability", "demo"):
        raise GenerationError(f"Unknown provider '{requested}'.")
    return requested


# ----------------------------------------------------------------- Stability
def generate_stability(sketch_png: bytes, prompt: str, negative: str, strength: float) -> GenResult:
    key = os.getenv("STABILITY_API_KEY", "").strip()
    if not key:
        raise GenerationError("STABILITY_API_KEY is not set. Add it to .env or use Demo mode.")
    try:
        resp = requests.post(
            "https://api.stability.ai/v2beta/stable-image/control/sketch",
            headers={"authorization": f"Bearer {key}", "accept": "image/*"},
            files={"image": ("sketch.png", sketch_png, "image/png")},
            data={
                "prompt": prompt,
                "negative_prompt": negative,
                "control_strength": str(strength),
                "output_format": "png",
            },
            timeout=120,
        )
    except requests.RequestException as exc:
        raise GenerationError(f"Could not reach Stability AI: {exc}") from exc

    if resp.status_code == 200 and resp.content:
        return GenResult(resp.content, "image/png", "stability", "Generated with Stability AI (sketch control).")

    detail = ""
    try:
        body = resp.json()
        detail = body.get("errors", [body.get("message", "")])[0] if isinstance(body, dict) else ""
    except Exception:
        detail = resp.text[:200]
    if resp.status_code in (401, 403):
        raise GenerationError("Stability AI rejected the API key (401/403). Check STABILITY_API_KEY.")
    if resp.status_code == 402:
        raise GenerationError("Stability AI account has insufficient credits.")
    if resp.status_code == 429:
        raise GenerationError("Rate limit reached. Wait a moment and try again.")
    raise GenerationError(f"Stability AI error {resp.status_code}: {detail}")


# ---------------------------------------------------------------------- Demo
_PALETTES = {
    "photorealistic": [(235, 206, 135), (120, 170, 90)],
    "digital-art": [(255, 170, 90), (170, 90, 200)],
    "watercolor": [(240, 220, 200), (200, 225, 190)],
    "anime": [(255, 200, 150), (190, 140, 255)],
    "oil-painting": [(90, 140, 190), (60, 90, 120)],
    "3d-render": [(230, 230, 235), (170, 175, 190)],
    "pencil": [(245, 245, 245), (225, 225, 225)],
}


def generate_demo(clean_bgr: np.ndarray, mask: np.ndarray, style: str) -> GenResult:
    """Local fallback: colourises the sketch with OpenCV. Not real AI - lets the
    whole app run end-to-end with zero setup or API keys."""
    h, w = mask.shape
    c1, c2 = _PALETTES.get(style, _PALETTES["digital-art"])
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    top = np.array(c1, np.float32)[None, None, :]
    bottom = np.array(c2, np.float32)[None, None, :]
    canvas = (top * (1 - t) + bottom * t) * np.ones((h, w, 1), np.float32)
    canvas = canvas.astype(np.uint8)

    # Fill closed regions with colour from the sketch's enclosed areas.
    inv = cv2.bitwise_not(mask)
    n, labels = cv2.connectedComponents(inv)
    rng = np.random.RandomState(7)
    fills = canvas.copy()
    for lab in range(1, n):
        region = labels == lab
        area = int(region.sum())
        if area < 0.002 * h * w or area > 0.6 * h * w:
            continue
        hue = int(rng.randint(0, 180))
        colour = cv2.cvtColor(np.uint8([[[hue, 130, 225]]]), cv2.COLOR_HSV2BGR)[0, 0]
        fills[region] = colour
    soft = cv2.bilateralFilter(fills, 9, 60, 60)

    if style == "pencil":
        soft = cv2.cvtColor(cv2.cvtColor(soft, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)

    # Draw (softened) strokes on top.
    edge = cv2.GaussianBlur(mask, (0, 0), 1.2)
    alpha = (edge.astype(np.float32) / 255.0)[:, :, None]
    dark = np.array((40, 30, 30), np.float32)
    out = soft.astype(np.float32) * (1 - 0.85 * alpha) + dark * (0.85 * alpha)
    return GenResult(
        encode_png(np.clip(out, 0, 255).astype(np.uint8)),
        "image/png",
        "demo",
        "Demo mode (local OpenCV rendering). Add STABILITY_API_KEY to .env for real AI images.",
    )
