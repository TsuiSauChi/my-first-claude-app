# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The repo holds two small apps that don't depend on each other. Each folder has its own README with the full details.

- `image-upload/`: a FastAPI service that converts uploaded images to WebP (Python, Pillow).
- `weather/`: **Rain Check**, a one-file dashboard showing live weather in all 197 capitals (HTML/CSS/JS, Open-Meteo API, no build step).

## image-upload

Run these from `image-upload/`:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload          # http://localhost:8000
.venv/bin/pytest                                 # all tests
.venv/bin/pytest tests/test_upload.py::test_empty_file_returns_400   # one test
```

There is no linter or formatter configured.

How the code fits together:
- `app/convert.py`: `to_webp(bytes) -> WebPResult` holds all the image logic. It takes bytes in and returns bytes out, with no HTTP, so it can be tested directly. It raises `UnsupportedImage` for anything it refuses, and `main.py` maps that to a 415. Size, frame and pixel limits are checked from the file header before any pixels are decoded. Read the constants at the top before changing any limit.
- `app/storage.py`: `LocalStorage` provides `save(bytes) -> id` (an atomic write through a temp file plus `os.replace`) and `url_for(id)`. To change the backend (e.g. S3), keep those two methods.
- `app/main.py`: `create_app(storage_dir)` is the factory, and tests build the app with a `tmp_path`. The `BodySizeLimit` ASGI middleware rejects bodies over 15 MB while they stream in, because Starlette spools the whole upload to disk before the handler runs. A check inside the handler alone would come too late. `/upload` is a sync `def`, so it runs in the threadpool, and a `BoundedSemaphore` (`CONVERT_CONCURRENCY` env) limits how many conversions run at once. Converted images are served from `/images` with immutable cache headers.
- Environment: `STORAGE_DIR` (default `./storage`, which git ignores) and `CONVERT_CONCURRENCY`. `tests/conftest.py` sets `STORAGE_DIR` before `app.main` is imported, so tests never create `./storage`. Keep that order.

## weather (Rain Check)

Everything is in `weather/index.html`. To run it, open the file in a browser, or serve it (`cd weather && python3 -m http.server 8080`) if the browser blocks `fetch` from `file://`. It needs internet access.

Structure inside the file:
- **Data:** `RAW` is a pipe-delimited list (`ISO|country|capital|lat|lon`) parsed into `COUNTRIES`. `load()` fetches current weather from Open-Meteo in batches of 50 coordinates, all in parallel, and re-runs every 15 minutes or when **Refresh now** is pressed. WMO weather codes are mapped to labels in `WMO`, and `kind()` classifies them as rain, storm, snow or dry.
- **UI state:** the `state` object holds filter, sort, unit and search query, and `render()` redraws the summary strip and the card grid from it. The °C/°F choice is saved in `localStorage` under `rc-unit`.
- **Themes (light / dark / pink):** colours are CSS custom properties on `:root`, overridden per `:root[data-theme="…"]`.
  - A script in `<head>` defines `window.rcTheme` (`names`, `choice`, `saved()`, `os()`) and sets `data-theme` before first paint, so the page doesn't flash the wrong theme. The theme switch script at the end of the page uses `rcTheme`; don't add globals shared between the two scripts.
  - Precedence: a choice made in this tab (`rcTheme.choice`, which still works when storage is blocked), then the saved choice (`localStorage` key `rc-theme`), then the OS setting. A `storage` listener keeps other open tabs in step.
  - The dark palette appears twice: once under `:root[data-theme="dark"]` and once as a no-JS fallback (`@media (prefers-color-scheme: dark) :root:not([data-theme])`). Change both together.
  - The `--{light,dark,pink}-{ground,accent}` tokens also colour the theme-switch swatches.
- Buttons share one pill style (`.chip, .unit, .toggle, #refresh`). The header has a smaller size for its buttons.

To check UI changes headlessly, use Python Playwright (`pip install playwright && playwright install --with-deps chromium`). The system Node is v12, which is too old for Node Playwright.
