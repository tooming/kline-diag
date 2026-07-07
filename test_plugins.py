#!/usr/bin/env python3
"""Tests for the plugin architecture scaffold (Phase 9)."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from plugins import Registry, ModulePlugin


def test_register_and_lookup():
    reg = Registry()

    class P(ModulePlugin):
        name = "TEST"
        addresses = (0x80,)
    assert reg.register(P()) is True
    assert reg.register(P()) is False   # duplicate skipped
    assert len(reg.all("module")) == 1
    assert reg.for_address(0x80) and not reg.for_address(0x12)
    print("test_register_and_lookup OK")


def test_applies_to_filtering():
    reg = Registry()

    class E39Only(ModulePlugin):
        name = "E39ONLY"
        addresses = (0x44,)

        def applies_to(self, key):
            return key == "e39"
    reg.register(E39Only())
    assert reg.for_address(0x44, "e39")
    assert not reg.for_address(0x44, "e87")
    print("test_applies_to_filtering OK")


def test_discover_isolates_errors():
    """A broken plugin file must not stop the others from loading."""
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "good.py"), "w") as f:
        f.write("from plugins import ModulePlugin\n"
                "class G(ModulePlugin):\n"
                "    name='GOOD'\n    addresses=(0x12,)\n"
                "PLUGIN=G()\n")
    with open(os.path.join(d, "broken.py"), "w") as f:
        f.write("raise RuntimeError('boom')\n")
    with open(os.path.join(d, "no_plugin.py"), "w") as f:
        f.write("x = 1\n")
    reg = Registry()
    loaded, errors = reg.discover(d)
    assert "GOOD" in loaded, loaded
    err_files = {e[0] for e in errors}
    assert "broken.py" in err_files and "no_plugin.py" in err_files, errors
    import shutil
    shutil.rmtree(d)
    print("test_discover_isolates_errors OK")


def test_real_example_plugin_loads():
    reg = Registry()
    loaded, errors = reg.discover()   # the repo plugins/ dir
    assert "IKE" in loaded, (loaded, errors)
    ike = reg.for_address(0x80, "e39")[0]
    assert ike.protocol == "ds2"
    print("test_real_example_plugin_loads OK")


if __name__ == "__main__":
    test_register_and_lookup()
    test_applies_to_filtering()
    test_discover_isolates_errors()
    test_real_example_plugin_loads()
    print("\nAll plugin tests passed.")
