#!/usr/bin/env python3
"""
Simple HTTP server to serve the Autograder Interactive Demo
"""

import http.server
import socketserver
import os
import sys

def main():
    # Change to examples directory
    examples_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(examples_dir)

    # Port configuration
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    # Create server
    Handler = http.server.SimpleHTTPRequestHandler

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"")
        print(f"🚀 Autograder Interactive Demo Server")
        print(f"=" * 50)
        print(f"")
        print(f"   Server running at: http://localhost:{PORT}")
        print(f"   Directory: {examples_dir}")
        print(f"")
        print(f"   Press Ctrl+C to stop")
        print(f"")
        print(f"=" * 50)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n\nServer stopped.")
            sys.exit(0)

if __name__ == "__main__":
    main()

