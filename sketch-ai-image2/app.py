"""Sketch -> AI Image : Flask backend."""
from __future__ import annotations

import base64
import os
import re
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

from backend import generators, keys, preprocess, prompt_builder  # noqa: E402

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024  # 12 MB


def data_url(raw: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def read_image_bytes() -> bytes:
    """Accept multipart 'file' or JSON/form 'image' (data URL or base64)."""
    if "file" in request.files:
        return request.files["file"].read()
    payload = request.get_json(silent=True) or request.form
    img = (payload.get("image") or "") if payload else ""
    if not img:
        raise preprocess.ImageError("No sketch received. Draw or upload one first.")
    img = re.sub(r"^data:image/[a-zA-Z0-9.+-]+;base64,", "", img)
    try:
        return base64.b64decode(img, validate=False)
    except Exception:
        raise preprocess.ImageError("The image data was corrupted.")


@app.get("/")
def index():
    return render_template(
        "index.html",
        styles=prompt_builder.style_names(),
        providers=generators.available_providers(),
    )


@app.get("/api/health")
def health():
    return jsonify(status="ok", providers=generators.available_providers())


@app.post("/api/generate")
def generate():
    started = time.time()
    try:
        raw = read_image_bytes()
        payload = request.get_json(silent=True) or request.form
        user_prompt = (payload.get("prompt") or "")[:500]
        style = payload.get("style") or "digital-art"
        provider = generators.resolve_provider(payload.get("provider") or "auto")
        try:
            strength = min(1.0, max(0.1, float(payload.get("strength") or 0.7)))
        except ValueError:
            strength = 0.7

        clean_png, clean_bgr, mask, analysis = preprocess.process(raw)

        caption = prompt_builder.describe_with_claude(clean_png)
        prompt = prompt_builder.build_prompt(user_prompt, style, analysis, caption)

        if provider == "stability":
            result = generators.generate_stability(clean_png, prompt, prompt_builder.NEGATIVE, strength)
        else:
            result = generators.generate_demo(clean_bgr, mask, style)

        return jsonify(
            ok=True,
            image=data_url(result.image, result.mime),
            processed_sketch=data_url(clean_png),
            prompt=prompt,
            provider=result.provider,
            note=result.note,
            analysis=analysis,
            claude_caption=bool(caption),
            seconds=round(time.time() - started, 2),
        )
    except (preprocess.ImageError, generators.GenerationError) as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception as exc:  # last-resort safety net: never return an HTML 500 page
        app.logger.exception("Unexpected error")
        return jsonify(ok=False, error=f"Unexpected server error: {exc}"), 500



@app.get("/api/key")
def key_status():
    key = os.getenv("STABILITY_API_KEY", "").strip()
    if not key:
        return jsonify(active=False, message="No API key set.")
    ok, msg, credits = keys.check_key(key)
    return jsonify(active=ok, masked=keys.mask(key), credits=credits, message=msg)


@app.post("/api/key")
def key_save():
    payload = request.get_json(silent=True) or {}
    key = (payload.get("key") or "").strip()
    ok, msg, credits = keys.check_key(key)
    if not ok:
        return jsonify(active=False, message=msg), 400
    keys.save_key(key)
    return jsonify(active=True, masked=keys.mask(key), credits=credits,
                   message="API key activated and saved to .env.")


@app.delete("/api/key")
def key_delete():
    keys.remove_key()
    return jsonify(active=False, message="API key removed.")

@app.errorhandler(413)
def too_large(_e):
    return jsonify(ok=False, error="Image is too large (max 12 MB)."), 413


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False)
