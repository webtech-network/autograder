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

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

# Change to the directory containing this script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Enable CORS for local development
class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=".", **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

print(f"""
╔══════════════════════════════════════════════════════════════╗
║          Autograder Testing Dashboard Server                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Dashboard URL: http://localhost:{PORT}/testing_dashboard.html
║                                                              ║
║  Make sure the Autograder API is running at:                 ║
║  http://localhost:8000                                       ║
║                                                              ║
║  Start the API with: docker-compose up                       ║
║  Or: uvicorn web.main:app --reload                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
    try:
        # Try to open the browser
        webbrowser.open(f"http://localhost:{PORT}/testing_dashboard.html")
    except Exception:
        pass

    print(f"Serving at http://localhost:{PORT}")
    print("Press Ctrl+C to stop the server\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

