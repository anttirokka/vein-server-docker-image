#!/bin/bash
# Cron job wrapper for backup script
# This ensures proper environment and logging

# Source environment variables if available
if [ -f /etc/environment ]; then
    set -a
    source /etc/environment
    set +a
fi

# Run backup with Python
python3 /backup.py

# Exit with the same code
exit $?
