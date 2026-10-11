# Sketch → AI Image

Draw or upload a rough sketch → OpenCV cleans it → a prompt is built → an AI model
turns it into an image → preview and download in the browser.

Based on the Team 2 PRD/TRD: HTML/CSS/JS frontend, Python (Flask) backend, OpenCV preprocessing,
image-generation API.

## Run in VS Code (3 steps)

1. **Open the project folder** in VS Code (`File → Open Folder…` → `sketch-ai-image2`, the folder containing `app.py`). Do not open its parent folder.
2. **Open a terminal** (`Ctrl+` ` ) and run:

   **Windows (PowerShell)**
   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe app.py
   ```
   These commands avoid PowerShell's Unix-incompatible `source` command and do not rely on the Microsoft Store `python` alias. If you are already in the parent folder, first run `Set-Location .\sketch-ai-image2`.

   **macOS / Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```
3. Open **http://127.0.0.1:5000**

Requires Python 3.9+. It works immediately in **Demo mode** (no keys needed).

## Activate your API key (easiest way)

1. Create a key at https://platform.stability.ai/account/keys (new accounts get free credits).
2. Start the app, paste the key into the **🔑 API key** box at the top, click **Save & activate**.
3. The app verifies it with Stability AI, shows **Active ✓** with your remaining credits and saves it to `.env`
   so it is still active next time. **Remove** deletes it.

## Real AI images (manual alternative)

```
copy .env.example .env      (Windows)    |    cp .env.example .env   (macOS/Linux)
```
Then edit `.env`:

| Key | Purpose |
|-----|---------|
| `STABILITY_API_KEY` | Real sketch→image generation (Stability AI "Control: Sketch") |
| `ANTHROPIC_API_KEY` | Optional: Claude vision describes your sketch to improve the prompt |

Restart the app after editing `.env` (on Windows, run `.\.venv\Scripts\python.exe app.py`).

## Tests

```
python -m pytest -q
```

## Structure

```
app.py                  Flask routes (/, /api/generate, /api/health)
backend/preprocess.py   OpenCV: decode, denoise, threshold, crop, resize, shape analysis
backend/prompt_builder.py  Sketch → prompt (heuristics + optional Claude vision), style presets
backend/generators.py   Stability AI provider + local Demo provider
templates/index.html    UI
static/js/app.js        Canvas drawing, upload, API calls, preview, download
static/css/style.css
tests/test_app.py
```

## Team mapping

| Member | Area |
|--------|------|
| Dheeraj Suriya | Canvas/upload, `backend/preprocess.py` |
| Sinchana BK | `backend/prompt_builder.py`, `backend/generators.py` |
| Dhanalakshmi I D | `templates/`, `static/` UI + error handling |
| Prem | `app.py` integration, `tests/` |

## Troubleshooting

- *"Demo mode"* shown → no `STABILITY_API_KEY` set; the app is working, just not using real AI.
- *Port in use* → set `PORT=5001` in `.env`.
- *Blank sketch error* → draw darker/larger strokes, or upload a clearer image.
