# Changelog

## [1.3.1] - 2026-08-19

### Changes
- Revert removal of the HTTP forwarder (http-forwarder.py). The Vein game server binds its HTTP API to 127.0.0.1 only inside the container network namespace; confirmed against the actual deployment that a direct port publish to 8080 gets connection-refused both externally and from another host on the same docker network - the forwarder relaying 0.0.0.0:9080 -> 127.0.0.1:8080 is required, not optional. The CORS half of the forwarder is still redundant when the consumer already proxies server-side (its own nginx, for example), but the relay itself is load-bearing. Map port 9080, not 8080.

## [1.3.0] - 2026-08-19

### Changes
- Add pre-stop backup: server now runs as a child process (not exec'd) so SIGTERM/SIGINT is caught, the server is given SHUTDOWN_GRACE_SECONDS to exit cleanly, then a backup runs before the container exits (BACKUP_ON_STOP, default true). Previously only the cron-scheduled backup existed.
- Remove the HTTP forwarder/CORS proxy (http-forwarder.py, port 9080). It solved two problems this deployment does not have: CORS is already handled by vein-server-info's own nginx proxy (server-to-server calls are never subject to CORS), and the claimed localhost-only HTTP API bind is contradicted by the current production setup, which maps the game's HTTP port straight through with no forwarder. HTTP_PORT now maps directly, one fewer moving part on startup.

  **Correction (see 1.3.1 above): this was wrong. The localhost-only bind claim was confirmed accurate, and the forwarder was restored.**

## [1.2.0] - 2025-12-09

### Changes
- delete steamapps if fails (df893f0)
- Increas tries (ab388f7)
- improve steam startup (8c79e22)
- Remove the server api (c8b863e)
- Fix engine.ini (baaee21)
- Dont add loggin settings (ee010fd)
- update ini generation (0fe0743)
- fix duplicate keys issue (65d1c34)
- add backup settings as configurable options (e50df56)
- add backup feature (b6d6629)
- fix start order (5d758ef)
- change start order (6925545)
- more logging and fixes to restart the process (142687e)
- process fixes (0571c1c)
- logging (69e70cf)
- add healthcheck (3b0edff)
- try to fix the restart command (5d33be0)
- add headers (fce437a)
- Try fix restart, notify to discord on server start (0a8b698)
- Add request (bd186d8)
- Update the update, send discord notification if configured (8b61cd3)
- add ability to restart and update vein (5218c69)
- add restart to api (10e9e59)
- More fixes (b3dc981)
- Update dockerfile (b3bb9d3)
- server api draft (2f4296b)
- remove allow creds header (2be6f3b)
- use python3 instead of python3 minimal (4b7d718)
- Replace forwarded with python version, add cors headers (7130f3d)
- attempt to fix multiple key issue (e30c867)


## [1.1.0] - 2025-11-15

### Changes
- Try fix build (a19bda5)
- Forwarder: Increase the check time and add delay between checks (c362c1a)
- Update port forwarder to different port, update readme. Add latest dev tag (5185229)
- Add http temporary http forwarder (595048e)
- Update changelog (ce14c5d)
- Update label (3dde657)
- Exclude dev builds from latest (821f6a0)
- Rename the image (9262b81)
- Initial commit (be11997)


## [1.0.0] - 2025-11-15

### Added
- Initial release of Vein Dedicated Server Docker image
