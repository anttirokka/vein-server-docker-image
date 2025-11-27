#!/usr/bin/env python3
"""
Server API for Vein Server - Provides endpoints for server metrics and config management.
Runs alongside the game server and http-forwarder.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import configparser
import psutil
import time
import signal
import subprocess
import requests
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
# Enable CORS with explicit configuration
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-API-Key", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": False
    }
})

# Configuration paths
CONFIG_PATH = os.getenv('CONFIG_PATH', '/home/steam/vein-server/Vein/Saved/Config/LinuxServer')
SERVER_PATH = os.getenv('SERVER_PATH', '/home/steam/vein-server')
LOG_DIR = os.path.join(SERVER_PATH, 'Vein/Saved/Logs')
APPID = os.getenv('APPID', '2131400')
STEAMCMD_PATH = '/home/steam/steamcmd/steamcmd.sh'

# API Key for protected operations (optional security)
API_KEY = os.getenv('SERVER_API_KEY', '')
# Port configuration
SERVER_API_PORT = int(os.getenv('SERVER_API_PORT', '9081'))
# Enable/disable API
SERVER_API_ENABLED = os.getenv('SERVER_API_ENABLED', 'false').lower() == 'true'
# Discord webhooks
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
DISCORD_ADMIN_WEBHOOK_URL = os.getenv('DISCORD_ADMIN_WEBHOOK_URL', '')


def require_api_key(f):
    """Decorator to require API key for protected operations."""
    def decorated_function(*args, **kwargs):
        if not API_KEY:
            return f(*args, **kwargs)

        provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if provided_key != API_KEY:
            return jsonify({'error': 'Unauthorized', 'message': 'Invalid or missing API key'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


def read_ini_file(filepath):
    """Read INI file and return as dictionary."""
    if not os.path.exists(filepath):
        return None

    config = configparser.RawConfigParser()
    config.optionxform = str  # Preserve case
    config.read(filepath)

    result = {}
    for section in config.sections():
        result[section] = dict(config.items(section))

    return result


def write_ini_file(filepath, data):
    """Write dictionary to INI file."""
    config = configparser.RawConfigParser()
    config.optionxform = str  # Preserve case

    for section, items in data.items():
        if not config.has_section(section):
            config.add_section(section)
        for key, value in items.items():
            config.set(section, key, value)

    with open(filepath, 'w') as f:
        config.write(f, space_around_delimiters=False)


def get_server_process():
    """Find the Vein server process."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'VeinServer' in proc.info['name'] or \
               (proc.info['cmdline'] and any('VeinServer' in cmd for cmd in proc.info['cmdline'])):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def send_discord_notification(message, title="Vein Server Notification", color=3447003, use_admin=False):
    """Send a notification to Discord webhook.

    Args:
        message: The message content
        title: Embed title
        color: Embed color (decimal) - 3447003 is blue, 15158332 is red, 3066993 is green
        use_admin: If True, use admin webhook; otherwise use regular webhook
    """
    webhook_url = DISCORD_ADMIN_WEBHOOK_URL if use_admin else DISCORD_WEBHOOK_URL

    if not webhook_url:
        return False

    try:
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Server API"
            }
        }

        payload = {
            "embeds": [embed]
        }

        response = requests.post(webhook_url, json=payload, timeout=5)
        return response.status_code in [200, 204]
    except Exception as e:
        print(f"Failed to send Discord notification: {e}")
        return False


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })


@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """Get server performance metrics."""
    proc = get_server_process()

    if not proc:
        return jsonify({
            'error': 'Server process not found',
            'server_running': False
        }), 404

    try:
        # Get process metrics
        cpu_percent = proc.cpu_percent(interval=1)
        memory_info = proc.memory_info()
        memory_percent = proc.memory_percent()
        create_time = proc.create_time()
        uptime_seconds = time.time() - create_time

        # Get system metrics
        system_cpu = psutil.cpu_percent(interval=1)
        system_memory = psutil.virtual_memory()
        system_disk = psutil.disk_usage(SERVER_PATH)

        return jsonify({
            'server_running': True,
            'timestamp': datetime.utcnow().isoformat(),
            'process': {
                'pid': proc.pid,
                'cpu_percent': cpu_percent,
                'memory_mb': memory_info.rss / (1024 * 1024),
                'memory_percent': memory_percent,
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': format_uptime(uptime_seconds)
            },
            'system': {
                'cpu_percent': system_cpu,
                'memory_total_gb': system_memory.total / (1024 ** 3),
                'memory_used_gb': system_memory.used / (1024 ** 3),
                'memory_percent': system_memory.percent,
                'disk_total_gb': system_disk.total / (1024 ** 3),
                'disk_used_gb': system_disk.used / (1024 ** 3),
                'disk_percent': system_disk.percent
            }
        })
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/game', methods=['GET'])
def get_game_config():
    """Get Game.ini configuration."""
    game_ini = os.path.join(CONFIG_PATH, 'Game.ini')
    config = read_ini_file(game_ini)

    if config is None:
        return jsonify({'error': 'Game.ini not found'}), 404

    return jsonify({
        'file': 'Game.ini',
        'path': game_ini,
        'config': config
    })


@app.route('/api/config/engine', methods=['GET'])
def get_engine_config():
    """Get Engine.ini configuration."""
    engine_ini = os.path.join(CONFIG_PATH, 'Engine.ini')
    config = read_ini_file(engine_ini)

    if config is None:
        return jsonify({'error': 'Engine.ini not found'}), 404

    return jsonify({
        'file': 'Engine.ini',
        'path': engine_ini,
        'config': config
    })


@app.route('/api/config/game', methods=['PUT', 'PATCH'])
@require_api_key
def update_game_config():
    """Update Game.ini configuration."""
    game_ini = os.path.join(CONFIG_PATH, 'Game.ini')

    if not os.path.exists(game_ini):
        return jsonify({'error': 'Game.ini not found'}), 404

    data = request.json
    if not data or 'config' not in data:
        return jsonify({'error': 'Invalid request body. Expected {"config": {...}}'}), 400

    try:
        # Backup current config
        backup_path = f"{game_ini}.backup.{int(time.time())}"
        os.system(f'cp "{game_ini}" "{backup_path}"')

        # Update config
        current_config = read_ini_file(game_ini)

        # Merge with updates
        for section, items in data['config'].items():
            if section not in current_config:
                current_config[section] = {}
            current_config[section].update(items)

        write_ini_file(game_ini, current_config)

        return jsonify({
            'success': True,
            'message': 'Game.ini updated successfully',
            'backup': backup_path,
            'note': 'Server restart required for changes to take effect'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/engine', methods=['PUT', 'PATCH'])
@require_api_key
def update_engine_config():
    """Update Engine.ini configuration."""
    engine_ini = os.path.join(CONFIG_PATH, 'Engine.ini')

    if not os.path.exists(engine_ini):
        return jsonify({'error': 'Engine.ini not found'}), 404

    data = request.json
    if not data or 'config' not in data:
        return jsonify({'error': 'Invalid request body. Expected {"config": {...}}'}), 400

    try:
        # Backup current config
        backup_path = f"{engine_ini}.backup.{int(time.time())}"
        os.system(f'cp "{engine_ini}" "{backup_path}"')

        # Update config
        current_config = read_ini_file(engine_ini)

        # Merge with updates
        for section, items in data['config'].items():
            if section not in current_config:
                current_config[section] = {}
            current_config[section].update(items)

        write_ini_file(engine_ini, current_config)

        return jsonify({
            'success': True,
            'message': 'Engine.ini updated successfully',
            'backup': backup_path,
            'note': 'Server restart required for changes to take effect'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs', methods=['GET'])
@require_api_key
def get_logs():
    """Get list of available log files."""
    if not os.path.exists(LOG_DIR):
        return jsonify({'error': 'Log directory not found'}), 404

    logs = []
    for log_file in Path(LOG_DIR).glob('*.log'):
        stat = log_file.stat()
        logs.append({
            'name': log_file.name,
            'path': str(log_file),
            'size_bytes': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
        })

    logs.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify({'logs': logs})


@app.route('/api/logs/<path:filename>', methods=['GET'])
@require_api_key
def get_log_content(filename):
    """Get content of a specific log file."""
    log_path = os.path.join(LOG_DIR, filename)

    if not os.path.exists(log_path) or not log_path.startswith(LOG_DIR):
        return jsonify({'error': 'Log file not found'}), 404

    lines = request.args.get('lines', type=int, default=100)

    try:
        with open(log_path, 'r') as f:
            all_lines = f.readlines()
            content = ''.join(all_lines[-lines:] if lines > 0 else all_lines)

        return jsonify({
            'filename': filename,
            'lines_returned': len(content.splitlines()),
            'total_lines': len(all_lines),
            'content': content
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def format_uptime(seconds):
    """Format uptime in human-readable format."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)


@app.route('/api/server/restart', methods=['POST'])
@require_api_key
def restart_server():
    """Restart the Vein server process."""
    proc = get_server_process()

    if not proc:
        return jsonify({
            'error': 'Server process not found',
            'server_running': False
        }), 404

    try:
        pid = proc.pid
        cmdline = proc.cmdline()

        # Extract any custom server arguments from the original command line
        # The cmdline typically looks like: ['./VeinServer.sh', '-log', '-QueryPort=27015', '-Port=7777', ...]
        server_args = []
        if cmdline:
            # Find VeinServer in the command line and extract args after it
            for i, arg in enumerate(cmdline):
                if 'VeinServer' in arg and i + 1 < len(cmdline):
                    server_args = cmdline[i + 1:]
                    break

        print(f"Sending SIGTERM to server process (PID: {pid})")
        print(f"Original server args: {server_args}")

        # Terminate all child processes first
        try:
            children = proc.children(recursive=True)
            print(f"Found {len(children)} child processes")
            for child in children:
                try:
                    print(f"Terminating child process PID: {child.pid}")
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        # Send SIGTERM to main process for graceful shutdown
        proc.terminate()

        # Wait for process to exit (max 45 seconds)
        print("Waiting for server to shut down...")
        try:
            proc.wait(timeout=45)
            print("Server shut down gracefully")
        except psutil.TimeoutExpired:
            # Force kill children first if graceful shutdown failed
            print("Server didn't shut down gracefully, force killing children...")
            try:
                children = proc.children(recursive=True)
                for child in children:
                    try:
                        child.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            # Force kill main process
            print("Force killing main process...")
            proc.kill()
            try:
                proc.wait(timeout=10)
            except psutil.TimeoutExpired:
                return jsonify({
                    'error': 'Server process could not be terminated',
                    'note': 'You may need to restart the container'
                }), 500

        # Wait a moment for cleanup
        time.sleep(2)

        # Restart the server by directly starting VeinServer
        print("Starting new server process...")
        server_path = os.getenv('SERVER_PATH', '/home/steam/vein-server')
        
        # Build server arguments from environment variables (same as entrypoint.py)
        server_args = ['-log']
        
        if os.getenv('GAME_PORT'):
            server_args.append(f'-Port={os.getenv("GAME_PORT")}')
        if os.getenv('GAME_SERVER_QUERY_PORT'):
            server_args.append(f'-QueryPort={os.getenv("GAME_SERVER_QUERY_PORT")}')
        if os.getenv('SERVER_MULTIHOME_IP'):
            server_args.append(f'-multihome={os.getenv("SERVER_MULTIHOME_IP")}')
        
        # Find the server executable
        vein_server_sh = os.path.join(server_path, 'VeinServer.sh')
        vein_server = os.path.join(server_path, 'VeinServer')
        
        if os.path.isfile(vein_server_sh):
            restart_cmd = [vein_server_sh] + server_args
        elif os.path.isfile(vein_server):
            restart_cmd = [vein_server] + server_args
        else:
            return jsonify({
                'error': 'VeinServer executable not found',
                'note': 'Cannot restart server - executable missing'
            }), 500

        # Start the new server process in the background
        subprocess.Popen(
            restart_cmd,
            cwd=server_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        # Send Discord notification
        server_name = os.getenv('SERVER_NAME', 'Vein Server')
        discord_sent = send_discord_notification(
            f"🔄 **{server_name}** has been restarted via API.\n\n"
            f"**Previous PID:** {pid}\n"
            f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            title="Server Restarted",
            color=3447003,  # Blue
            use_admin=True
        )

        return jsonify({
            'success': True,
            'message': 'Server restart initiated',
            'previous_pid': pid,
            'server_args_detected': server_args,
            'discord_notification_sent': discord_sent,
            'note': 'Server is restarting with flags from environment variables. Custom CMD flags from container start are not preserved.',
            'recommendation': 'Set all server flags via environment variables (GAME_PORT, SERVER_MULTIHOME_IP, etc.) for reliable restarts'
        })
    except psutil.NoSuchProcess:
        return jsonify({
            'error': 'Server process disappeared during restart'
        }), 500
    except Exception as e:
        return jsonify({
            'error': f'Failed to restart server: {str(e)}'
        }), 500


@app.route('/api/server/status', methods=['GET'])
def get_server_status():
    """Get current server status."""
    proc = get_server_process()

    if not proc:
        return jsonify({
            'server_running': False,
            'status': 'offline'
        })

    try:
        return jsonify({
            'server_running': True,
            'status': 'online',
            'pid': proc.pid,
            'uptime_seconds': time.time() - proc.create_time(),
            'uptime_formatted': format_uptime(time.time() - proc.create_time())
        })
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return jsonify({
            'server_running': False,
            'status': 'unknown'
        })


@app.route('/api/server/update', methods=['POST'])
@require_api_key
def update_server():
    """Update the Vein server by restarting it.

    The entrypoint.py automatically runs SteamCMD app_update on every start,
    so restarting the server will check for and install any available updates.

    This can be done with server running - it will be stopped, updated, and restarted.
    """
    proc = get_server_process()

    try:
        print(f"Initiating server update for AppID {APPID}...")

        # If server is running, stop it first
        if proc:
            pid = proc.pid
            print(f"Stopping server (PID: {pid}) for update...")

            proc.terminate()
            try:
                proc.wait(timeout=30)
                print("Server stopped gracefully")
            except psutil.TimeoutExpired:
                print("Force killing server...")
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    return jsonify({
                        'error': 'Could not stop server for update',
                        'note': 'Server process could not be terminated'
                    }), 500

            time.sleep(2)
        else:
            print("Server is not running, will start fresh after update")

        # Start the server via entrypoint, which will run SteamCMD update
        print("Starting entrypoint (will update and start server)...")
        server_path = os.getenv('SERVER_PATH', '/home/steam/vein-server')

        restart_cmd = ['/usr/bin/python3', '/entrypoint.py']

        subprocess.Popen(
            restart_cmd,
            cwd=server_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        # Send Discord notification
        server_name = os.getenv('SERVER_NAME', 'Vein Server')
        notification_msg = f"⬆️ **{server_name}** is being updated via API.\n\n"
        notification_msg += f"**App ID:** {APPID}\n"
        notification_msg += f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
        notification_msg += "The server is restarting and will check for updates automatically."

        discord_sent = send_discord_notification(
            notification_msg,
            title="Server Update Initiated",
            color=3447003,  # Blue
            use_admin=True
        )

        return jsonify({
            'success': True,
            'message': 'Server update initiated',
            'appid': APPID,
            'discord_notification_sent': discord_sent,
            'note': 'The entrypoint will run SteamCMD app_update and restart the server. This may take a few minutes.',
            'how_it_works': 'entrypoint.py automatically runs install_or_update_server() on every start'
        })

    except Exception as e:
        return jsonify({
            'error': f'Failed to update server: {str(e)}'
        }), 500


@app.route('/api/server/update-info', methods=['GET'])
def get_update_info():
    """Get information about server installation and potential updates.

    Note: SteamCMD cannot detect available updates without downloading them.
    This endpoint provides installation metadata instead.
    """
    try:
        # Check for appmanifest file which contains installation info
        manifest_pattern = f'appmanifest_{APPID}.acf'
        steamapps_dir = os.path.join(SERVER_PATH, '..', 'steamapps')
        manifest_path = os.path.join(steamapps_dir, manifest_pattern)

        install_info = {
            'appid': APPID,
            'server_path': SERVER_PATH,
            'installed': os.path.exists(os.path.join(SERVER_PATH, 'VeinServer.sh')) or
                        os.path.exists(os.path.join(SERVER_PATH, 'VeinServer')),
        }

        # Try to read manifest file for build ID
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r') as f:
                    content = f.read()
                    # Parse ACF format (simple key-value)
                    for line in content.split('\n'):
                        if '"buildid"' in line.lower():
                            build_id = line.split('"')[-2] if '"' in line else None
                            if build_id:
                                install_info['build_id'] = build_id
                        elif '"timeupdated"' in line.lower():
                            timestamp = line.split('"')[-2] if '"' in line else None
                            if timestamp:
                                install_info['last_updated'] = datetime.fromtimestamp(int(timestamp)).isoformat()
            except Exception as e:
                install_info['manifest_error'] = str(e)

        return jsonify({
            'install_info': install_info,
            'note': 'SteamCMD cannot check for updates without downloading. Use POST /api/server/update to update.',
            'limitations': 'Steam API does not provide a reliable way to check for available updates before downloading'
        })

    except Exception as e:
        return jsonify({
            'error': f'Failed to get update info: {str(e)}'
        }), 500


if __name__ == '__main__':
    if not SERVER_API_ENABLED:
        print("Server API is disabled (SERVER_API_ENABLED=false). Exiting.")
        import sys
        sys.exit(0)

    print(f"Starting Server API on port {SERVER_API_PORT}")
    print(f"Config path: {CONFIG_PATH}")
    print(f"Server path: {SERVER_PATH}")

    if API_KEY:
        print("API Key authentication enabled for protected operations")
    else:
        print("Warning: No API key set. Protected operations are unprotected!")

    app.run(host='0.0.0.0', port=SERVER_API_PORT, debug=False)