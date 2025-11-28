#!/usr/bin/env python3
"""
Automatic backup script for Vein Server save files.
Backs up Server.vns to a dated backup folder and manages retention.
"""

import os
import shutil
import time
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Configuration from environment variables
SERVER_PATH = os.getenv('SERVER_PATH', '/home/steam/vein-server')
SAVE_FILE = os.path.join(SERVER_PATH, 'Vein/Saved/SaveGames/Server.vns')
BACKUP_DIR = os.getenv('BACKUP_DIR', os.path.join(SERVER_PATH, 'Vein/Saved/Backups'))
MAX_BACKUPS = int(os.getenv('BACKUP_RETENTION', '14'))  # Keep 14 backups by default
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')

def send_discord_notification(message, title="Vein Server Backup", color=3066993):
    """Send a notification to Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        return False

    try:
        import requests

        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }

        payload = {"embeds": [embed]}
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        return response.status_code in [200, 204]
    except Exception as e:
        logging.error(f"Failed to send Discord notification: {e}")
        return False

def ensure_backup_directory():
    """Create backup directory if it doesn't exist."""
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    logging.info(f"Backup directory ensured: {BACKUP_DIR}")

def get_file_size_mb(filepath):
    """Get file size in MB."""
    if os.path.exists(filepath):
        return os.path.getsize(filepath) / (1024 * 1024)
    return 0

def backup_save_file():
    """Backup the Server.vns file with timestamp."""
    if not os.path.exists(SAVE_FILE):
        logging.warning(f"Save file not found: {SAVE_FILE}")
        return False

    try:
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"Server_{timestamp}.vns"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        # Get file size before backup
        file_size = get_file_size_mb(SAVE_FILE)

        # Copy the save file
        logging.info(f"Backing up {SAVE_FILE} -> {backup_path}")
        shutil.copy2(SAVE_FILE, backup_path)

        logging.info(f"Backup created successfully: {backup_filename} ({file_size:.2f} MB)")

        # Send Discord notification
        send_discord_notification(
            f"✅ **Backup completed successfully**\n\n"
            f"**File:** Server.vns\n"
            f"**Size:** {file_size:.2f} MB\n"
            f"**Backup:** {backup_filename}\n"
            f"**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            title="Save File Backed Up",
            color=3066993  # Green
        )

        return True
    except Exception as e:
        logging.error(f"Backup failed: {e}", exc_info=True)
        send_discord_notification(
            f"❌ **Backup failed**\n\n"
            f"**Error:** {str(e)}\n"
            f"**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            title="Backup Error",
            color=15158332  # Red
        )
        return False

def cleanup_old_backups():
    """Remove old backups, keeping only the most recent MAX_BACKUPS."""
    try:
        # Get all backup files
        backup_files = sorted(
            [f for f in Path(BACKUP_DIR).glob('Server_*.vns')],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        if len(backup_files) <= MAX_BACKUPS:
            logging.info(f"Current backups: {len(backup_files)}, retention limit: {MAX_BACKUPS}, no cleanup needed")
            return

        # Remove old backups
        files_to_remove = backup_files[MAX_BACKUPS:]
        logging.info(f"Removing {len(files_to_remove)} old backup(s)")

        for backup_file in files_to_remove:
            logging.info(f"Removing old backup: {backup_file.name}")
            backup_file.unlink()

        logging.info(f"Cleanup complete. Kept {MAX_BACKUPS} most recent backups")
    except Exception as e:
        logging.error(f"Cleanup failed: {e}", exc_info=True)

def list_backups():
    """List all existing backups."""
    try:
        backup_files = sorted(
            [f for f in Path(BACKUP_DIR).glob('Server_*.vns')],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        if not backup_files:
            logging.info("No backups found")
            return

        logging.info(f"Found {len(backup_files)} backup(s):")
        for backup_file in backup_files:
            stat = backup_file.stat()
            size_mb = stat.st_size / (1024 * 1024)
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            logging.info(f"  - {backup_file.name} ({size_mb:.2f} MB) - {mtime}")
    except Exception as e:
        logging.error(f"Failed to list backups: {e}")

def main():
    """Main backup function."""
    logging.info("=" * 50)
    logging.info("Vein Server Backup Starting")
    logging.info(f"Save file: {SAVE_FILE}")
    logging.info(f"Backup directory: {BACKUP_DIR}")
    logging.info(f"Retention: {MAX_BACKUPS} backups")
    logging.info("=" * 50)

    # Ensure backup directory exists
    ensure_backup_directory()

    # Perform backup
    if backup_save_file():
        # Cleanup old backups
        cleanup_old_backups()

        # List current backups
        list_backups()

        logging.info("Backup process completed successfully")
        return 0
    else:
        logging.error("Backup process failed")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
