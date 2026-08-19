# Vein Server Docker Image - Claude Instructions

## Project Overview

Docker image for running a Vein dedicated server. Built on `cm2network/steamcmd:root`.

**Source files live in `app/`:**
- `dockerfile` — main Dockerfile
- `entrypoint.py` — server install, config generation, launch, and shutdown/backup logic
- `http-forwarder.py` — forwards `0.0.0.0:9080` → `localhost:8080` (game HTTP API). Required, not optional: the game binds its HTTP API to `127.0.0.1` only, so Docker's port publish cannot reach it without this relay. Don't remove it without an alternative that solves the same loopback-bind problem.
- `backup.py` — save backup logic
- `backup-cron.sh` — cron wrapper for backups
- `requirements.txt` — Python deps (requests, etc.)

## Key Conventions

- All server configuration is driven by environment variables, documented in `Readme.md`.
- `entrypoint.py` reads env vars, writes `Game.ini` / `Engine.ini`, runs steamcmd, then launches the server binary as a child process (not exec'd).
- `CVAR_` prefixed env vars are written to `Engine.ini` under `[ConsoleVariables]`.
- Steam App ID: `2131400` for both stable and experimental (experimental just adds `-beta experimental` to steamcmd).
- Experimental branch: set `EXPERIMENTAL_BUILD=True`; steamcmd gets `-beta experimental` and uses `EXPERIMENTAL_APPID`.
- The Dockerfile `ENTRYPOINT` is a bash one-liner that: fixes volume ownership → sets up backup cron → starts cron → execs `entrypoint.py`.
- `entrypoint.py`'s `start_server()` keeps the server as a child process and installs SIGTERM/SIGINT handlers so it can forward the signal, wait for the server to exit (or kill it after `SHUTDOWN_GRACE_SECONDS`), then run a pre-stop backup (`BACKUP_ON_STOP`) before the container actually exits. Don't switch this back to `os.execv()` for the server launch — that would remove the ability to hook shutdown.
- The HTTP forwarder's CORS headers are redundant when the consumer (e.g. `vein-server-info`) already proxies server-side through its own nginx — but the relay itself (0.0.0.0:9080 -> 127.0.0.1:8080) is not optional, see above.

## Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 7777 | UDP | Game traffic (`GAME_PORT`) |
| 27015 | UDP | Steam query (`GAME_SERVER_QUERY_PORT`) |
| 9080 | TCP | HTTP API forwarder — only listens if `HTTP_PORT` is set; map this, not 8080 |

## Adding New Environment Variables

1. Add `ENV VAR_NAME=default` in `dockerfile` near related vars.
2. Read with `os.getenv('VAR_NAME', 'default')` in `entrypoint.py`.
3. Update the env var table in `Readme.md`.
