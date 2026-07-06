#!/usr/bin/env python3
"""Resource- vs data-path resolution, for running frozen or from source.

Two kinds of file location must diverge once the app is packaged with
PyInstaller:

* **resource_dir()** — read-only bundled files (ui.html, the *.json fault/
  parameter tables). In a frozen build these are unpacked to a temp dir
  (``sys._MEIPASS``); from source they sit in the project directory.

* **data_dir()** — writable runtime data (kline_raw.log, drive/​power logs,
  fault snapshots, the VIN backup tree, verified_maps.json). In a frozen
  build the project dir is read-only/ephemeral, so these must live in a
  persistent per-user folder (``%APPDATA%\\BMWDiag`` on Windows). The
  backup tree in particular MUST persist — it's the safety net behind every
  module write.

Running from source (the normal dev / macOS case) both resolve to the
project directory, so behaviour is byte-for-byte unchanged.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def is_frozen():
    return getattr(sys, "frozen", False)


def resource_dir():
    """Directory holding read-only bundled resources."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return _HERE


def _user_data_base():
    if sys.platform.startswith("win"):
        return os.environ.get("APPDATA") or os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library",
                            "Application Support")
    return (os.environ.get("XDG_DATA_HOME")
            or os.path.join(os.path.expanduser("~"), ".local", "share"))


def data_dir():
    """Directory for writable runtime data (created if missing)."""
    d = os.path.join(_user_data_base(), "BMWDiag") if is_frozen() else _HERE
    os.makedirs(d, exist_ok=True)
    return d


def data_path(*parts):
    """Convenience: a path under data_dir()."""
    return os.path.join(data_dir(), *parts)
