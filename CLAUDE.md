# Vein Server Docker Image - Claude Instructions

## Project Overview

Docker image for running a Vein dedicated server. Built on `cm2network/steamcmd:root`.

**Source files live in `app/`:**
- `dockerfile` — main Dockerfile
- `entrypoint.py` — server install, config generation, and launch logic
- `http-forwarder.py` — forwards `0.0.0.0:9080` → `localhost:8080` (game HTTP API)
- `backup.py` — save backup logic
- `backup-cron.sh` — cron wrapper for backups
- `requirements.txt` — Python deps (requests, etc.)

## Key Conventions

- All server configuration is driven by environment variables, documented in `Readme.md`.
- `entrypoint.py` reads env vars, writes `Game.ini` / `Engine.ini`, runs steamcmd, then execs the server binary.
- `CVAR_` prefixed env vars are written to `Engine.ini` under `[ConsoleVariables]`.
- Steam App IDs: stable = `2131400`, experimental = `2600250`.
- Experimental branch: set `EXPERIMENTAL_BUILD=True`; steamcmd gets `-beta experimental` and uses `EXPERIMENTAL_APPID`.
- The Dockerfile `ENTRYPOINT` is a bash one-liner that: fixes volume ownership → sets up backup cron → starts cron → starts http-forwarder → execs `entrypoint.py`.

## Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 7777 | UDP | Game traffic (`GAME_PORT`) |
| 27015 | UDP | Steam query (`GAME_SERVER_QUERY_PORT`) |
| 9080 | TCP | HTTP API forwarder |

## Adding New Environment Variables

1. Add `ENV VAR_NAME=default` in `dockerfile` near related vars.
2. Read with `os.getenv('VAR_NAME', 'default')` in `entrypoint.py`.
3. Update the env var table in `Readme.md`.
