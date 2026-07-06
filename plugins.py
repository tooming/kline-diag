#!/usr/bin/env python3
"""Plugin architecture (Phase 9 scaffold).

A lightweight, dependency-free plugin registry so module/vehicle support can
be added as drop-in files instead of edits to the central code. This is the
foundational layer of the roadmap's plugin system — the interface and loader,
kept minimal and testable — not the full multi-week refactor.

A plugin is any object exposing:
    name: str
    kind: "module" | "vehicle" | "analysis"
    (optional) applies_to(profile_key) -> bool

Plugins are discovered from the `plugins/` directory (each .py defining a
top-level `PLUGIN`) or registered directly. Discovery failures are isolated:
one broken plugin never takes down the loader.

Pure stdlib, offline.
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.join(HERE, "plugins")


class ModulePlugin:
    """Base class for a diagnostic module plugin. Subclasses fill in the
    address map and (optionally) coding/adaptation behaviour. Kept abstract:
    the base does not talk to the car."""
    name = "unnamed"
    kind = "module"
    description = ""
    addresses = ()          # module addresses this plugin handles
    protocol = "ds2"        # ds2 | kwp2000 | uds

    def applies_to(self, profile_key):
        return True

    def describe(self):
        return {"name": self.name, "kind": self.kind,
                "description": self.description,
                "addresses": [f"0x{a:02X}" for a in self.addresses],
                "protocol": self.protocol}


class Registry:
    """Holds registered plugins and answers lookups by kind/address."""

    def __init__(self):
        self._plugins = []

    def register(self, plugin):
        if not getattr(plugin, "name", None):
            raise ValueError("plugin missing .name")
        if any(p.name == plugin.name and p.kind == plugin.kind
               for p in self._plugins):
            return False  # idempotent: skip duplicates
        self._plugins.append(plugin)
        return True

    def all(self, kind=None):
        return [p for p in self._plugins
                if kind is None or p.kind == kind]

    def for_address(self, addr, profile_key=None):
        out = []
        for p in self._plugins:
            if addr in getattr(p, "addresses", ()):
                if profile_key is None or p.applies_to(profile_key):
                    out.append(p)
        return out

    def discover(self, path=PLUGIN_DIR):
        """Load every plugins/*.py that defines a top-level PLUGIN. Returns
        (loaded_names, errors) — errors are isolated per file."""
        loaded, errors = [], []
        if not os.path.isdir(path):
            return loaded, errors
        for fn in sorted(os.listdir(path)):
            if not fn.endswith(".py") or fn.startswith("_"):
                continue
            fpath = os.path.join(path, fn)
            try:
                spec = importlib.util.spec_from_file_location(
                    f"_plugin_{fn[:-3]}", fpath)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                plugin = getattr(mod, "PLUGIN", None)
                if plugin is None:
                    errors.append((fn, "no top-level PLUGIN"))
                    continue
                if self.register(plugin):
                    loaded.append(plugin.name)
            except Exception as e:  # isolate a bad plugin
                errors.append((fn, str(e)))
        return loaded, errors


# Process-wide default registry.
REGISTRY = Registry()


def load_all():
    return REGISTRY.discover()


if __name__ == "__main__":
    loaded, errors = load_all()
    print(f"loaded plugins: {loaded}")
    if errors:
        print(f"errors: {errors}")
    for p in REGISTRY.all():
        print(" ", p.describe())
