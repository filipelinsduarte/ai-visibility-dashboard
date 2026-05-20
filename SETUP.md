# Local Setup

> Copy-paste guide for spinning up this dashboard on your laptop. Every command in this doc has been tested end-to-end on a fresh clone (macOS, Python 3.14). If something doesn't work, jump to the **Troubleshooting** section at the bottom.

---

## What you're setting up

A self-contained HTML dashboard you view in your browser at `http://localhost:8080/dashboard.html`. No npm install, no database, no Docker. The dashboard's data is already baked into the HTML file (see `_AIM_SNAPSHOT` on line ~5214 of `dashboard.html`) — you only need to regenerate it if you want fresh numbers from the Peekaboo API.

---

## Prerequisites

You need **one** thing:

- **Python 3** (any version 3.6+ — check with `python3 --version`)

That's it. No pip install. No Node. The scripts use Python stdlib only.

Optional (only for regenerating data or running tests):
- A Peekaboo API key + Brand ID (from aipeekaboo.com/settings/integrations)
- Node.js + Playwright (only if you want to run UI tests — see `TDD_PHILOSOPHY.md`)

---

## Spin it up in 3 commands

```bash
git clone https://github.com/filipelinsduarte/ai-visibility-dashboard.git
cd ai-visibility-dashboard
python3 -m http.server 8080
```

Then open: **http://localhost:8080/dashboard.html**

That's the whole setup. The dashboard should render with data already (the snapshot is committed into `dashboard.html`).

To stop the server: `Ctrl+C` in the terminal where it's running.

---

## Verify it worked

You should see:
- The sidebar on the left with nav items (Overview, Competitors, Prompts, Sources, etc.)
- Numbers in the cards at the top of the Overview page (visibility %, position, sentiment)
- At least one chart rendering (the daily trend line chart)

If you see the sidebar but **everything else is blank**, jump to **Troubleshooting → "Dashboard renders but data is missing"** below.

---

## Optional: refresh the data from the live API

The committed `dashboard.html` already has data baked in. To pull fresh numbers from the Peekaboo API:

```bash
export PEEKABOO_BRAND_ID="your-brand-uuid"
export PEEKABOO_API_KEY="your-api-key"
cd scripts
python3 generate_snapshot.py
```

This takes **10–20 minutes** (API rate-limited to 18 req/min). When it finishes, refresh the browser tab.

If the Competitors view looks incomplete after that, also run:
```bash
python3 refresh_brand_vis.py
```

---

## Optional: change the port

Port 8080 is the default in this doc, but you can use any port:

```bash
python3 -m http.server 8090     # use 8090 instead
```

Then open `http://localhost:8090/dashboard.html` (matching the port you chose).

---

## Troubleshooting

These are the failure modes we've actually seen. If yours isn't here, paste the error into an AI assistant (Claude / ChatGPT) along with a screenshot of your browser DevTools console.

### "Address already in use" / "Port 8080 in use"

Something else is already running on port 8080. Two options:

**Option A — use a different port** (easiest):
```bash
python3 -m http.server 8090
```

**Option B — kill the other server**. First find what's using the port:
```bash
lsof -i :8080
```
Then kill the process by its PID:
```bash
kill <PID>     # replace <PID> with the number you saw
```

If `kill` doesn't stop it, use `kill -9 <PID>`.

### Dashboard renders but data is missing (blank cards / no charts)

The most common cause: **your browser is showing a cached version** of an older file. Force a hard refresh:

- **macOS Chrome/Safari/Edge**: `Cmd + Shift + R`
- **Windows/Linux**: `Ctrl + Shift + R`
- Or: open the page in an Incognito/Private window

If that doesn't fix it, open **DevTools → Console** (`Cmd + Option + I` on Mac, `F12` on Windows) and look for red errors. The two we've seen recently:

| Error | What it means | Fix |
|---|---|---|
| `Uncaught SyntaxError` | JS file is broken; nothing in `dashboard.html` runs | Check that you're on the `main` branch and your file isn't corrupted. `git status` should show no changes. |
| `Uncaught ReferenceError: X is not defined` | A required variable is missing from `dashboard.html` | See `README.md` → "Debugging log" for the full story |

### "Command not found: python3"

Python 3 isn't installed (or isn't on your `PATH`).

**macOS**: install via Homebrew (`brew install python3`) or download from python.org.
**Windows**: install from python.org and check "Add Python to PATH" during install.
**Linux**: `sudo apt install python3` (Ubuntu/Debian) or `sudo dnf install python3` (Fedora).

Verify with:
```bash
python3 --version    # expect "Python 3.x.x"
```

### Dashboard opens but charts don't render

Chart.js loads from a CDN (`cdn.jsdelivr.net`). If you're offline or behind a firewall blocking that CDN, charts won't draw but the rest of the dashboard will work.

Check the DevTools **Network** tab — if `chart.umd.min.js` shows `(failed)` or `(blocked)`, that's the cause.

**Fix**: connect to the internet, or download Chart.js once and update the `<script>` tags at the top of `dashboard.html` to point to a local file.

### "I opened dashboard.html directly (file://) and it's broken"

Don't open the file directly from Finder/Explorer. Some browser features (especially `fetch`, `XMLHttpRequest`, and certain CDN behaviors) are restricted on `file://` URLs.

**Always serve via** `python3 -m http.server` and open `http://localhost:8080/dashboard.html`.

### `generate_snapshot.py` says "PEEKABOO_BRAND_ID is required"

You didn't `export` the env vars before running the script, or you started a new terminal tab and the exports got lost.

In the **same terminal** where you'll run the script:
```bash
export PEEKABOO_BRAND_ID="your-brand-uuid"
export PEEKABOO_API_KEY="your-api-key"
python3 scripts/generate_snapshot.py
```

To make them persist across terminal sessions, add the two `export` lines to your `~/.zshrc` (macOS Catalina+) or `~/.bashrc`.

### `generate_snapshot.py` runs but the dashboard still shows old data

The script writes to `dashboard.html` in your current directory by default. If you ran it from `scripts/`, it may have written to `scripts/dashboard.html` (a no-op file) instead of the repo root.

**Fix** — be explicit about the target:
```bash
DASHBOARD_PATH=../dashboard.html python3 scripts/generate_snapshot.py
```

Or run it from the repo root:
```bash
python3 scripts/generate_snapshot.py
```

Verify the file timestamp changed:
```bash
ls -la dashboard.html
```

### "I made changes and now something's broken"

The dashboard has no tests yet (see `TDD_PHILOSOPHY.md` — this is the next thing to fix). For now, the fastest way to recover:

```bash
git status                 # see what changed
git diff dashboard.html    # see the actual diff
git restore dashboard.html # ⚠️ DISCARDS your changes — only if you don't want them
```

If you do want to keep your changes but they don't work, the diagnostic checklist is:

1. **DevTools console** — any red errors?
2. **DevTools network** — did anything fail to load?
3. **`git diff dashboard.html`** — does the diff look like what you intended?
4. Read the **`README.md` → "Debugging log"** section for a worked example of the exact debugging path.

---

## Verifying your setup is complete

Run this checklist (all should pass):

```bash
# 1. Python works
python3 --version

# 2. Repo is clean
git status

# 3. dashboard.html exists and is big (~16MB with snapshot baked in)
ls -lh dashboard.html

# 4. Server starts (Ctrl+C to stop after seeing the listening message)
python3 -m http.server 8080
```

Then in the browser:

```bash
# 5. Server responds with the file (run in a separate terminal)
curl -s -o /dev/null -w "HTTP %{http_code} - %{size_download} bytes\n" http://localhost:8080/dashboard.html
# Expected: HTTP 200 - ~16400000 bytes
```

---

## What comes next

Once it's running:

- **Read `TEARDOWN.md`** for the high-level state of this repo.
- **Read `TDD_PHILOSOPHY.md`** for the testing strategy (especially relevant when making changes with AI tools).
- **Read `README.md` → "Debugging log"** for the worked example of fixing a real issue.
