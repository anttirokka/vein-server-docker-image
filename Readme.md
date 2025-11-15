# Vein Dedicated Server - Docker Image

A Docker container for running a Vein dedicated server with easy configuration through environment variables.

> **📖 Official Documentation**: For detailed information about Vein dedicated servers, see the [Official Vein Dedicated Server Documentation](https://ramjet.notion.site/dedicated-servers)

## Quick Start

### Using Docker Run

```bash
docker run -d \
  --name vein-server \
  -p 7777:7777/udp \
  -p 27015:27015/udp \
  -e SERVER_NAME="My Vein Server" \
  -e MAX_PLAYERS=16 \
  -v /path/to/server/data:/home/steam/vein-server \
  ghcr.io/anttirokka/vein-server-docker-image:latest
```

### Using Docker Compose

```yaml
version: '3.8'

services:
  vein-server:
    image: ghcr.io/anttirokka/vein-server-docker-image:latest
    container_name: vein-server
    ports:
      - "7777:7777/udp"  # Game port
      - "27015:27015/udp"  # Query port
      - "8080:8080/tcp"  # HTTP API (optional)
    environment:
      - SERVER_NAME=My Vein Server
      - MAX_PLAYERS=16
      - SERVER_PUBLIC=True
      - HTTP_PORT=8080
      - GAME_PORT=7777
      - GAME_SERVER_QUERY_PORT=27015
    volumes:
      - ./vein-data:/home/steam/vein-server
    restart: unless-stopped
```

## Environment Variables

### Basic Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_NAME` | "Vein Docker Server" | Name of your server |
| `MAX_PLAYERS` | 16 | Maximum number of players |
| `SERVER_PUBLIC` | True | Whether server appears in public server list |
| `SERVER_PASSWORD` | "" | Server password (empty = no password) |
| `SERVER_BIND_ADDR` | 0.0.0.0 | Server bind address |

### Network Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GAME_PORT` | 7777 | UDP port for game traffic |
| `GAME_SERVER_QUERY_PORT` | 27015 | UDP port for Steam queries |
| `HTTP_PORT` | "" | TCP port for HTTP API (empty = disabled) |
| `SERVER_MULTIHOME_IP` | "" | Specific IP to bind to |

### Admin Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPER_ADMIN_STEAM_IDS` | "" | Comma-separated list of Super Admin Steam IDs |
| `ADMIN_STEAM_IDS` | "" | Comma-separated list of Admin Steam IDs |

Example:
```bash
SUPER_ADMIN_STEAM_IDS="76561198012345678,76561198087654321"
ADMIN_STEAM_IDS="76561198111111111,76561198222222222"
```

### Server Features

| Variable | Default | Description |
|----------|---------|-------------|
| `VAC_ENABLED` | 0 | Enable Valve Anti-Cheat (0=disabled, 1=enabled) |
| `HEARTBEAT_INTERVAL` | 5.0 | Server heartbeat interval in seconds |
| `GS_SHOW_SCOREBOARD_BADGES` | "" | Show scoreboard badges (0=disabled, 1=enabled) |

### Discord Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_WEBHOOK_URL` | "" | Discord webhook for chat messages |
| `DISCORD_ADMIN_WEBHOOK_URL` | "" | Discord webhook for admin notifications |

### Console Variables (CVARs)

Set any Vein console variable by prefixing it with `CVAR_`:

```bash
CVAR_vein.PvP=True
CVAR_vein.TimeMultiplier=16
CVAR_vein.DifficultyMultiplier=1.5
```

### Steam Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `STEAM_USER` | anonymous | Steam username (use anonymous for public servers) |
| `STEAM_PASS` | "" | Steam password |
| `STEAM_AUTH` | "" | Steam Guard authentication code |

## HTTP API Configuration

Enable the HTTP API to query server data:

```bash
docker run -d \
  --name vein-server \
  -p 7777:7777/udp \
  -p 27015:27015/udp \
  -p 8080:8080/tcp \
  -e HTTP_PORT=8080 \
  -e SERVER_NAME="My Vein Server" \
  vein-server:latest
```

**⚠️ Security Warning:** The HTTP API has no built-in authentication. If you expose this port publicly, consider using a reverse proxy with authentication or an intermediate server to handle requests securely.

Once enabled, you can query the server at `http://your-server-ip:8080` for JSON-formatted data.

## Volume Mounts

Mount volumes to persist server data:

```bash
-v /path/to/server/data:/home/steam/vein-server
```

This will preserve:
- Server installation files
- Configuration files
- Save game data
- Logs

## Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 7777 | UDP | Game traffic (configurable via `GAME_PORT`) |
| 27015 | UDP | Steam query port (configurable via `GAME_SERVER_QUERY_PORT`) |
| 8080 | TCP | HTTP API (optional, configurable via `HTTP_PORT`) |


### Available Tags

- `latest` - Latest stable release
- `X.Y.Z` - Specific version (e.g., `1.0.0`)
- `main-<sha>` - Development builds from main branch

### Using Specific Versions

```bash
# Use latest version
docker pull ghcr.io/anttirokka/vein-server-docker-image:latest

# Use specific version
docker pull ghcr.io/anttirokka/vein-server-docker-image:1.0.0
```

## Configuration File Preservation

The entrypoint script **preserves existing configurations** in `Game.ini` and `Engine.ini`.

- Environment variables will update their specific settings
- Manual changes to other settings in the INI files will be preserved
- This allows you to manually edit configuration files while still managing core settings through environment variables

## Advanced Configuration

### Custom Configuration Files

You can manually edit configuration files after the first run:

1. Start the container once to generate initial configs
2. Stop the container
3. Edit files in the mounted volume:
   - `Vein/Saved/Config/LinuxServer/Game.ini`
   - `Vein/Saved/Config/LinuxServer/Engine.ini`
4. Restart the container

Environment variables will update only their managed settings, leaving your custom configurations intact.

### Multiple Servers

Run multiple Vein servers by using different ports and container names:

```bash
# Server 1
docker run -d --name vein-server-1 \
  -p 7777:7777/udp -p 27015:27015/udp \
  -e SERVER_NAME="Server 1" \
  vein-server:latest

# Server 2
docker run -d --name vein-server-2 \
  -p 7778:7777/udp -p 27016:27015/udp \
  -e SERVER_NAME="Server 2" \
  -e GAME_PORT=7778 -e GAME_SERVER_QUERY_PORT=27016 \
  vein-server:latest
```

## Logs

View container logs:

```bash
docker logs -f vein-server
```

Server logs are stored in:
```
/home/steam/vein-server/Vein/Saved/Logs/
```

## Troubleshooting

### Server not appearing in server list

- Ensure `SERVER_PUBLIC=True`
- Check that ports 7777/UDP and 27015/UDP are properly forwarded
- Verify firewall rules allow UDP traffic

### Can't connect to server

- Verify ports are correctly mapped and forwarded
- Check if `SERVER_BIND_ADDR` is set correctly
- Ensure `SERVER_PASSWORD` matches if set

### Server crashes on startup

- Check logs: `docker logs vein-server`
- Verify environment variables are correctly formatted
- Ensure sufficient system resources (RAM, CPU)

### HTTP API not working

- Verify `HTTP_PORT` is set and the TCP port is exposed
- Check that the port is not blocked by firewall
- The HTTP API requires the game to be fully started

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Development Workflow

1. Create a feature branch
2. Make your changes
3. Test locally using `./scripts/build-local.sh`
4. Submit a pull request
5. After merge, the image is automatically built and versioned

## License

This project is provided as-is

## Credits

- Original repository: [JMeta0/vein-docker-server](https://github.com/JMeta0/vein-docker-server)

## Links

- [Official Vein Dedicated Server Documentation](https://ramjet.notion.site/dedicated-servers)
- [Vein Game Store Page](https://store.steampowered.com/app/1975370/Vein/)
- [SteamCMD Docker Image](https://github.com/CM2Walki/steamcmd)
