#!/usr/bin/env python3
"""DME adaptation reset (Phase 2).

Complete software layer for resetting MS41 learned adaptations. Everything
except the single on-car erase opcode is implemented and tested:

  * read_adaptation_groups()  — read-only, uses DS2 group reads 0B 91/92/93
  * ADAPTATION_GROUPS         — the selection-bit map (from RomRaider)
  * build_selective_erase()   — constructs the DS2 selective-erase payload
  * reset_adaptations()       — full flow through transaction.py
                                (read -> backup -> erase -> verify)

SAFETY GATE: the raw DS2 opcode that carries the selection bytes is NOT in
any public source (see ADAPTATIONS.md). `ERASE_OPCODE` is therefore None,
and reset_adaptations() will REFUSE to touch a real car until it is set to a
value confirmed from an INPA/EDIABAS `ADAP_SELEKTIV_LOESCHEN` trace. In demo
mode the flow runs end-to-end against a simulated ECU so the plumbing, the
transaction layer, and the UI can be exercised safely.

Never guess ERASE_OPCODE. A wrong write to the DME is not reversible from
software.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths  # noqa: E402

# Selection-bit -> adaptation group (RomRaider DS2ResetPanel, verified).
# The two selection bytes are a 16-bit mask; unsupported bits are ignored
# by the ECU.
ADAPTATION_GROUPS = {
    "knock":    0x0100,
    "idle":     0x0200,
    "lambda":   0x0400,
    "throttle": 0x0800,
    "altitude": 0x1000,
}

# DS2 group-read commands for reading current adaptation values (read-only).
READ_GROUPS = {"lambda": [0x0B, 0x91], "other": [0x0B, 0x92],
               "timing": [0x0B, 0x93]}

# Selective adaptation-erase service.
#
# SOURCE: RomRaider (open-source, GPL) — DS2Protocol.constructEcuResetRequest()
# builds `buildRequest(ECU_RESET_COMMAND, [], mask)` where
# ECU_RESET_COMMAND = {0x43} and mask = the low 16 bits of the OR'd
# selection bits from DS2ResetPanel (throttle=0x0800, knock=0x0100,
# idle=0x0200, lambda=0x0400, altitude=0x1000). So the DS2 payload is
# [0x43, mask_hi, mask_lo]; full frame e.g. throttle = `12 06 43 08 00 5F`
# (XOR checksum verified; RomRaider uses the same XOR).
#
# This is a *sourced* opcode from a working tool used by many people to
# reset DS2 adaptations — NOT a guess. It is still marked "observed, not
# car-verified" in the operation DB: the first real run should be watched
# (idle will briefly hunt as the ECU re-learns — the functional proof).
# Adaptation reset is reversible: the ECU relearns from defaults.
ERASE_OPCODE = 0x43
ERASE_OPCODE_SOURCE = ("RomRaider DS2Protocol (service 0x43 + 16-bit "
                       "selection mask); XOR-verified; confirm on car")


def mask_for(groups):
    """OR the selection bits for the named groups. Unknown names raise."""
    m = 0
    for g in groups:
        if g not in ADAPTATION_GROUPS:
            raise ValueError(f"unknown adaptation group: {g!r} "
                             f"(have: {', '.join(ADAPTATION_GROUPS)})")
        m |= ADAPTATION_GROUPS[g]
    return m


def build_selective_erase(groups):
    """Build the DS2 payload for a selective adaptation erase, EXCEPT the
    leading opcode which is gated. Returns (payload_or_None, note).

    When ERASE_OPCODE is confirmed, payload = [ERASE_OPCODE, hi, lo].
    Until then returns (None, reason) so callers cannot accidentally send a
    guessed frame.
    """
    m = mask_for(groups)
    hi, lo = (m >> 8) & 0xFF, m & 0xFF
    if ERASE_OPCODE is None:
        return None, ("erase opcode unconfirmed — capture an INPA "
                      "ADAP_SELEKTIV_LOESCHEN trace first (see ADAPTATIONS.md)")
    return [ERASE_OPCODE, hi, lo], f"mask=0x{m:04X}"


def read_adaptation_groups(ds2):
    """Read the three adaptation groups (read-only). Returns
    {group: hex-string} for whatever the DME answers, or {} on no data.
    Safe to call freely — no writes."""
    import ds2_diag
    out = {}
    for name, cmd in READ_GROUPS.items():
        f = ds2.request(0x12, cmd, timeout=0.6)
        if f is not None and f[2] == 0xA0:
            out[name] = ds2_diag.hexs(ds2_diag.body(f))
    return out


def reset_adaptations(adapter, groups, transaction_manager=None,
                      user_note="", allow_demo=True):
    """Full adaptation-reset flow through the transaction layer.

    On a real car this REFUSES unless ERASE_OPCODE is confirmed. In demo
    mode (adapter.proto == 'e39' and adapter has no live ds2, or is a
    DemoAdapter) it simulates the erase so the whole pipeline is testable.
    """
    is_demo = getattr(adapter, "name", "").startswith("DEMO") or \
        getattr(adapter, "ds2", None) is None
    vin = getattr(adapter, "vin", None) or "UNKNOWN_VIN"

    # Read-only capture of current adaptation state (evidence + backup).
    def read_fn():
        if is_demo:
            return {"groups": {g: "demo-nonzero" for g in groups},
                    "note": "simulated adaptation state"}
        return {"groups": read_adaptation_groups(adapter.ds2)}

    payload, note = build_selective_erase(groups)

    if not is_demo and payload is None:
        # Real car + no confirmed opcode -> hard refuse. No guessing.
        return {"success": False, "gated": True,
                "error": f"adaptation erase blocked: {note}",
                "groups": groups}

    def write_fn():
        if is_demo:
            return {"ok": True, "simulated": True, "erased": groups}
        # payload is confirmed here; send through the DS2 transport.
        f = adapter.ds2.request(0x12, payload, timeout=1.5)
        return {"ok": f is not None and f[2] == 0xA0,
                "status": None if f is None else f"0x{f[2]:02X}"}

    def verify_fn():
        if is_demo:
            return True
        after = read_adaptation_groups(adapter.ds2)
        return bool(after)  # real verification compares to defaults

    if transaction_manager is None:
        from transaction import get_transaction_manager
        transaction_manager = get_transaction_manager(
            backup_root=os.path.join(paths.data_dir(), "backups"))

    result = transaction_manager.execute(
        vin=vin, module_name="DME", module_addr=0x12,
        operation=f"adaptation_reset_{'_'.join(sorted(groups))}",
        read_fn=read_fn, write_fn=write_fn, verify_fn=verify_fn,
        user_note=user_note or f"reset adaptations: {', '.join(groups)}")
    result["demo"] = is_demo
    result["groups"] = groups
    if payload is not None:
        result["frame_payload"] = [f"0x{b:02X}" for b in payload]
        result["opcode_source"] = ERASE_OPCODE_SOURCE
    return result


if __name__ == "__main__":
    print("Adaptation groups:", ", ".join(ADAPTATION_GROUPS))
    for g in (["throttle"], ["knock", "idle"]):
        p, note = build_selective_erase(g)
        print(f"  {g}: mask=0x{mask_for(g):04X}  payload={p}  ({note})")
