"""Sketch -> prompt conversion (heuristic + optional Claude vision)."""
from __future__ import annotations

import base64
import os
from typing import Dict, Optional

import requests

STYLES: Dict[str, str] = {
    "photorealistic": "photorealistic, natural lighting, sharp focus, high detail, 35mm photo",
    "digital-art": "polished digital illustration, vibrant colors, clean shading, concept art",
    "watercolor": "soft watercolor painting, flowing pigments, paper texture, gentle gradients",
    "anime": "anime style, clean line art, cel shading, vivid colors",
    "oil-painting": "classical oil painting, rich brushwork, warm palette, canvas texture",
    "3d-render": "3D render, soft global illumination, smooth materials, studio lighting",
    "pencil": "detailed pencil drawing, graphite shading, cross-hatching, paper grain",
}

NEGATIVE = "blurry, low quality, distorted, extra limbs, watermark, text, signature"


def style_names():
    return list(STYLES.keys())


def heuristic_description(analysis: Dict) -> str:
    """Describe sketch structure in words from the OpenCV analysis."""
    s = analysis.get("shapes", {})
    parts = []
    for key, label in (("circles", "round"), ("triangles", "triangular"), ("rectangles", "rectangular")):
        n = s.get(key, 0)
        if n:
            parts.append(f"{n} {label} shape{'s' if n > 1 else ''}")
    if s.get("other_closed"):
        parts.append(f"{s['other_closed']} organic shape{'s' if s['other_closed'] > 1 else ''}")
    shapes = ", ".join(parts) if parts else "flowing lines"
    return f"a {analysis.get('complexity', 'simple')} composition made of {shapes}"


def describe_with_claude(png_bytes: bytes) -> Optional[str]:
    """Ask Claude to describe the sketch. Returns None on any problem."""
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 200,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": base64.b64encode(png_bytes).decode(),
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "This is a rough hand-drawn sketch. In ONE sentence (max 40 words), "
                                    "describe what it most likely depicts and its layout, as a noun phrase "
                                    "usable inside an image-generation prompt. No preamble."
                                ),
                            },
                        ],
                    }
                ],
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        blocks = resp.json().get("content", [])
        text = " ".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        return text or None
    except Exception:
        return None


def build_prompt(user_prompt: str, style: str, analysis: Dict, caption: Optional[str] = None) -> str:
    user_prompt = (user_prompt or "").strip()
    style_text = STYLES.get(style, STYLES["digital-art"])
    subject = user_prompt or caption or heuristic_description(analysis)
    if user_prompt and caption:
        subject = f"{user_prompt}, {caption}"
    return f"{subject}. {style_text}. Follow the composition and proportions of the sketch."
