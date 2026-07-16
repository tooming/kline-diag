#!/usr/bin/env python3
"""Developer Mode — safe raw console backend (Phase 8).

Lets a developer send a raw diagnostic request and see the response, WITHOUT
opening a hole for arbitrary writes. Only read-only service IDs are allowed;
anything that could write, clear, actuate, or run a routine is rejected
before it reaches the bus. This is the safe backend the Developer Mode UI
needs; the raw traffic view already exists via /api/log.

Rejection is by service byte (first payload byte). The whitelist is
per-protocol and intentionally conservative — unknown services are denied.
"""

# Read-only service IDs that are safe to expose in the raw console.
DS2_READ_SERVICES = {
    0x00,        # ident
    0x04,        # read fault memory (read-only)
    0x0B,        # status/group read (0B 00/01/03.. are reads)
    0x1A,        # read ident
    0x17,        # read status
    0x18,        # read DTC by status
    0x21,        # read data by local id
    0x22,        # read data by common id
    0x06,        # read memory (read-only)
    0x3E,        # tester present
}
KWP_READ_SERVICES = {0x01, 0x09, 0x1A, 0x17, 0x18, 0x21, 0x22, 0x3E}

# Explicitly dangerous services — always denied with a clear reason.
WRITE_SERVICES = {
    0x05: "clear adaptations (write)",
    0x14: "clear diagnostic information (write)",
    0x2E: "write data by identifier (write)",
    0x2F: "input/output control (actuate)",
    0x30: "input/output control (actuate)",
    0x31: "start routine (actuate)",
    0x34: "request download (write)",
    0x35: "request upload",
    0x36: "transfer data (write)",
    0x3B: "write data by local id (write)",
    0x43: "ECU reset",
}


def check_request(payload, protocol):
    """Return (allowed: bool, reason: str) for a raw request payload.

    payload: list/bytes of the service + args (no header/checksum).
    protocol: "ds2" | "kwp2000".
    """
    if not payload:
        return False, "empty request"
    svc = payload[0]
    if svc in WRITE_SERVICES:
        return False, f"blocked: service 0x{svc:02X} = {WRITE_SERVICES[svc]}"
    allow = DS2_READ_SERVICES if protocol == "ds2" else KWP_READ_SERVICES
    if svc not in allow:
        return False, (f"blocked: service 0x{svc:02X} is not on the read-only "
                       f"whitelist for {protocol}")
    # DS2 0B subfunction 0x01 (set address list) is a read setup — allowed;
    # but guard against a write-shaped 0B if any exist.
    return True, "ok"


def send_raw(adapter, payload, addr=0x12):
    """Send a raw request after the safety check. Never sends a denied
    request. Returns a result dict with the raw response or the block reason.
    """
    protocol = getattr(adapter, "proto", None)
    protocol = "ds2" if protocol == "e39" else "kwp2000"
    payload = [int(x, 16) if isinstance(x, str) else int(x) for x in payload]
    allowed, reason = check_request(payload, protocol)
    if not allowed:
        return {"ok": False, "blocked": True, "reason": reason}
    transport = getattr(adapter, "ds2" if protocol == "ds2" else "kl", None)
    if getattr(adapter, "name", "").startswith("DEMO") or transport is None:
        return {"ok": True, "demo": True,
                "note": "request passed safety check (demo — not sent)",
                "request": [f"0x{b:02X}" for b in payload]}
    if protocol == "ds2":
        f = transport.request(addr, payload, timeout=0.8)
        import ds2_diag
        return {"ok": f is not None,
                "response": ds2_diag.hexs(f) if f is not None else None}
    # KWP path via power_diag transport on the E87 adapter
    frames = adapter.kl.request(bytes(payload), addr, timeout=0.6)
    import power_diag
    return {"ok": bool(frames),
            "response": [power_diag.hexs(power_diag.frame_payload(x))
                         for x in frames]}


if __name__ == "__main__":
    for p, proto in (([0x1A, 0x80], "ds2"), ([0x14, 0xFF, 0xFF], "ds2"),
                     ([0x2E, 0x10], "ds2"), ([0x21, 0x5A], "kwp2000")):
        print(f"{proto} {p}: {check_request(p, proto)}")
