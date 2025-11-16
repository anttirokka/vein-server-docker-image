#!/usr/bin/env python3
"""
HTTP forwarder with CORS support for Vein Server API.
Waits for the game server to start, then forwards traffic with CORS headers.
"""

import argparse
import http.client
import http.server
import os
import socketserver
import sys
import time

HOP_BY_HOP = {
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailer', 'transfer-encoding', 'upgrade'
}

class CORSForwardHandler(http.server.BaseHTTPRequestHandler):
    upstream_host = '127.0.0.1'
    upstream_port = 8080
    allow_origin = '*'

    def log_message(self, fmt, *args):
        print(f"[CORS-Forwarder] {fmt % args}")

    def _write_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', self.allow_origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def do_OPTIONS(self):
        self.send_response(204)
        self._write_cors_headers()
        self.end_headers()

    def _proxy_request(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else None

        conn = http.client.HTTPConnection(self.upstream_host, self.upstream_port, timeout=15)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        headers['Host'] = f"{self.upstream_host}:{self.upstream_port}"

        try:
            conn.request(self.command, self.path, body, headers)
            resp = conn.getresponse()
            payload = resp.read()
            self.send_response(resp.status, resp.reason)
            for key, value in resp.getheaders():
                if key.lower() not in HOP_BY_HOP:
                    self.send_header(key, value)
            self._write_cors_headers()
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            self.send_response(502, "Bad Gateway")
            self._write_cors_headers()
            self.end_headers()
            error_msg = f'{{"error":"Upstream unavailable","details":"{str(exc)}"}}'
            self.wfile.write(error_msg.encode())
        finally:
            conn.close()

    def do_GET(self): self._proxy_request()
    def do_POST(self): self._proxy_request()
    def do_PUT(self): self._proxy_request()
    def do_PATCH(self): self._proxy_request()
    def do_DELETE(self): self._proxy_request()

def wait_for_upstream(upstream_port, max_retries=120, check_interval=5):
    """Wait for the upstream server to start listening."""
    print(f"Waiting for game server to start on port {upstream_port}...")
    time.sleep(30)  # Initial delay for game server startup

    port_hex = f"{upstream_port:04X}"

    for attempt in range(1, max_retries + 1):
        try:
            with open('/proc/net/tcp', 'r') as f:
                for line in f:
                    if f":{port_hex} " in line:
                        print(f"Game server HTTP listener detected on port {upstream_port}")
                        return True
        except Exception as e:
            print(f"Warning: Could not read /proc/net/tcp: {e}")

        print(f"Waiting for game server HTTP listener (attempt {attempt}/{max_retries})...")
        time.sleep(check_interval)

    print(f"Warning: Game server HTTP listener not detected after {max_retries} attempts "
          f"({max_retries * check_interval // 60} minutes)")
    print("Starting forwarder anyway...")
    return False

def main():
    # Read from environment variables with defaults
    listen_host = os.getenv('FORWARD_HOST', '0.0.0.0')
    listen_port = int(os.getenv('FORWARD_PORT', '9080'))
    upstream_host = os.getenv('UPSTREAM_HOST', '127.0.0.1')
    upstream_port = int(os.getenv('HTTP_PORT', '8080'))
    allow_origin = os.getenv('CORS_ALLOW_ORIGIN', '*')

    if not upstream_port:
        print("HTTP_PORT not set, skipping HTTP forwarder")
        sys.exit(0)

    print(f"Starting HTTP forwarder: {listen_host}:{listen_port} -> {upstream_host}:{upstream_port}")

    # Wait for upstream server
    wait_for_upstream(upstream_port)

    # Configure handler
    CORSForwardHandler.upstream_host = upstream_host
    CORSForwardHandler.upstream_port = upstream_port
    CORSForwardHandler.allow_origin = allow_origin

    print(f"Starting HTTP traffic forwarder on port {listen_port} with CORS origin '{allow_origin}'")

    try:
        with socketserver.ThreadingTCPServer((listen_host, listen_port), CORSForwardHandler) as httpd:
            print(f"Forwarder ready: http://{listen_host}:{listen_port} -> "
                  f"http://{upstream_host}:{upstream_port}")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nForwarder stopped")
    except Exception as e:
        print(f"Error starting forwarder: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
