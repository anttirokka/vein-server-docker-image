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
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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

        # Send SIGTERM for graceful shutdown
        proc.terminate()

        # Wait for process to exit (max 30 seconds)
        print("Waiting for server to shut down...")
        try:
            proc.wait(timeout=30)
            print("Server shut down gracefully")
        except psutil.TimeoutExpired:
            # Force kill if graceful shutdown failed
            print("Server didn't shut down gracefully, forcing...")
            proc.kill()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                return jsonify({
                    'error': 'Server process could not be terminated',
                    'note': 'You may need to restart the container'
                }), 500

        # Wait a moment for cleanup
        time.sleep(2)

        # Restart the server by running the entrypoint command in a subprocess
        # This spawns a new server process with the same args
        print("Starting new server process...")
        server_path = os.getenv('SERVER_PATH', '/home/steam/vein-server')

        # Build the command to restart the server
        # Note: entrypoint.py will regenerate the default flags from env vars
        # Any custom flags from the original container start won't be preserved
        # unless they were set via environment variables
        restart_cmd = ['/usr/bin/python3', '/entrypoint.py']

        # Start the new server process in the background
        subprocess.Popen(
            restart_cmd,
            cwd=server_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        return jsonify({
            'success': True,
            'message': 'Server restart initiated',
            'previous_pid': pid,
            'server_args_detected': server_args,
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
    """Update the Vein server using SteamCMD.
    
    Note: SteamCMD cannot reliably detect if an update is available before downloading.
    This endpoint will run app_update which downloads any available updates.
    The server should be stopped before updating.
    """
    # Check if server is running
    proc = get_server_process()
    
    if proc:
        return jsonify({
            'error': 'Server is currently running',
            'message': 'Please stop the server before updating',
            'suggestion': 'Use POST /api/server/restart to restart after stopping, or stop manually first'
        }), 400

    if not os.path.exists(STEAMCMD_PATH):
        return jsonify({
            'error': 'SteamCMD not found',
            'path': STEAMCMD_PATH
        }), 500

    try:
        print(f"Running SteamCMD update for AppID {APPID}...")
        
        # Get Steam credentials from environment
        steam_user = os.getenv('STEAM_USER', 'anonymous')
        steam_pass = os.getenv('STEAM_PASS', '')
        steam_auth = os.getenv('STEAM_AUTH', '')

        # Build SteamCMD command
        cmd = [
            STEAMCMD_PATH,
            '+force_install_dir', SERVER_PATH,
            '+login', steam_user, steam_pass, steam_auth,
            '+app_update', APPID, 'validate',
            '+quit'
        ]

        # Run SteamCMD update
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        # Parse output to detect if update occurred
        output = result.stdout + result.stderr
        update_occurred = 'downloading' in output.lower() or 'update required' in output.lower()
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'Server update completed',
                'appid': APPID,
                'update_detected': update_occurred,
                'note': 'Start the server to apply changes' if not proc else 'Server will need to be restarted',
                'output_snippet': output[-500:] if len(output) > 500 else output  # Last 500 chars
            })
        else:
            return jsonify({
                'error': 'SteamCMD update failed',
                'return_code': result.returncode,
                'output': output[-1000:] if len(output) > 1000 else output
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            'error': 'SteamCMD update timed out',
            'message': 'Update took longer than 10 minutes'
        }), 500
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