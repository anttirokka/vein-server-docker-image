#!/bin/bash

# HTTP API port forwarder
# Forwards traffic from 0.0.0.0:9080 to 127.0.0.1:8080
# This allows external access to the game server's HTTP API that binds to localhost

if [ -n "${HTTP_PORT}" ]; then
    # Use a different port for the external listener to avoid conflicts
    FORWARD_PORT=9080

    echo "Starting HTTP forwarder: 0.0.0.0:${FORWARD_PORT} -> 127.0.0.1:${HTTP_PORT}"

    # Wait for the game server to start the HTTP listener
    echo "Waiting for game server to start..."
    sleep 30

    # Check if the game server's HTTP listener is up using /proc/net/tcp
    # This is more lightweight than netstat and doesn't require additional packages
    MAX_RETRIES=120  # Increased from 60 to 120 (10 minutes total)
    RETRY_COUNT=0
    CHECK_INTERVAL=5  # Configurable check interval in seconds

    # Convert port to hex for /proc/net/tcp format
    PORT_HEX=$(printf '%04X' "${HTTP_PORT}")

    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        # Check if localhost:HTTP_PORT is listening
        # /proc/net/tcp format: local_address is "0100007F:PORT" for 127.0.0.1:PORT
        if grep -q ":${PORT_HEX} " /proc/net/tcp 2>/dev/null; then
            echo "Game server HTTP listener detected on port ${HTTP_PORT}"
            break
        fi

        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "Waiting for game server HTTP listener (attempt ${RETRY_COUNT}/${MAX_RETRIES})..."
        sleep ${CHECK_INTERVAL}
    done

    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo "Warning: Game server HTTP listener not detected after ${MAX_RETRIES} attempts ($(($MAX_RETRIES * $CHECK_INTERVAL / 60)) minutes)"
        echo "Starting forwarder anyway..."
    fi

    echo "Starting HTTP traffic forwarder on port ${FORWARD_PORT}..."
    # Forward traffic using socat on a different port
    exec socat TCP-LISTEN:${FORWARD_PORT},fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:${HTTP_PORT}
else
    echo "HTTP_PORT not set, skipping HTTP forwarder"
    exit 0
fi
