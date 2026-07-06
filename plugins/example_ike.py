"""Example module plugin (IKE / instrument cluster) demonstrating the
plugin interface. Drop-in: this file's presence alone registers the plugin
via Registry.discover(). Read-only descriptive scaffold — no car writes."""
from plugins import ModulePlugin


class IKEPlugin(ModulePlugin):
    name = "IKE"
    kind = "module"
    description = "Instrument cluster — VIN, mileage, SIA service reset"
    addresses = (0x80,)
    protocol = "ds2"

    def applies_to(self, profile_key):
        return profile_key == "e39"


PLUGIN = IKEPlugin()
