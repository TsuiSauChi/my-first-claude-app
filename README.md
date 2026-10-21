# my-first-claude-app

Two small, separate apps built with Claude Code.

| App | What it is | Stack |
|---|---|---|
| [`image-upload/`](image-upload/) | A web service that takes an image upload, converts it to WebP, saves it and returns its URL. It comes with a simple upload page. | Python, FastAPI, Pillow |
| [`weather/`](weather/) | **Rain Check**: a one-page dashboard that shows the live weather in every country's capital and whether it is raining there. | HTML, CSS, JavaScript, Open-Meteo API |

## Quick start

**Image upload** (needs Python 3.9+):

```bash
cd image-upload
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload
# then open http://localhost:8000
```

**Rain Check** (needs only a browser and internet): open `weather/index.html` in your browser.

Each folder's README has the full instructions and details.

## Emoji log

One new emoji for every push to GitHub.

- 🤖 2026-10-21 — Add CLAUDE.md, code-reviewer subagent and push-emoji skill
- 🔀 2026-10-21 — Add push emoji 🤖 to README
- 🧹 2026-10-21 — Add PostToolUse hook that auto-formats edited files
