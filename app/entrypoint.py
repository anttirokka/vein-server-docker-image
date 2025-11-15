#!/usr/bin/env python3
import os
import sys
import subprocess
import configparser
from pathlib import Path

def run_as_steam_user():
    """Re-execute script as steam user if running as root."""
    if os.getuid() == 0:
        print("Switching to user steam...")
        os.execvp('gosu', ['gosu', 'steam', 'python3'] + sys.argv)

def ensure_directory(path):
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)

def update_ini_value(config, section, key, value):
    """Update or add a value in the config."""
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, key, str(value))

def update_ini_array(config, section, key, csv_values):
    """Handle array-style INI entries (like Steam IDs with + prefix)."""
    if not csv_values:
        return

    if not config.has_section(section):
        config.add_section(section)

    # Add new entries directly (configparser will handle duplicates)
    values = [v.strip() for v in csv_values.split(',')]
    config.set(section, key, values[0])
    for val in values[1:]:
        # Multiple values with same key get overwritten, so we use a workaround
        # Store them as separate options with + prefix
        existing_count = sum(1 for opt in config.options(section) if opt.startswith(f'+{key}'))
        config.set(section, f'+{key}#{existing_count}', val)

def write_ini_file(config, filepath):
    """Write INI file with proper formatting."""
    with open(filepath, 'w') as f:
        config.write(f, space_around_delimiters=False)

def update_game_ini(config_path):
    """Update Game.ini with environment variables."""
    game_ini_path = os.path.join(config_path, 'Game.ini')

    # Use RawConfigParser to preserve case and special characters
    config = configparser.RawConfigParser()
    config.optionxform = str  # Preserve case

    if os.path.exists(game_ini_path):
        config.read(game_ini_path)

    print(f"Updating {game_ini_path}...")

    # [/Script/Engine.GameSession]
    update_ini_value(config, '/Script/Engine.GameSession', 'MaxPlayers',
                     os.getenv('MAX_PLAYERS', '16'))

    # [/Script/Vein.VeinGameSession]
    update_ini_value(config, '/Script/Vein.VeinGameSession', 'ServerName',
                     f'"{os.getenv("SERVER_NAME", "Vein Docker Server")}"')
    update_ini_value(config, '/Script/Vein.VeinGameSession', 'BindAddr',
                     os.getenv('SERVER_BIND_ADDR', '0.0.0.0'))
    update_ini_value(config, '/Script/Vein.VeinGameSession', 'HeartbeatInterval',
                     os.getenv('HEARTBEAT_INTERVAL', '5.0'))

    # HTTP Port - add HTTPPort
    http_port = os.getenv('HTTP_PORT')
    if http_port:
        update_ini_value(config, '/Script/Vein.VeinGameSession', 'HTTPPort', http_port)

    # Public setting
    is_public = os.getenv('SERVER_PUBLIC', 'True').lower() != 'false'
    update_ini_value(config, '/Script/Vein.VeinGameSession', 'bPublic',
                     'True' if is_public else 'False')

    server_password = os.getenv('SERVER_PASSWORD')
    if server_password:
        update_ini_value(config, '/Script/Vein.VeinGameSession', 'Password', server_password)

    # Steam IDs - always update if provided
    super_admin_ids = os.getenv('SUPER_ADMIN_STEAM_IDS')
    if super_admin_ids:
        update_ini_array(config, '/Script/Vein.VeinGameSession', 'SuperAdminSteamIDs', super_admin_ids)

    admin_ids = os.getenv('ADMIN_STEAM_IDS')
    if admin_ids:
        update_ini_array(config, '/Script/Vein.VeinGameSession', 'AdminSteamIDs', admin_ids)

    # [OnlineSubsystemSteam]
    update_ini_value(config, 'OnlineSubsystemSteam', 'GameServerQueryPort',
                     os.getenv('GAME_SERVER_QUERY_PORT', '27015'))
    update_ini_value(config, 'OnlineSubsystemSteam', 'bVACEnabled',
                     os.getenv('VAC_ENABLED', '0'))

    # [URL]
    update_ini_value(config, 'URL', 'Port', os.getenv('GAME_PORT', '7777'))

    # [/Script/Vein.ServerSettings]
    show_badges = os.getenv('GS_SHOW_SCOREBOARD_BADGES')
    if show_badges:
        update_ini_value(config, '/Script/Vein.ServerSettings', 'GS_ShowScoreboardBadges', show_badges)

    discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
    if discord_webhook:
        update_ini_value(config, '/Script/Vein.ServerSettings', 'DiscordChatWebhookURL',
                         f'"{discord_webhook}"')

    discord_admin_webhook = os.getenv('DISCORD_ADMIN_WEBHOOK_URL')
    if discord_admin_webhook:
        update_ini_value(config, '/Script/Vein.ServerSettings', 'DiscordChatAdminWebhookURL',
                         f'"{discord_admin_webhook}"')

    write_ini_file(config, game_ini_path)
    print(f"{game_ini_path} updated.")

def update_engine_ini(config_path):
    """Update Engine.ini with environment variables."""
    engine_ini_path = os.path.join(config_path, 'Engine.ini')

    config = configparser.RawConfigParser()
    config.optionxform = str  # Preserve case

    if os.path.exists(engine_ini_path):
        config.read(engine_ini_path)

    print(f"Updating {engine_ini_path}...")

    # [URL]
    update_ini_value(config, 'URL', 'Port', os.getenv('GAME_PORT', '7777'))

    # [Core.Log]
    update_ini_value(config, 'Core.Log', 'LogOnlineSession', 'Warning')
    update_ini_value(config, 'Core.Log', 'LogOnline', 'Warning')

    # [ConsoleVariables] - Handle CVAR_ prefixed environment variables
    for key, value in os.environ.items():
        if key.startswith('CVAR_'):
            cvar_name = key[5:]  # Remove 'CVAR_' prefix
            update_ini_value(config, 'ConsoleVariables', cvar_name, value)

    write_ini_file(config, engine_ini_path)
    print(f"{engine_ini_path} updated.")

def setup_directories(server_path, config_path):
    """Create and display directory information."""
    log_dir = os.getenv('LOG_DIR', os.path.join(server_path, 'Vein/Saved/Logs'))

    for directory in [log_dir, config_path]:
        ensure_directory(directory)

    print(f"Install directory: {server_path}")
    subprocess.run(['ls', '-la', server_path], check=False)

    print(f"Config directory: {config_path}")
    subprocess.run(['ls', '-la', config_path], check=False)

    print(f"Log directory: {log_dir}")
    subprocess.run(['ls', '-la', log_dir], check=False)

def install_or_update_server(server_path):
    """Run SteamCMD to install/update the server."""
    appid = os.getenv('APPID')
    steam_user = os.getenv('STEAM_USER', 'anonymous')
    steam_pass = os.getenv('STEAM_PASS', '')
    steam_auth = os.getenv('STEAM_AUTH', '')

    print(f"Updating/Installing Vein Dedicated Server (AppID: {appid})...")

    cmd = [
        '/home/steam/steamcmd/steamcmd.sh',
        '+force_install_dir', server_path,
        '+login', steam_user, steam_pass, steam_auth,
        '+app_update', appid, 'validate',
        '+quit'
    ]

    subprocess.run(cmd, check=True)

def setup_steamclient_symlink(server_path):
    """Create steamclient.so symlink if needed."""
    steamcmd_path = '/home/steam/.steam/steamcmd/linux64'
    sdk64_path = '/home/steam/.steam/sdk64'
    steamclient_so = 'steamclient.so'

    source_path = None
    steamcmd_file = os.path.join(steamcmd_path, steamclient_so)
    server_file = os.path.join(server_path, steamclient_so)

    if os.path.isfile(steamcmd_file):
        source_path = steamcmd_file
    elif os.path.isfile(server_file):
        source_path = server_file

    if source_path:
        ensure_directory(sdk64_path)
        target = os.path.join(sdk64_path, steamclient_so)

        if not os.path.islink(target):
            os.symlink(source_path, target)
            print(f"Symlinked {steamclient_so} for SteamAPI.")
    else:
        print(f"Warning: {steamclient_so} not found in common SteamCMD paths or server directory. SteamAPI might fail.")

def start_server(server_path, extra_args):
    """Start the Vein server."""
    game_port = os.getenv('GAME_PORT', '7777')
    query_port = os.getenv('GAME_SERVER_QUERY_PORT', '27015')

    server_args = [
        '-log',
        f'-QueryPort={query_port}',
        f'-Port={game_port}'
    ]

    # Add multihome if specified
    if os.getenv('SERVER_MULTIHOME_IP'):
        server_args.append(f'-multihome={os.getenv("SERVER_MULTIHOME_IP")}')

    # Add any extra arguments
    server_args.extend(extra_args)

    print(f"Starting Vein Server with arguments: {' '.join(server_args)}")

    os.chdir(server_path)

    # Find server executable
    if os.path.isfile('./VeinServer.sh'):
        os.execv('./VeinServer.sh', ['./VeinServer.sh'] + server_args)
    elif os.path.isfile('./VeinServer'):
        os.execv('./VeinServer', ['./VeinServer'] + server_args)
    else:
        print(f"Error: VeinServer.sh or VeinServer executable not found in {server_path}.")
        print("Please check the installation.")
        sys.exit(1)

def main():
    """Main entrypoint function."""
    # Switch to steam user if running as root
    run_as_steam_user()

    # Get paths from environment
    server_path = os.getenv('SERVER_PATH')
    config_path = os.getenv('CONFIG_PATH')

    if not server_path or not config_path:
        print("Error: SERVER_PATH and CONFIG_PATH must be set")
        sys.exit(1)

    # Create config directory
    ensure_directory(config_path)

    # Update configuration files
    update_game_ini(config_path)
    update_engine_ini(config_path)

    # Setup directories
    setup_directories(server_path, config_path)

    # Install/update server
    install_or_update_server(server_path)

    # Setup steamclient.so symlink
    setup_steamclient_symlink(server_path)

    # Start server with any additional arguments
    start_server(server_path, sys.argv[1:])

if __name__ == '__main__':
    main()
