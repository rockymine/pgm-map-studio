---
description: Launch and restart the PGM Map Studio (Flask app) for browser verification
---

# Run Studio Skill

## Overview

PGM Map Studio is a Flask app. It runs on **http://localhost:7892**. The browser tab for testing is typically already open at that address.

## Python interpreter

The project venv lives on the VirtualBox shared folder (`/media/sf_repos/…/.venv`) and its binaries cannot be executed from Linux (Protocol error). Use the local venv at `/root/ctw-venv` instead, which has all requirements installed.

If `/root/ctw-venv` does not have the package, install it once:
```bash
/root/ctw-venv/bin/pip install -e /media/sf_repos/pgm-map-studio -q
```

## Starting the server (fresh or after restart)

**Step 1 — Kill any existing process on port 7892** (Bash tool):
```bash
fuser -k 7892/tcp 2>/dev/null; sleep 1
```

**Step 2 — Start the server** (Bash tool, `run_in_background: true`):
```bash
/root/ctw-venv/bin/python -c "
from pgm_map_studio.studio import create_app
app = create_app()
app.run(host='0.0.0.0', port=7892, debug=False, use_reloader=False)
"
```

**Step 3 — Wait for it to come up** (Bash tool):
```bash
sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://localhost:7892/
```
Expect `200`. If not, wait another second and retry once.

**Step 4 — Reload the browser tab** using the Chrome automation tools (F5 or navigate to the URL).

## Browser automation

Use `mcp__claude-in-chrome__tabs_context_mcp` first to get the current tab ID. The editor is at `/editor?map=<slug>`, the dashboard at `/`, configure at `/configure?map=<slug>`.

## Notes

- The kill step is safe to run even if no server is running.
- The server does not exit on its own — the background task notification will never fire during normal operation. Just wait 3 seconds and proceed.
- Config is stored at `~/.config/pgm-map-studio/config.json` (maps_folder, output_folder).
- The old CTW viewer runs on port 7891 — both can run simultaneously.
