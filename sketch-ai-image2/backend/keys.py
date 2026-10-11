"""API key helper: validate a Stability AI key, activate it, and save it to .env."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Tuple

import requests

BALANCE_URL = "https://api.stability.ai/v1/user/balance"


def env_path() -> Path:
    return Path(os.getenv("ENV_FILE_PATH") or Path(__file__).resolve().parent.parent / ".env")


def mask(key: str) -> str:
    return (key[:5] + "…" + key[-4:]) if len(key) > 12 else "set"


def check_key(key: str) -> Tuple[bool, str, float]:
    """Return (is_valid, message, credits). Uses the free balance endpoint."""
    key = (key or "").strip()
    if len(key) < 10 or re.search(r"\s", key):
        return False, "That does not look like a valid key. Paste it without spaces.", 0.0
    try:
        r = requests.get(BALANCE_URL, headers={"Authorization": f"Bearer {key}"}, timeout=15)
    except requests.RequestException as exc:
        return False, f"Could not reach Stability AI to verify the key: {exc}", 0.0
    if r.status_code == 200:
        try:
            credits = float(r.json().get("credits", 0))
        except Exception:
            credits = 0.0
        return True, "API key is active.", credits
    if r.status_code in (401, 403):
        return False, "Stability AI says this key is invalid or revoked.", 0.0
    return False, f"Stability AI returned status {r.status_code}. Try again shortly.", 0.0


def save_key(key: str) -> None:
    """Activate for this process and persist to .env (other lines preserved)."""
    os.environ["STABILITY_API_KEY"] = key
    path = env_path()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out, done = [], False
    for line in lines:
        if line.startswith("STABILITY_API_KEY="):
            out.append(f"STABILITY_API_KEY={key}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"STABILITY_API_KEY={key}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def remove_key() -> None:
    os.environ["STABILITY_API_KEY"] = ""
    path = env_path()
    if path.exists():
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if not l.startswith("STABILITY_API_KEY=")]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
