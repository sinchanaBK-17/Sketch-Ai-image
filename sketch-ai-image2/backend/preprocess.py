"""Image preprocessing + simple sketch analysis (OpenCV)."""
from __future__ import annotations

import math
from typing import Dict, Tuple

import cv2
import numpy as np

TARGET_SIZE = 1024


class ImageError(ValueError):
    """Raised for bad / unusable input images (shown to the user)."""


def decode_image(data: bytes) -> np.ndarray:
    """Decode bytes to a BGR uint8 image. Transparent pixels become white."""
    if not data:
        raise ImageError("No image data received.")
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ImageError("Could not read the image. Use a PNG, JPG, WEBP or BMP file.")
    if img.dtype != np.uint8:
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        bgr = img[:, :, :3].astype(np.float32)
        img = (bgr * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    return img[:, :, :3]


def clean_sketch(bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return (clean_sketch_bgr, ink_mask).

    clean_sketch: black strokes on white, cropped to content, square, 1024px.
    ink_mask: uint8 mask (255 = stroke) at the same size.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Limit absurdly large uploads before heavy work.
    h, w = gray.shape
    longest = max(h, w)
    if longest > 2400:
        scale = 2400.0 / longest
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    # Dark background (e.g. white chalk on blackboard) -> invert.
    if float(np.mean(gray)) < 110:
        gray = 255 - gray

    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Photos of paper: Otsu can over-select shadows. Fall back to adaptive threshold.
    if np.count_nonzero(mask) / mask.size > 0.45:
        mask = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12
        )

    # Remove specks.
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))

    if np.count_nonzero(mask) / mask.size < 0.0003:
        raise ImageError("The sketch looks empty. Please draw something first.")

    ys, xs = np.where(mask > 0)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    pad = int(0.08 * max(x1 - x0, y1 - y0, 20))
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(mask.shape[1] - 1, x1 + pad), min(mask.shape[0] - 1, y1 + pad)
    mask = mask[y0 : y1 + 1, x0 : x1 + 1]

    # Pad to square, resize.
    mh, mw = mask.shape
    side = max(mh, mw)
    square = np.zeros((side, side), np.uint8)
    square[(side - mh) // 2 : (side - mh) // 2 + mh, (side - mw) // 2 : (side - mw) // 2 + mw] = mask
    square = cv2.resize(square, (TARGET_SIZE, TARGET_SIZE), interpolation=cv2.INTER_AREA)

    # Thicken thin lines so the model sees them clearly.
    k = max(2, TARGET_SIZE // 256)
    square = cv2.dilate(square, np.ones((k, k), np.uint8))
    _, square = cv2.threshold(square, 80, 255, cv2.THRESH_BINARY)

    clean = np.full((TARGET_SIZE, TARGET_SIZE, 3), 255, np.uint8)
    clean[square > 0] = (0, 0, 0)
    return clean, square


def analyze_sketch(mask: np.ndarray) -> Dict:
    """Very light structural analysis used to hint the prompt."""
    h, w = mask.shape
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = 0.002 * h * w
    shapes = {"circles": 0, "triangles": 0, "rectangles": 0, "other_closed": 0, "lines": 0}
    kept = 0
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        kept += 1
        peri = cv2.arcLength(c, True)
        if peri == 0:
            continue
        # Perimeter of a pixelated contour is jittery, so compare the area with
        # the minimum enclosing circle instead of using 4*pi*A/P^2.
        (_cx, _cy), radius = cv2.minEnclosingCircle(c)
        circularity = area / (math.pi * radius * radius) if radius > 0 else 0
        approx = cv2.approxPolyDP(c, 0.03 * peri, True)
        x, y, bw, bh = cv2.boundingRect(c)
        fill = area / float(bw * bh) if bw * bh else 0
        if circularity > 0.85:
            shapes["circles"] += 1
        elif len(approx) == 3:
            shapes["triangles"] += 1
        elif len(approx) == 4:
            shapes["rectangles"] += 1
        elif fill < 0.15:
            shapes["lines"] += 1
        else:
            shapes["other_closed"] += 1

    ink_ratio = float(np.count_nonzero(mask)) / mask.size
    complexity = "simple" if ink_ratio < 0.03 else "moderately detailed" if ink_ratio < 0.08 else "detailed"
    return {
        "elements": kept,
        "shapes": shapes,
        "ink_ratio": round(ink_ratio, 4),
        "complexity": complexity,
    }


def encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ImageError("Could not encode image.")
    return buf.tobytes()


def process(data: bytes):
    """Full pipeline: bytes -> (clean_png_bytes, clean_bgr, mask, analysis)."""
    bgr = decode_image(data)
    clean, mask = clean_sketch(bgr)
    analysis = analyze_sketch(mask)
    return encode_png(clean), clean, mask, analysis
