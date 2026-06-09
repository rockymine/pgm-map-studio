---
description: Launch and restart the PGM Map Studio (Flask app) for browser verification
---

# Run Studio Skill

## Overview

PGM Map Studio is a Flask app. It runs on **http://localhost:7892**. The browser tab for testing is typically already open at that address.

## Starting / restarting the server

Use the project shell wrapper (Bash tool):
```bash
/media/sf_repos/pgm-map-studio/tools/studio-dev.sh restart
```

This calls `tools/run_studio_dev.py` with `--host 0.0.0.0 --port 7892` using `/root/ctw-venv/bin/python`. It writes a PID file to `.tmp/studio-dev-7892.pid` and blocks until the server responds.

If `/root/ctw-venv` does not have the package installed, install it first:
```bash
/root/ctw-venv/bin/pip install -e /media/sf_repos/pgm-map-studio -q
```

## Other commands

```bash
/media/sf_repos/pgm-map-studio/tools/studio-dev.sh status   # check if running
/media/sf_repos/pgm-map-studio/tools/studio-dev.sh stop     # stop cleanly
```

## Reloading the browser tab

After the server is up, reload the tab using the Chrome automation tools (navigate to the URL). The editor is at `/editor?map=<slug>`, the dashboard at `/`, sketch at `/sketch?id=<id>`.

Use `mcp__claude-in-chrome__tabs_context_mcp` first to get the current tab ID.

## Notes

- `restart` stops any running instance (by PID) then starts a fresh one — no need for `fuser`.
- The server does not exit on its own. `studio-dev.sh` returns as soon as the server is HTTP-ready.
- Config is stored at `~/.config/pgm-map-studio/config.json` (maps_folder, output_folder).
- The old CTW viewer runs on port 7891 — both can run simultaneously.
