#!/usr/bin/env python3
"""Coding data structures and decoders for BMW modules.

Coding defines module configuration, behavior, and vehicle-specific options.
Each module stores coding as a string of bytes (hex) that configure various
features. This module provides:
  - Reading coding data from modules
  - Decoding into human-readable structure
  - Encoding back to byte strings (for writes)
  - Known coding options per module

Coding is module-specific. This file documents E39 modules first (IKE, LCM, GM),
then can be extended to other vehicles (E46, E87, E90, etc.).

Safety: Coding changes require transaction layer (backup → write → verify).
Wrong coding can cause malfunctions. Always read before writing.
"""
import json
from typing import Dict, List, Tuple, Optional


# === E39 IKE (Instrument Cluster) Coding ===

# IKE coding structure (based on E39 SGBD documentation)
# Byte positions and their meanings
IKE_CODING_MAP = {
    "byte_0": {
        "name": "Vehicle Type",
        "type": "enum",
        "values": {
            0x00: "Sedan",
            0x01: "Touring (Wagon)",
            0x02: "Coupe",
            0x03: "Convertible"
        }
    },
    "byte_1": {
        "name": "Units",
        "type": "bitfield",
        "bits": {
            0: {"name": "Speed unit", "values": {0: "km/h", 1: "mph"}},
            1: {"name": "Temp unit", "values": {0: "°C", 1: "°F"}},
            2: {"name": "Fuel unit", "values": {0: "L/100km", 1: "mpg"}},
            3: {"name": "Distance unit", "values": {0: "km", 1: "miles"}}
        }
    },
    "byte_2": {
        "name": "Country",
        "type": "enum",
        "values": {
            0x00: "EU/Rest of World",
            0x01: "USA",
            0x02: "Canada",
            0x03: "Japan",
            0x04: "UK/Australia (RHD)",
            0x05: "South Africa"
        }
    },
    "byte_3": {
        "name": "Language",
        "type": "enum",
        "values": {
            0x00: "German",
            0x01: "English (US)",
            0x02: "Italian",
            0x03: "French",
            0x04: "Spanish",
            0x05: "Japanese",
            0x06: "Dutch",
            0x07: "English (UK)"
        }
    },
    "byte_4": {
        "name": "Options 1",
        "type": "bitfield",
        "bits": {
            0: {"name": "Digital speed display", "values": {0: "Disabled", 1: "Enabled"}},
            1: {"name": "Gong volume", "values": {0: "Normal", 1: "Loud"}},
            2: {"name": "Oil service", "values": {0: "Inspection I/II", 1: "Oil service"}},
            3: {"name": "Consumption display", "values": {0: "L/100km or mpg", 1: "km/L"}},
            4: {"name": "Check control active", "values": {0: "No", 1: "Yes"}},
            5: {"name": "US gong", "values": {0: "EU gong", 1: "US gong"}},
            6: {"name": "Date format", "values": {0: "DD.MM.YYYY", 1: "MM/DD/YYYY"}},
            7: {"name": "Time format", "values": {0: "24h", 1: "12h AM/PM"}}
        }
    }
}

# === E39 IHKA (Climate Control) Coding ===

IHKA_CODING_MAP = {
    "byte_0": {
        "name": "Market",
        "type": "enum",
        "values": {
            0x00: "EU/ECE",
            0x01: "USA",
            0x02: "Canada",
            0x03: "Japan"
        }
    },
    "byte_1": {
        "name": "Temperature Unit",
        "type": "enum",
        "values": {
            0x00: "Celsius",
            0x01: "Fahrenheit"
        }
    },
    "byte_2": {
        "name": "Control Options",
        "type": "bitfield",
        "bits": {
            0: {"name": "Recirculation auto", "values": {0: "Manual", 1: "Automatic"}},
            1: {"name": "Max cooling button", "values": {0: "Disabled", 1: "Enabled"}},
            2: {"name": "Rear defroster auto", "values": {0: "Manual", 1: "Automatic"}},
            3: {"name": "Auto program", "values": {0: "Comfort", 1: "Economy"}},
            4: {"name": "Aux heater", "values": {0: "Disabled", 1: "Enabled"}},
            5: {"name": "Solar sensor", "values": {0: "Disabled", 1: "Enabled"}},
            6: {"name": "Rest function", "values": {0: "Disabled", 1: "Enabled"}},
            7: {"name": "Stratification", "values": {0: "Disabled", 1: "Enabled"}}
        }
    }
}

# === E39 GM/ZKE (General Module) Coding ===

GM_CODING_MAP = {
    "byte_0": {
        "name": "Market",
        "type": "enum",
        "values": {
            0x00: "EU/ECE",
            0x01: "USA",
            0x02: "Canada",
            0x03: "Japan",
            0x04: "Australia/RHD"
        }
    },
    "byte_1": {
        "name": "Central Locking",
        "type": "bitfield",
        "bits": {
            0: {"name": "Auto lock at 15 km/h", "values": {0: "Disabled", 1: "Enabled"}},
            1: {"name": "Auto unlock on ignition off", "values": {0: "Disabled", 1: "Enabled"}},
            2: {"name": "Selective door unlock", "values": {0: "All doors", 1: "Driver door first"}},
            3: {"name": "Comfort close windows", "values": {0: "Disabled", 1: "Enabled"}},
            4: {"name": "Comfort open windows", "values": {0: "Disabled", 1: "Enabled"}},
            5: {"name": "Lock confirmation", "values": {0: "Horn", 1: "Lights"}},
            6: {"name": "Crash unlock", "values": {0: "Disabled", 1: "Enabled"}},
            7: {"name": "Deadlocking", "values": {0: "Disabled", 1: "Enabled"}}
        }
    },
    "byte_2": {
        "name": "Comfort Functions",
        "type": "bitfield",
        "bits": {
            0: {"name": "Mirror fold on lock", "values": {0: "Disabled", 1: "Enabled"}},
            1: {"name": "Mirror unfold on unlock", "values": {0: "Disabled", 1: "Enabled"}},
            2: {"name": "Wiper service position", "values": {0: "Disabled", 1: "Enabled"}},
            3: {"name": "Rain sensor", "values": {0: "Disabled", 1: "Enabled"}},
            4: {"name": "Coming home delay", "values": {0: "30s", 1: "60s"}},
            5: {"name": "Leaving home", "values": {0: "Disabled", 1: "Enabled"}},
            6: {"name": "Remote trunk release", "values": {0: "Disabled", 1: "Enabled"}},
            7: {"name": "Key memory", "values": {0: "Disabled", 1: "Enabled"}}
        }
    }
}

# === E39 LCM (Light Control Module) Coding ===

LCM_CODING_MAP = {
    "byte_0": {
        "name": "Market",
        "type": "enum",
        "values": {
            0x00: "EU/ECE",
            0x01: "USA/FMVSS",
            0x02: "Canada",
            0x03: "Japan",
            0x04: "Australia"
        }
    },
    "byte_1": {
        "name": "Lighting Options",
        "type": "bitfield",
        "bits": {
            0: {"name": "Welcome lights", "values": {0: "Disabled", 1: "Enabled"}},
            1: {"name": "Welcome light duration", "values": {0: "20s", 1: "40s"}},
            2: {"name": "Follow-me-home", "values": {0: "Disabled", 1: "Enabled"}},
            3: {"name": "Daytime running lights", "values": {0: "Disabled", 1: "Enabled"}},
            4: {"name": "US turn signals", "values": {0: "EU (red)", 1: "US (amber)"}},
            5: {"name": "Comfort blink", "values": {0: "Disabled", 1: "Enabled"}},
            6: {"name": "Auto headlights", "values": {0: "Disabled", 1: "Enabled"}},
            7: {"name": "Cornering lights", "values": {0: "Disabled", 1: "Enabled"}}
        }
    },
    "byte_2": {
        "name": "Headlight Type",
        "type": "enum",
        "values": {
            0x00: "Halogen",
            0x01: "Xenon",
            0x02: "Xenon with self-leveling",
            0x03: "Bi-Xenon"
        }
    },
    "byte_3": {
        "name": "Fade Options",
        "type": "bitfield",
        "bits": {
            0: {"name": "Interior fade", "values": {0: "Instant", 1: "Fade"}},
            1: {"name": "Exterior fade", "values": {0: "Instant", 1: "Fade"}},
            2: {"name": "Locator flash", "values": {0: "Disabled", 1: "Enabled"}},
            3: {"name": "Panic alarm", "values": {0: "Disabled", 1: "Enabled"}}
        }
    }
}


class CodingDecoder:
    """Decode module coding bytes into human-readable structure."""

    def __init__(self, coding_map: Dict):
        """
        Initialize decoder with a coding map.

        Args:
            coding_map: Coding structure definition (e.g., IKE_CODING_MAP)
        """
        self.coding_map = coding_map

    def decode_byte(self, byte_idx: int, value: int) -> Dict:
        """
        Decode a single byte of coding data.

        Args:
            byte_idx: Byte position in coding string
            value: Byte value (0-255)

        Returns:
            dict with decoded information
        """
        key = f"byte_{byte_idx}"
        if key not in self.coding_map:
            return {"raw": f"0x{value:02X}", "unknown": True}

        field = self.coding_map[key]
        result = {"name": field["name"], "raw": f"0x{value:02X}"}

        if field["type"] == "enum":
            result["value"] = field["values"].get(value, f"Unknown (0x{value:02X})")
            result["type"] = "enum"

        elif field["type"] == "bitfield":
            bits = {}
            for bit_pos, bit_def in field["bits"].items():
                bit_value = (value >> bit_pos) & 1
                bits[bit_def["name"]] = {
                    "value": bit_def["values"][bit_value],
                    "bit": bit_pos,
                    "raw": bit_value
                }
            result["bits"] = bits
            result["type"] = "bitfield"

        return result

    def decode_coding(self, coding_bytes: bytes) -> Dict:
        """
        Decode full coding string.

        Args:
            coding_bytes: Raw coding data

        Returns:
            dict with all decoded fields
        """
        decoded = {"raw": coding_bytes.hex(), "bytes": []}

        for i, byte_val in enumerate(coding_bytes):
            decoded["bytes"].append(self.decode_byte(i, byte_val))

        return decoded

    def encode_coding(self, decoded: Dict) -> bytes:
        """
        Encode human-readable structure back to coding bytes.

        Args:
            decoded: Decoded coding structure

        Returns:
            Raw coding bytes

        Note: For now, returns raw bytes from hex string
        """
        if "raw" in decoded:
            return bytes.fromhex(decoded["raw"])
        raise NotImplementedError("Encoding from modified structure not yet implemented")

    def apply_preset(self, current_bytes: bytes, preset: Dict) -> bytes:
        """
        Apply a preset modification to coding bytes.

        Args:
            current_bytes: Current coding bytes
            preset: Preset definition with byte/bit modifications

        Returns:
            Modified coding bytes
        """
        result = bytearray(current_bytes)

        for byte_idx, modifications in preset.get("bytes", {}).items():
            if byte_idx >= len(result):
                continue

            byte_val = result[byte_idx]

            # Apply bit modifications
            for bit_pos, new_value in modifications.get("bits", {}).items():
                if new_value == 1:
                    byte_val |= (1 << bit_pos)  # Set bit
                else:
                    byte_val &= ~(1 << bit_pos)  # Clear bit

            # Apply direct byte value if specified
            if "value" in modifications:
                byte_val = modifications["value"]

            result[byte_idx] = byte_val

        return bytes(result)


def get_coding_decoder(module_name: str, protocol: str = "ds2") -> Optional[CodingDecoder]:
    """
    Get appropriate coding decoder for a module.

    Args:
        module_name: Module identifier (e.g., "IKE", "LCM", "GM", "IKE (instrument cluster)")
        protocol: Protocol (ds2, kwp2000, uds)

    Returns:
        CodingDecoder instance or None if not supported
    """
    # Normalize module name (handle descriptive names)
    module_name_upper = module_name.upper()

    # E39 DS2 modules
    if protocol == "ds2":
        if "IKE" in module_name_upper:
            return CodingDecoder(IKE_CODING_MAP)
        elif "LCM" in module_name_upper:
            return CodingDecoder(LCM_CODING_MAP)
        elif "GM" in module_name_upper or "ZKE" in module_name_upper:
            return CodingDecoder(GM_CODING_MAP)
        elif "IHKA" in module_name_upper:
            return CodingDecoder(IHKA_CODING_MAP)

    return None


# === Known Coding Examples ===

CODING_EXAMPLES = {
    "E39_IKE_US": {
        "description": "E39 IKE - US Market with digital speed",
        "hex": "01 0F 01 01 41",
        "decoded": {
            "Vehicle Type": "Touring",
            "Units": "mph, °F, mpg, miles",
            "Country": "USA",
            "Language": "English (US)",
            "Digital speed display": "Enabled",
            "Date format": "MM/DD/YYYY",
            "Time format": "12h AM/PM"
        }
    },
    "E39_LCM_US_Xenon": {
        "description": "E39 LCM - US Market with Xenon, comfort blink, DRL",
        "hex": "01 3C 02 00",
        "decoded": {
            "Market": "USA/FMVSS",
            "US turn signals": "Enabled",
            "Daytime running lights": "Enabled",
            "Comfort blink": "Enabled",
            "Headlight Type": "Xenon with self-leveling"
        }
    }
}

# === Coding Presets ===
# One-click modifications for common features

IKE_PRESETS = {
    "enable_digital_speed": {
        "name": "Enable Digital Speed Display",
        "description": "Show digital speed in instrument cluster center display",
        "module": "IKE",
        "bytes": {
            4: {"bits": {0: 1}}  # Byte 4, bit 0 = 1
        }
    },
    "disable_digital_speed": {
        "name": "Disable Digital Speed Display",
        "description": "Hide digital speed display",
        "module": "IKE",
        "bytes": {
            4: {"bits": {0: 0}}
        }
    },
    "us_date_format": {
        "name": "US Date Format (MM/DD/YYYY)",
        "description": "Change date format to US style",
        "module": "IKE",
        "bytes": {
            4: {"bits": {6: 1}}  # Byte 4, bit 6 = 1
        }
    },
    "eu_date_format": {
        "name": "EU Date Format (DD.MM.YYYY)",
        "description": "Change date format to European style",
        "module": "IKE",
        "bytes": {
            4: {"bits": {6: 0}}
        }
    },
    "12h_time": {
        "name": "12-Hour Time (AM/PM)",
        "description": "Use 12-hour time format with AM/PM",
        "module": "IKE",
        "bytes": {
            4: {"bits": {7: 1}}  # Byte 4, bit 7 = 1
        }
    },
    "24h_time": {
        "name": "24-Hour Time",
        "description": "Use 24-hour time format",
        "module": "IKE",
        "bytes": {
            4: {"bits": {7: 0}}
        }
    }
}

LCM_PRESETS = {
    "enable_us_signals": {
        "name": "Enable US Turn Signals (Amber)",
        "description": "Rear turn signals flash amber instead of red (requires amber bulbs)",
        "module": "LCM",
        "bytes": {
            1: {"bits": {4: 1}}  # Byte 1, bit 4 = 1
        }
    },
    "disable_us_signals": {
        "name": "Disable US Turn Signals (Red)",
        "description": "Rear turn signals use red brake lights (EU style)",
        "module": "LCM",
        "bytes": {
            1: {"bits": {4: 0}}
        }
    },
    "enable_comfort_blink": {
        "name": "Enable Comfort Blink",
        "description": "3 blinks from a tap of the turn signal stalk",
        "module": "LCM",
        "bytes": {
            1: {"bits": {5: 1}}  # Byte 1, bit 5 = 1
        }
    },
    "disable_comfort_blink": {
        "name": "Disable Comfort Blink",
        "description": "Standard turn signal operation",
        "module": "LCM",
        "bytes": {
            1: {"bits": {5: 0}}
        }
    },
    "enable_drl": {
        "name": "Enable Daytime Running Lights",
        "description": "Low beams on during day (where legal)",
        "module": "LCM",
        "bytes": {
            1: {"bits": {3: 1}}  # Byte 1, bit 3 = 1
        }
    },
    "disable_drl": {
        "name": "Disable Daytime Running Lights",
        "description": "Headlights off during day",
        "module": "LCM",
        "bytes": {
            1: {"bits": {3: 0}}
        }
    },
    "enable_welcome_lights": {
        "name": "Enable Welcome Lights",
        "description": "Lights illuminate when unlocking car",
        "module": "LCM",
        "bytes": {
            1: {"bits": {0: 1}}  # Byte 1, bit 0 = 1
        }
    },
    "disable_welcome_lights": {
        "name": "Disable Welcome Lights",
        "description": "No lights when unlocking",
        "module": "LCM",
        "bytes": {
            1: {"bits": {0: 0}}
        }
    },
    "enable_follow_me_home": {
        "name": "Enable Follow-Me-Home",
        "description": "Lights stay on after locking car",
        "module": "LCM",
        "bytes": {
            1: {"bits": {2: 1}}  # Byte 1, bit 2 = 1
        }
    },
    "disable_follow_me_home": {
        "name": "Disable Follow-Me-Home",
        "description": "Lights off immediately when locking",
        "module": "LCM",
        "bytes": {
            1: {"bits": {2: 0}}
        }
    }
}

GM_PRESETS = {
    "enable_auto_lock": {
        "name": "Enable Auto Lock at Speed",
        "description": "Automatically lock doors when driving above 15 km/h",
        "module": "GM",
        "bytes": {
            1: {"bits": {0: 1}}
        }
    },
    "disable_auto_lock": {
        "name": "Disable Auto Lock at Speed",
        "description": "Don't automatically lock doors when driving",
        "module": "GM",
        "bytes": {
            1: {"bits": {0: 0}}
        }
    },
    "enable_selective_unlock": {
        "name": "Enable Selective Door Unlock",
        "description": "First key press unlocks driver door only, second press unlocks all",
        "module": "GM",
        "bytes": {
            1: {"bits": {2: 1}}
        }
    },
    "disable_selective_unlock": {
        "name": "Disable Selective Door Unlock",
        "description": "All doors unlock with first key press",
        "module": "GM",
        "bytes": {
            1: {"bits": {2: 0}}
        }
    },
    "enable_comfort_close": {
        "name": "Enable Comfort Close",
        "description": "Hold lock button to close all windows and sunroof",
        "module": "GM",
        "bytes": {
            1: {"bits": {3: 1}}
        }
    },
    "disable_comfort_close": {
        "name": "Disable Comfort Close",
        "description": "Lock button only locks doors",
        "module": "GM",
        "bytes": {
            1: {"bits": {3: 0}}
        }
    },
    "enable_crash_unlock": {
        "name": "Enable Crash Unlock",
        "description": "Automatically unlock all doors after airbag deployment",
        "module": "GM",
        "bytes": {
            1: {"bits": {6: 1}}
        }
    },
    "disable_crash_unlock": {
        "name": "Disable Crash Unlock",
        "description": "Doors remain locked after crash",
        "module": "GM",
        "bytes": {
            1: {"bits": {6: 0}}
        }
    },
    "enable_mirror_fold": {
        "name": "Enable Mirror Fold on Lock",
        "description": "Fold mirrors when locking car (if equipped with folding mirrors)",
        "module": "GM",
        "bytes": {
            2: {"bits": {0: 1}}
        }
    },
    "disable_mirror_fold": {
        "name": "Disable Mirror Fold on Lock",
        "description": "Mirrors stay extended when locking",
        "module": "GM",
        "bytes": {
            2: {"bits": {0: 0}}
        }
    }
}

IHKA_PRESETS = {
    "temp_celsius": {
        "name": "Temperature in Celsius",
        "description": "Display temperature in °C",
        "module": "IHKA",
        "bytes": {
            1: {"value": 0x00}
        }
    },
    "temp_fahrenheit": {
        "name": "Temperature in Fahrenheit",
        "description": "Display temperature in °F",
        "module": "IHKA",
        "bytes": {
            1: {"value": 0x01}
        }
    },
    "enable_recirc_auto": {
        "name": "Enable Auto Recirculation",
        "description": "Automatically activate recirculation in tunnels/poor air quality",
        "module": "IHKA",
        "bytes": {
            2: {"bits": {0: 1}}
        }
    },
    "disable_recirc_auto": {
        "name": "Disable Auto Recirculation",
        "description": "Manual recirculation control only",
        "module": "IHKA",
        "bytes": {
            2: {"bits": {0: 0}}
        }
    },
    "enable_rest_function": {
        "name": "Enable Rest Function",
        "description": "Use residual engine heat after shutdown to warm cabin",
        "module": "IHKA",
        "bytes": {
            2: {"bits": {6: 1}}
        }
    },
    "disable_rest_function": {
        "name": "Disable Rest Function",
        "description": "No post-shutdown heating",
        "module": "IHKA",
        "bytes": {
            2: {"bits": {6: 0}}
        }
    },
    "auto_mode_comfort": {
        "name": "Auto Mode: Comfort",
        "description": "Prioritize comfort over efficiency",
        "module": "IHKA",
        "bytes": {
            2: {"bits": {3: 0}}
        }
    },
    "auto_mode_economy": {
        "name": "Auto Mode: Economy",
        "description": "Prioritize fuel efficiency",
        "module": "IHKA",
        "bytes": {
            2: {"bits": {3: 1}}
        }
    }
}

CODING_PRESETS = {
    "IKE": IKE_PRESETS,
    "LCM": LCM_PRESETS,
    "GM": GM_PRESETS,
    "IHKA": IHKA_PRESETS
}


def get_presets_for_module(module_name: str) -> Dict:
    """
    Get available coding presets for a module.

    Args:
        module_name: Module identifier (e.g., "IKE", "LCM")

    Returns:
        Dict of presets or empty dict if none available
    """
    module_name_upper = module_name.upper()
    for key in CODING_PRESETS:
        if key in module_name_upper:
            return CODING_PRESETS[key]
    return {}


if __name__ == "__main__":
    # Test decoder
    print("=== IKE Coding Decoder Test ===\n")

    # Example: E39 IKE coding bytes
    test_coding = bytes([0x01, 0x0F, 0x01, 0x01, 0x41])
    print(f"Raw coding: {test_coding.hex().upper()}\n")

    decoder = CodingDecoder(IKE_CODING_MAP)
    decoded = decoder.decode_coding(test_coding)

    for i, byte_info in enumerate(decoded["bytes"]):
        print(f"Byte {i}: {byte_info['name']} = {byte_info['raw']}")
        if byte_info.get("type") == "enum":
            print(f"  → {byte_info['value']}")
        elif byte_info.get("type") == "bitfield":
            for bit_name, bit_info in byte_info["bits"].items():
                print(f"  • {bit_name}: {bit_info['value']}")
        print()
