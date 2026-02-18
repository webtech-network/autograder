#!/usr/bin/env python3
"""
Simple HTTP server to serve the Autograder Testing Dashboard.

Usage:
    python serve_dashboard.py [port]

Default port is 8080. The dashboard will connect to the Autograder API
at http://localhost:8000 by default (configurable in the UI).
"""

import http.server
import socketserver
import os
import sys
import webbrowser
import socket

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

# Change to the dashboard directory (parent of scripts)
script_dir = os.path.dirname(os.path.abspath(__file__))
dashboard_dir = os.path.join(os.path.dirname(script_dir), 'dashboard')
os.chdir(dashboard_dir)

# Enable CORS for local development
class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=".", **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def find_available_port(start_port, max_attempts=10):
    """Find an available port starting from start_port."""
    for i in range(max_attempts):
        port = start_port + i
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return None

def main():
    global PORT

    # Try to find an available port
    available_port = find_available_port(PORT)
    if available_port is None:
        print(f"Error: Could not find an available port starting from {PORT}")
        print("Try specifying a different port: python serve_dashboard.py 9090")
        sys.exit(1)

    if available_port != PORT:
        print(f"Port {PORT} is in use, using port {available_port} instead.")
    PORT = available_port

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║          Autograder Testing Dashboard Server                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Dashboard URL: http://localhost:{PORT}/index.html
║                                                              ║
║  Pages:                                                      ║
║    - index.html        (Main menu)                           ║
║    - page_config.html  (Create configuration)                ║
║    - page_submit.html  (Submit & grade code)                 ║
║    - page_api.html     (API operations)                      ║
║                                                              ║
║  Make sure the Autograder API is running at:                 ║
║  http://localhost:8000                                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Allow socket reuse to avoid "Address already in use" errors
    socketserver.TCPServer.allow_reuse_address = True

    try:
        with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
            try:
                # Try to open the browser (skip if in Docker/headless)
                if os.environ.get('DISPLAY') or sys.platform == 'darwin':
                    webbrowser.open(f"http://localhost:{PORT}/index.html")
            except Exception:
                pass

            print(f"Serving at http://localhost:{PORT}")
            print("Press Ctrl+C to stop the server\n")

            httpd.serve_forever()
    except OSError as e:
        print(f"Error starting server: {e}")
        print(f"Port {PORT} may already be in use.")
        print("Try: python serve_dashboard.py 9090")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
