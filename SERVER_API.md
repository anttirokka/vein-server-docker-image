# Vein Server Admin API

This API provides endpoints for monitoring server performance and managing configuration files.

## Features

- **Server Metrics**: Real-time CPU, memory, and disk usage
- **Configuration Management**: Read and update Game.ini and Engine.ini
- **Log Access**: View server logs without SSH access (protected by API key)
- **Health Check**: Simple endpoint to verify API is running
- **Optional**: Can be disabled via environment variable

## Quick Start

The Admin API can be enabled when starting your Vein server Docker container.

### Enable the API

```yaml
environment:
  - ADMIN_API_ENABLED=true  # Set to true to enable the API
  - ADMIN_API_PORT=9081      # Optional: custom port (default: 9081)
  - ADMIN_API_KEY=your-secret-key-here  # Required for security
```

### Port Configuration

- **Default Port**: 9081 (inside container)
- **Environment Variable**: `ADMIN_API_PORT`
- **Docker Compose**: Map to host port (e.g., `8856:9081`)

### Security

**IMPORTANT**: Always set an API key to protect all endpoints:

```yaml
environment:
  - ADMIN_API_KEY=your-secret-key-here
```

Include the key in requests:
- Header: `X-API-Key: your-secret-key-here`
- Query parameter: `?api_key=your-secret-key-here`

**All endpoints (including read-only ones like metrics and logs) require the API key when configured.**

## API Endpoints

### Health Check

```bash
GET /health
```

Returns API status and version.

**Example:**
```bash
curl http://localhost:8856/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-27T12:00:00.000000",
  "version": "1.0.0"
}
```

---

### Server Metrics

```bash
GET /api/metrics
```

Get real-time server performance metrics.

**Example:**
```bash
curl http://localhost:8856/api/metrics
```

**Response:**
```json
{
  "server_running": true,
  "timestamp": "2025-11-27T12:00:00.000000",
  "process": {
    "pid": 1234,
    "cpu_percent": 45.2,
    "memory_mb": 2048.5,
    "memory_percent": 12.8,
    "uptime_seconds": 3600,
    "uptime_formatted": "1h 0m 0s"
  },
  "system": {
    "cpu_percent": 25.0,
    "memory_total_gb": 16.0,
    "memory_used_gb": 8.5,
    "memory_percent": 53.1,
    "disk_total_gb": 500.0,
    "disk_used_gb": 250.0,
    "disk_percent": 50.0
  }
}
```

---

### Get Game Configuration

```bash
GET /api/config/game
```

Retrieve current Game.ini settings.

**Example:**
```bash
curl http://localhost:8856/api/config/game
```

**Response:**
```json
{
  "file": "Game.ini",
  "path": "/home/steam/vein-server/Vein/Saved/Config/LinuxServer/Game.ini",
  "config": {
    "/Script/Engine.GameSession": {
      "MaxPlayers": "16"
    },
    "/Script/Vein.VeinGameSession": {
      "ServerName": "\"My Server\"",
      "bPublic": "True",
      "HTTPPort": "8080"
    }
  }
}
```

---

### Get Engine Configuration

```bash
GET /api/config/engine
```

Retrieve current Engine.ini settings.

**Example:**
```bash
curl http://localhost:8856/api/config/engine
```

---

### Update Game Configuration

```bash
PUT /api/config/game
PATCH /api/config/game
```

Update Game.ini settings. Requires API key if configured.

**Headers:**
```
Content-Type: application/json
X-API-Key: your-secret-key-here
```

**Body:**
```json
{
  "config": {
    "/Script/Engine.GameSession": {
      "MaxPlayers": "32"
    },
    "/Script/Vein.VeinGameSession": {
      "ServerName": "\"New Server Name\""
    }
  }
}
```

**Example:**
```bash
curl -X PUT http://localhost:8856/api/config/game \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key-here" \
  -d '{
    "config": {
      "/Script/Engine.GameSession": {
        "MaxPlayers": "32"
      }
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Game.ini updated successfully",
  "backup": "/home/steam/vein-server/Vein/Saved/Config/LinuxServer/Game.ini.backup.1732708800",
  "note": "Server restart required for changes to take effect"
}
```

**Important**: Configuration changes require a server restart to take effect!

---

### Update Engine Configuration

```bash
PUT /api/config/engine
PATCH /api/config/engine
```

Update Engine.ini settings. Works the same as Game.ini updates.

**Example:**
```bash
curl -X PUT http://localhost:8856/api/config/engine \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key-here" \
  -d '{
    "config": {
      "ConsoleVariables": {
        "vein.PvP": "True",
        "vein.TimeMultiplier": "16"
      }
    }
  }'
```

---

### List Log Files

```bash
GET /api/logs
```

Get a list of available log files. **Requires API key.**

**Example:**
```bash
curl -H "X-API-Key: your-secret-key-here" http://localhost:8856/api/logs
```

**Response:**
```json
{
  "logs": [
    {
      "name": "VeinServer.log",
      "path": "/home/steam/vein-server/Vein/Saved/Logs/VeinServer.log",
      "size_bytes": 1048576,
      "size_mb": 1.0,
      "modified": "2025-11-27T12:00:00"
    }
  ]
}
```

---

### Get Log Content

```bash
GET /api/logs/<filename>?lines=100
```

Retrieve log file content. By default returns last 100 lines. **Requires API key.**

**Query Parameters:**
- `lines`: Number of lines to return (default: 100, use 0 for all)

**Example:**
```bash
# Get last 100 lines
curl -H "X-API-Key: your-secret-key-here" http://localhost:8856/api/logs/VeinServer.log

# Get last 500 lines
curl -H "X-API-Key: your-secret-key-here" http://localhost:8856/api/logs/VeinServer.log?lines=500

# Get entire file
curl -H "X-API-Key: your-secret-key-here" http://localhost:8856/api/logs/VeinServer.log?lines=0

# Or use query parameter for API key
curl "http://localhost:8856/api/logs/VeinServer.log?api_key=your-secret-key-here&lines=100"
```

**Response:**
```json
{
  "filename": "VeinServer.log",
  "lines_returned": 100,
  "total_lines": 5000,
  "content": "[2025.11.27-12:00:00:000][  0]LogInit: ..."
}
```

---

## Integration Examples

### Python

```python
import requests

# API Configuration
API_BASE = "http://localhost:8856"
API_KEY = "your-secret-key-here"

# Get server metrics
response = requests.get(f"{API_BASE}/api/metrics")
metrics = response.json()
print(f"CPU: {metrics['process']['cpu_percent']}%")

# Update max players
response = requests.put(
    f"{API_BASE}/api/config/game",
    headers={
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    },
    json={
        "config": {
            "/Script/Engine.GameSession": {
                "MaxPlayers": "32"
            }
        }
    }
)
print(response.json())
```

### JavaScript

```javascript
const API_BASE = 'http://localhost:8856';
const API_KEY = 'your-secret-key-here';

// Get server metrics
async function getMetrics() {
    const response = await fetch(`${API_BASE}/api/metrics`);
    const metrics = await response.json();
    console.log(`CPU: ${metrics.process.cpu_percent}%`);
}

// Update configuration
async function updateConfig() {
    const response = await fetch(`${API_BASE}/api/config/game`, {
        method: 'PUT',
        headers: {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            config: {
                '/Script/Engine.GameSession': {
                    MaxPlayers: '32'
                }
            }
        })
    });
    const result = await response.json();
    console.log(result);
}
```

### Bash/curl

```bash
#!/bin/bash
API_BASE="http://localhost:8856"
API_KEY="your-secret-key-here"

# Get metrics and parse with jq
curl -s "$API_BASE/api/metrics" | jq '.process.cpu_percent'

# Update config
curl -X PUT "$API_BASE/api/config/game" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "/Script/Engine.GameSession": {
        "MaxPlayers": "32"
      }
    }
  }'
```

---

## Docker Compose Example

```yaml
version: '3.8'

services:
  vein-server:
    image: ghcr.io/anttirokka/vein-dedicated-server:latest
    container_name: vein-server
    ports:
      - "7777:7777/udp"     # Game port
      - "27015:27015/udp"   # Query port
      - "8855:9080/tcp"     # Game HTTP API
      - "8856:9081/tcp"     # Admin API
    environment:
      - SERVER_NAME=My Vein Server
      - MAX_PLAYERS=16
      - HTTP_PORT=8080
      - ADMIN_API_ENABLED=true
      - ADMIN_API_PORT=9081
      - ADMIN_API_KEY=change-me-to-something-secure
    volumes:
      - ./vein-data:/home/steam/vein-server
    restart: unless-stopped
```

---

## Monitoring Dashboard

You can build a simple monitoring dashboard using the metrics endpoint:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Vein Server Monitor</title>
    <script>
        async function updateMetrics() {
            const response = await fetch('http://localhost:8856/api/metrics');
            const data = await response.json();

            document.getElementById('cpu').textContent = data.process.cpu_percent.toFixed(1) + '%';
            document.getElementById('memory').textContent = data.process.memory_mb.toFixed(0) + ' MB';
            document.getElementById('uptime').textContent = data.process.uptime_formatted;
        }

        setInterval(updateMetrics, 5000);
        updateMetrics();
    </script>
</head>
<body>
    <h1>Vein Server Status</h1>
    <p>CPU: <span id="cpu">-</span></p>
    <p>Memory: <span id="memory">-</span></p>
    <p>Uptime: <span id="uptime">-</span></p>
</body>
</html>
```

---

## Backup System

The API automatically creates backups before modifying configuration files:

- Backups are stored next to the original file
- Format: `<filename>.backup.<timestamp>`
- Example: `Game.ini.backup.1732708800`

To restore a backup:

```bash
docker exec vein-server cp \
  /home/steam/vein-server/Vein/Saved/Config/LinuxServer/Game.ini.backup.1732708800 \
  /home/steam/vein-server/Vein/Saved/Config/LinuxServer/Game.ini
```

---

## Troubleshooting

### API Not Responding

Check if the admin API is running:

```bash
docker logs vein-server | grep "Admin API"
```

### Permission Denied

Ensure the server has write permissions to config files:

```bash
docker exec vein-server ls -la /home/steam/vein-server/Vein/Saved/Config/LinuxServer/
```

### Config Changes Not Applied

Remember that configuration changes require a server restart:

```bash
docker restart vein-server
```

---

## Security Recommendations

1. **Always set an API key** for production environments - ALL endpoints require it
2. **Always enable explicitly** with `ADMIN_API_ENABLED=true`
3. **Use HTTPS** when exposing the API publicly (use a reverse proxy like nginx or Traefik)
4. **Restrict access** using firewall rules or Docker networks
5. **Rotate API keys** regularly
6. **Monitor access logs** for suspicious activity
7. **Keep the API disabled** when not needed

---

## Future Enhancements

Potential features for future versions:

- Server restart/stop controls
- Player management (kick, ban)
- Real-time log streaming via WebSocket
- Scheduled configuration changes
- Metrics history and graphs
- Backup/restore management
- Multiple server support

---

## Support

For issues or feature requests, please open an issue on the GitHub repository.
