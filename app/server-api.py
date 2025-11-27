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
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration paths
CONFIG_PATH = os.getenv('CONFIG_PATH', '/home/steam/vein-server/Vein/Saved/Config/LinuxServer')
SERVER_PATH = os.getenv('SERVER_PATH', '/home/steam/vein-server')
LOG_DIR = os.path.join(SERVER_PATH, 'Vein/Saved/Logs')

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