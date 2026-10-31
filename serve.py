#!/usr/bin/env python3
"""Lokal utviklingsserver. Importerer rapporter og bygger først (manifest, sitemap, SEO), og åpner siden.

  python serve.py            starter på http://localhost:8080
  python serve.py 9000       bruker en annen port
"""
import functools
import http.server
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    for step in ("import_reports.py", "build.py"):
        subprocess.run([sys.executable, str(ROOT / "tools" / step)], check=False)
    handler = functools.partial(Quiet, directory=str(ROOT))
    # Bare localhost, så andre på nettverket ikke når siden
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler) as srv:
        url = f"http://localhost:{PORT}"
        print(f"Server på {url}  (Ctrl+C for å stoppe)")
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nStoppet.")
