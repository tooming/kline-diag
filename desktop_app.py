#!/usr/bin/env python3
"""Native desktop-app wrapper for the diagnostic UI.

Wraps ``diag_ui.py``'s localhost web server in a native OS webview window
(pywebview) so the tool launches as a normal Mac/Windows/Linux app instead
of "run a server, open a browser". No Chromium is bundled — this uses the
platform webview (WKWebView on macOS).

This is an OPTIONAL wrapper. The core scripts (``power_diag.py``,
``ds2_diag.py``, ``diag_ui.py``) stay stdlib-only and still run with bare
python3; only this launcher needs the ``pywebview`` dependency:

    pip install -r requirements-desktop.txt
    python3 desktop_app.py

The diag server is started as a child process — it owns the serial port
exclusively (matching its design), so keeping it in its own process keeps
that isolation clean. The window teardown terminates the child.
"""
import atexit
import os
import subprocess
import sys
import time
import urllib.request

import webview

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("BMW_DIAG_PORT", "8039"))
BASE = f"http://127.0.0.1:{PORT}"


def _server_up():
    """True if something answers /api/state on PORT."""
    try:
        with urllib.request.urlopen(f"{BASE}/api/state", timeout=0.5) as r:
            return r.status == 200
    except Exception:
        return False


def start_server():
    """Spawn diag_ui.py and wait for it to come up.

    Returns the Popen, or None if a server was already running on PORT (in
    which case we attach to it and leave it alone on exit).
    """
    if _server_up():
        return None
    proc = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "diag_ui.py"),
         "--no-connect", "--port-http", str(PORT)],
        cwd=HERE)
    for _ in range(100):            # up to ~10 s
        if _server_up():
            return proc
        if proc.poll() is not None:
            raise SystemExit(
                f"diag server exited early (code {proc.returncode})")
        time.sleep(0.1)
    proc.terminate()
    raise SystemExit("diag server did not start within 10 s")


def main():
    proc = start_server()

    def cleanup():
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    atexit.register(cleanup)
    webview.create_window(
        "BMW Diagnostics", BASE,
        width=1280, height=860, min_size=(900, 600))
    try:
        webview.start()
    finally:
        cleanup()


if __name__ == "__main__":
    main()
